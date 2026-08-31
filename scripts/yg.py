#!/usr/bin/env python3
"""консольный клиент YouGile REST API v2

    yg.py <инструмент> '{"ключ": "значение"}'
    yg.py <инструмент> -          # аргументы из stdin
    yg.py setup                   # получить и сохранить ключ
    yg.py --list                  # перечислить инструменты
    yg.py --selfcheck             # прогнать встроенные проверки
"""

from __future__ import annotations

import json
import mimetypes
import os
import platform
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from getpass import getpass
from typing import Any, Final, NamedTuple

API_ROOT: Final[str] = "https://yougile.com/api-v2"
SECRET_LABEL: Final[str] = "yougile-api-key"
ENV_VAR: Final[str] = "YOUGILE_API_KEY"

# 429 приходит при превышении 50 запросов в минуту, пятисотые - при перебоях на стороне
# сервиса; и то и другое проходит само, поэтому запрос стоит повторить
RETRY_ON: Final[frozenset[int]] = frozenset({429, 500, 502, 503, 504})
# трёх попыток хватает: лимит частоты сбрасывается в пределах минуты, а пауза растёт
RETRY_ATTEMPTS: Final[int] = 3
# пауза удваивается с каждой попыткой: 2 и 4 секунды, суммарно около 6 секунд ожидания
RETRY_PAUSE_SEC: Final[float] = 2.0
# страница по умолчанию 50 строк, максимум API - 1000
MAX_PAGE: Final[int] = 1000

JsonDict = dict[str, Any]
JsonValue = JsonDict | list[Any]


class ApiError(RuntimeError):
    """сервер ответил ошибкой"""


class UsageError(RuntimeError):
    """не хватает аргумента, ключа или файла"""


class Route(NamedTuple):
    """маршрут: метод, шаблон пути, разрешённые query-параметры, нужен ли ключ"""

    method: str
    path: str
    query: tuple[str, ...] = ()
    anonymous: bool = False


# общие наборы фильтров, чтобы не повторять их в каждой строке таблицы
PAGED: Final[tuple[str, ...]] = ("includeDeleted", "limit", "offset")
TASK_FILTERS: Final[tuple[str, ...]] = PAGED + (
    "title", "columnId", "assignedTo", "stickerId", "stickerStateId",
)
STICKER_FILTERS: Final[tuple[str, ...]] = PAGED + ("name", "boardId")

# путь пишется шаблоном: {имя} берётся из аргументов, остальное уходит телом
ROUTES: Final[dict[str, Route]] = {
    # ключи доступа
    "auth_companies": Route("POST", "/auth/companies", anonymous=True),
    "auth_create_key": Route("POST", "/auth/keys", anonymous=True),
    "auth_list_keys": Route("POST", "/auth/keys/get", anonymous=True),
    "auth_delete_key": Route("DELETE", "/auth/keys/{key}", anonymous=True),
    # компания
    "company_get": Route("GET", "/companies"),
    "company_update": Route("PUT", "/companies"),
    # проекты
    "projects_list": Route("GET", "/projects", PAGED + ("title",)),
    "projects_get": Route("GET", "/projects/{id}"),
    "projects_create": Route("POST", "/projects"),
    "projects_update": Route("PUT", "/projects/{id}"),
    # роли в проекте
    "roles_list": Route("GET", "/projects/{projectId}/roles", ("limit", "offset", "name")),
    "roles_get": Route("GET", "/projects/{projectId}/roles/{id}"),
    "roles_create": Route("POST", "/projects/{projectId}/roles"),
    "roles_update": Route("PUT", "/projects/{projectId}/roles/{id}"),
    "roles_delete": Route("DELETE", "/projects/{projectId}/roles/{id}"),
    # доски и колонки
    "boards_list": Route("GET", "/boards", PAGED + ("title", "projectId")),
    "boards_get": Route("GET", "/boards/{id}"),
    "boards_create": Route("POST", "/boards"),
    "boards_update": Route("PUT", "/boards/{id}"),
    "columns_list": Route("GET", "/columns", PAGED + ("title", "boardId")),
    "columns_get": Route("GET", "/columns/{id}"),
    "columns_create": Route("POST", "/columns"),
    "columns_update": Route("PUT", "/columns/{id}"),
    # задачи: /tasks отдаёт свежие сверху, /task-list в прямом порядке
    "tasks_list": Route("GET", "/tasks", TASK_FILTERS),
    "tasks_list_chrono": Route("GET", "/task-list", TASK_FILTERS),
    "tasks_get": Route("GET", "/tasks/{id}"),
    "tasks_create": Route("POST", "/tasks"),
    "tasks_update": Route("PUT", "/tasks/{id}"),
    "task_subscribers_get": Route("GET", "/tasks/{id}/chat-subscribers"),
    "task_subscribers_update": Route("PUT", "/tasks/{id}/chat-subscribers"),
    # сотрудники
    "users_list": Route("GET", "/users", ("limit", "offset", "email", "projectId")),
    "users_get": Route("GET", "/users/{id}"),
    "users_me": Route("GET", "/users/me"),
    "users_invite": Route("POST", "/users"),
    "users_update": Route("PUT", "/users/{id}"),
    "users_delete": Route("DELETE", "/users/{id}"),
    # отделы
    "departments_list": Route("GET", "/departments", PAGED + ("title", "parentId")),
    "departments_get": Route("GET", "/departments/{id}"),
    "departments_create": Route("POST", "/departments"),
    "departments_update": Route("PUT", "/departments/{id}"),
    # чаты
    "chat_messages": Route(
        "GET", "/chats/{chatId}/messages",
        PAGED + ("fromUserId", "text", "label", "since", "includeSystem"),
    ),
    "chat_send": Route("POST", "/chats/{chatId}/messages"),
    "chat_message_get": Route("GET", "/chats/{chatId}/messages/{id}"),
    "chat_message_update": Route("PUT", "/chats/{chatId}/messages/{id}"),
    "chat_typing": Route("POST", "/chats/{chatId}/typing"),
    "group_chats_list": Route("GET", "/group-chats", PAGED + ("title",)),
    "group_chats_get": Route("GET", "/group-chats/{id}"),
    "group_chats_create": Route("POST", "/group-chats"),
    "group_chats_update": Route("PUT", "/group-chats/{id}"),
    # текстовые стикеры и их состояния
    "stickers_list": Route("GET", "/string-stickers", STICKER_FILTERS),
    "stickers_get": Route("GET", "/string-stickers/{id}"),
    "stickers_create": Route("POST", "/string-stickers"),
    "stickers_update": Route("PUT", "/string-stickers/{id}"),
    "sticker_states_create": Route("POST", "/string-stickers/{stickerId}/states"),
    "sticker_states_get": Route(
        "GET", "/string-stickers/{stickerId}/states/{stateId}", ("includeDeleted",),
    ),
    "sticker_states_update": Route("PUT", "/string-stickers/{stickerId}/states/{stateId}"),
    # спринтовые стикеры
    "sprint_stickers_list": Route("GET", "/sprint-stickers", STICKER_FILTERS),
    "sprint_stickers_get": Route("GET", "/sprint-stickers/{id}"),
    "sprint_stickers_create": Route("POST", "/sprint-stickers"),
    "sprint_stickers_update": Route("PUT", "/sprint-stickers/{id}"),
    "sprint_states_create": Route("POST", "/sprint-stickers/{stickerId}/states"),
    "sprint_states_get": Route(
        "GET", "/sprint-stickers/{stickerId}/states/{stateId}", ("includeDeleted",),
    ),
    "sprint_states_update": Route("PUT", "/sprint-stickers/{stickerId}/states/{stateId}"),
    # подписки на события
    "webhooks_list": Route("GET", "/webhooks", ("includeDeleted",)),
    "webhooks_create": Route("POST", "/webhooks"),
    "webhooks_update": Route("PUT", "/webhooks/{id}"),
    # CRM: контактные лица и поиск по внешнему идентификатору
    "crm_contact_create": Route("POST", "/crm/contact-persons"),
    "crm_contact_find": Route("GET", "/crm/contacts/by-external-id", ("provider", "chatId")),
}


# ─── сборка запроса ───────────────────────────────────────────────────

def fill_path(template: str, args: JsonDict) -> str:
    """подставить сегменты пути, изъяв их из аргументов"""

    def take(found: re.Match[str]) -> str:
        name = found.group(1)
        if name not in args:
            raise UsageError(f"нужен аргумент '{name}' для пути {template}")
        return urllib.parse.quote(str(args.pop(name)), safe="")

    return re.sub(r"\{(\w+)}", take, template)


def encode_query(params: JsonDict) -> str:
    """собрать query-строку

    булево приводится к true/false: на True с большой буквы сервер отвечает 200
    и молча игнорирует фильтр
    """
    if not params:
        return ""
    flat = {k: str(v).lower() if isinstance(v, bool) else v for k, v in params.items()}
    return "?" + urllib.parse.urlencode(flat)


def split_args(route: Route, args: JsonDict) -> tuple[str, JsonDict | None]:
    """разложить аргументы на путь, фильтры и тело"""
    rest = dict(args)
    path = fill_path(route.path, rest)
    query = {key: rest.pop(key) for key in route.query if key in rest}
    body = None if route.method == "GET" else rest
    return path + encode_query(query), body


# ─── транспорт ────────────────────────────────────────────────────────

def _explain(code: int) -> str:
    """подсказать, что делать с кодом ответа: тело ответа у YouGile редко объясняет причину"""
    hints = {
        401: "Ключ недействителен или отозван. Проверьте YOUGILE_API_KEY либо перевыпустите"
             " ключ через 'yg.py setup'.",
        403: "Ключ рабочий, но у аккаунта нет прав на это действие. Права API совпадают с"
             " правами аккаунта в интерфейсе.",
        404: "Объект не найден. Возможно, он помечен удалённым: повторите с"
             " includeDeleted: true.",
        400: "Сервер отверг запрос. Проверьте формат полей по references/api.md, но учтите:"
             " нехватку прав YouGile тоже показывает как 400, а не 403, поэтому на аккаунте"
             " без прав администратора так отвечают создание проекта и удаление стикера.",
    }
    hint = hints.get(code)
    return f"\n{hint}" if hint else ""


def send(method: str, path: str, token: str | None, body: JsonDict | None) -> JsonValue:
    """выполнить запрос, повторяя его при 429 и пятисотых

    POST повторяется только с idempotencyKey в теле: без него повтор оборвавшегося
    создания заведёт вторую задачу или проект
    """
    retriable = method != "POST" or (body is not None and "idempotencyKey" in body)
    request = urllib.request.Request(
        API_ROOT + path,
        data=json.dumps(body).encode() if body is not None else None,
        method=method,
        headers={"Content-Type": "application/json"}
        | ({"Authorization": f"Bearer {token}"} if token else {}),
    )
    last: Exception | None = None
    for attempt in range(1, RETRY_ATTEMPTS + 1):
        try:
            with urllib.request.urlopen(request) as answer:
                payload = answer.read().decode()
                return json.loads(payload) if payload else {}
        except urllib.error.HTTPError as failure:
            if failure.code not in RETRY_ON:
                raise ApiError(
                    f"{method} {path} -> HTTP {failure.code}: "
                    f"{failure.read().decode()[:500]}{_explain(failure.code)}"
                ) from failure
            last = failure
        except urllib.error.URLError as failure:
            last = failure
        if not retriable:
            raise ApiError(
                f"{method} {path} -> {last}. Повтор не сделан: у POST без idempotencyKey"
                " он может создать дубль. Добавьте idempotencyKey и повторите."
            )
        if attempt < RETRY_ATTEMPTS:
            print(f"попытка {attempt} не прошла ({last}), повтор", file=sys.stderr)
            time.sleep(RETRY_PAUSE_SEC * attempt)
    raise ApiError(f"{method} {path} -> не удалось за {RETRY_ATTEMPTS} попытки: {last}")


# ─── хранение ключа ───────────────────────────────────────────────────

def _keychain_read(label: str) -> str | None:
    """прочитать пароль из связки ключей macOS"""
    try:
        return subprocess.check_output(
            ["security", "find-generic-password", "-s", label, "-w"],
            text=True, stderr=subprocess.DEVNULL,
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def _keychain_write(label: str, secret: str) -> bool:
    """записать пароль в связку ключей macOS, перетирая прежний"""
    account = os.environ.get("USER", "yougile")
    try:
        subprocess.run(
            ["security", "delete-generic-password", "-s", label],
            capture_output=True, check=False,
        )
        subprocess.run(
            ["security", "add-generic-password", "-s", label, "-a", account, "-w", secret],
            capture_output=True, check=True,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def read_key() -> str:
    """достать ключ: сначала переменная окружения, затем хранилище системы"""
    from_env = os.environ.get(ENV_VAR)
    if from_env:
        return from_env
    if platform.system() == "Darwin":
        stored = _keychain_read(SECRET_LABEL)
        if stored:
            return stored
    raise UsageError(f"ключ не найден: запустите 'yg.py setup' или задайте {ENV_VAR}")


def save_key(secret: str) -> str:
    """положить ключ в связку ключей, вернув её название

    хранилище есть только для macOS: cmdkey на Windows умеет записывать секрет, но не
    отдавать его обратно, поэтому там ключ живёт в переменной окружения
    """
    if platform.system() == "Darwin" and _keychain_write(SECRET_LABEL, secret):
        return "связка ключей macOS"
    return ""


# ─── отдельные операции ───────────────────────────────────────────────

def _pick_company(companies: list[JsonDict], index: Any) -> JsonDict:
    """выбрать компанию: единственную молча, иначе по номеру"""
    if len(companies) == 1:
        return companies[0]
    if index is not None:
        position = int(index) - 1
        if not 0 <= position < len(companies):
            raise UsageError(f"companyIndex вне диапазона 1..{len(companies)}")
        return companies[position]
    for number, company in enumerate(companies, start=1):
        mark = " (админ)" if company.get("isAdmin") else ""
        print(f"  [{number}] {company['name']}{mark}", file=sys.stderr)
    return _pick_company(companies, input(f"Компания [1-{len(companies)}]: ").strip())


def run_setup(args: JsonDict) -> JsonValue:
    """получить ключ по логину и паролю и сохранить его

    логин и пароль можно передать аргументами, иначе они спрашиваются в терминале;
    пароль читается скрытым вводом, поэтому нужен настоящий tty
    """
    login = args.get("login") or input("Почта YouGile: ").strip()
    password = args.get("password") or getpass("Пароль: ").strip()
    if not login or not password:
        raise UsageError("нужны почта и пароль")

    credentials = {"login": login, "password": password}
    companies = send("POST", "/auth/companies", None, credentials).get("content", [])
    if not companies:
        raise UsageError("у аккаунта нет компаний")

    chosen = _pick_company(companies, args.get("companyIndex"))
    key = send("POST", "/auth/keys", None,
               credentials | {"companyId": chosen["id"]}).get("key")
    if not key:
        raise ApiError("сервер не вернул ключ")

    where = save_key(key)
    if where:
        print(f"ключ сохранён: {where}", file=sys.stderr)
    else:
        print(f"сохранить не удалось, задайте вручную:\n  export {ENV_VAR}='{key}'",
              file=sys.stderr)
    return {"company": chosen["name"], "stored": where or None}


def upload_file(args: JsonDict) -> JsonValue:
    """загрузить файл и получить его адрес

    multipart собирается вручную: тянуть стороннюю библиотеку ради одного запроса незачем
    """
    source = args.get("path")
    if not source:
        raise UsageError("нужен аргумент 'path'")
    if not os.path.isfile(source):
        raise UsageError(f"файл не найден: {source}")

    name = os.path.basename(source)
    kind = mimetypes.guess_type(name)[0] or "application/octet-stream"
    edge = uuid.uuid4().hex
    with open(source, "rb") as handle:
        content = handle.read()
    payload = b"".join([
        f"--{edge}\r\n".encode(),
        f'Content-Disposition: form-data; name="file"; filename="{name}"\r\n'.encode(),
        f"Content-Type: {kind}\r\n\r\n".encode(),
        content,
        f"\r\n--{edge}--\r\n".encode(),
    ])
    request = urllib.request.Request(
        f"{API_ROOT}/upload-file", data=payload, method="POST",
        headers={
            "Content-Type": f"multipart/form-data; boundary={edge}",
            "Authorization": f"Bearer {read_key()}",
        },
    )
    try:
        with urllib.request.urlopen(request) as answer:
            body = answer.read().decode()
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as failure:
        raise ApiError(
            f"POST /upload-file -> HTTP {failure.code}: {failure.read().decode()[:500]}"
        ) from failure


DIRECT: Final[dict[str, Any]] = {"setup": run_setup, "upload_file": upload_file}


# ─── командная строка ─────────────────────────────────────────────────

# поля, без которых сервер вернёт 400: проверяются заранее, чтобы не тратить запрос
REQUIRED_BODY: Final[dict[str, tuple[str, ...]]] = {
    "chat_send": ("text", "textHtml", "label"),
    "tasks_create": ("title",),
    "projects_create": ("title",),
    "boards_create": ("title", "projectId"),
    "columns_create": ("title", "boardId"),
    "webhooks_create": ("url", "event", "filters"),
    "users_invite": ("email",),
    "roles_create": ("name", "permissions"),
    "crm_contact_create": ("projectId", "title"),
}


def dispatch(tool: str, args: JsonDict) -> JsonValue:
    """выполнить инструмент по имени"""
    if tool in DIRECT:
        return DIRECT[tool](args)
    route = ROUTES.get(tool)
    if route is None:
        raise UsageError(f"нет такого инструмента: {tool}")
    absent = [f for f in REQUIRED_BODY.get(tool, ()) if f not in args]
    if absent:
        raise UsageError(f"{tool}: не хватает обязательных полей: {', '.join(absent)}")
    if args.get("all"):
        return collect_pages(route, args)
    path, body = split_args(route, args)
    token = None if route.anonymous else read_key()
    return send(route.method, path, token, body)


def collect_pages(route: Route, args: JsonDict) -> JsonValue:
    """пройти все страницы списка и вернуть строки одним массивом

    пагинация - самая частая ошибка при работе с этим API: без неё в руках оказываются
    первые 50 строк, похожие на полный ответ
    """
    if route.method != "GET" or "limit" not in route.query:
        raise UsageError("'all' работает только со списками")
    token = read_key()
    query = dict(args)
    query.pop("all")
    query["limit"] = MAX_PAGE
    collected: list[Any] = []
    offset = 0
    while True:
        query["offset"] = offset
        path, _ = split_args(route, query)
        page = send("GET", path, token, None)
        rows = page.get("content", [])
        collected += rows
        # пустая страница обрывает обход, даже если сервер продолжает обещать next
        if not rows or not page.get("paging", {}).get("next"):
            return {"paging": {"count": len(collected), "all": True}, "content": collected}
        offset += MAX_PAGE


def read_arguments(raw: str | None) -> JsonDict:
    """разобрать аргументы: строка JSON или '-' для чтения из stdin"""
    if raw is None:
        return {}
    text = sys.stdin.read() if raw == "-" else raw
    if not text.strip():
        return {}
    parsed = json.loads(text)
    if not isinstance(parsed, dict):
        raise UsageError("аргументы должны быть объектом JSON")
    return parsed


def selfcheck() -> None:
    """проверить сборку запроса: здесь легче всего ошибиться незаметно"""
    assert encode_query({}) == ""
    assert encode_query({"includeDeleted": True}) == "?includeDeleted=true"
    assert encode_query({"includeDeleted": False}) == "?includeDeleted=false"
    assert encode_query({"title": "a/b c&d"}) == "?title=a%2Fb+c%26d"

    args = {"id": "7", "limit": 5, "completed": True}
    path, body = split_args(Route("PUT", "/tasks/{id}"), args)
    assert path == "/tasks/7", path
    assert body == {"limit": 5, "completed": True}, body
    assert args == {"id": "7", "limit": 5, "completed": True}, "аргументы изменились"

    path, body = split_args(Route("GET", "/tasks", ("limit", "includeDeleted")),
                            {"limit": 5, "includeDeleted": True, "columnId": "x"})
    assert path == "/tasks?limit=5&includeDeleted=true", path
    assert body is None, body

    path, _ = split_args(Route("GET", "/chats/{chatId}/messages/{id}"),
                         {"chatId": "a b", "id": 3})
    assert path == "/chats/a%20b/messages/3", path

    try:
        fill_path("/tasks/{id}", {})
    except UsageError:
        pass
    else:
        raise AssertionError("пропущенный сегмент пути должен приводить к ошибке")

    assert not set(DIRECT) & set(ROUTES), "инструмент объявлен дважды"
    assert set(REQUIRED_BODY) <= set(ROUTES), "проверка полей ссылается на несуществующий инструмент"
    assert _explain(401) and _explain(403) and not _explain(418)

    try:
        dispatch("chat_send", {"chatId": "x", "text": "привет"})
    except UsageError as failure:
        assert "textHtml" in str(failure) and "label" in str(failure), failure
    else:
        raise AssertionError("отсутствие обязательных полей должно ловиться до запроса")

    print(f"ок: инструментов {len(ROUTES) + len(DIRECT)}")


def main(argv: list[str]) -> int:
    """точка входа: разобрать аргументы, выполнить инструмент, напечатать ответ"""
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__.strip())
        return 0
    if argv[0] == "--selfcheck":
        selfcheck()
        return 0
    if argv[0] == "--list":
        print("\n".join(sorted(set(ROUTES) | set(DIRECT))))
        return 0

    try:
        result = dispatch(argv[0], read_arguments(argv[1] if len(argv) > 1 else None))
    except (ApiError, UsageError, json.JSONDecodeError) as failure:
        print(json.dumps({"error": str(failure)}, ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
