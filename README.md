# Скилл YouGile для Claude Code

A Claude Code plugin for the YouGile task tracker (REST API v2), in Russian.
Install with `/plugin marketplace add boundlessend/yougile-tracking`, then
`/plugin install yougile-tracking@senya-plugins`.

Плагин Claude Code для работы с [YouGile](https://yougile.com) через REST API v2.
Один файл на Python, только стандартная библиотека, зависимостей нет.
Нужен Python 3.10 или новее.

Покрыты все 69 операций спецификации: проекты, доски, колонки, задачи,
сотрудники, отделы, роли в проектах, чаты и групповые чаты, текстовые и
спринтовые стикеры, вебхуки, загрузка файлов, контакты CRM.

## Установка

```
/plugin marketplace add boundlessend/yougile-tracking
/plugin install yougile-tracking@senya-plugins
```

Затем один раз получить ключ API:

```bash
YG=$(ls -d ~/.claude/plugins/cache/senya-plugins/yougile-tracking/*/skills/yougile-tracking/scripts/yg.py | tail -1)
python3 "$YG" setup
```

Переменной `CLAUDE_PLUGIN_ROOT` в обычной оболочке нет, она подставляется только
внутри Claude Code, поэтому в терминале путь берётся из каталога установленного
плагина: версия в нём меняется с каждым обновлением.

Команда спросит почту и пароль от аккаунта, создаст ключ и положит его в связку
ключей macOS. Нужен настоящий терминал: пароль читается скрытым вводом и требует
tty, через агента запустить не выйдет. Если ключ уже есть, положите его в
переменную `YOUGILE_API_KEY` или сохраните в связку ключей под именем
`yougile-api-key`. На Windows связки ключей нет, там работает только переменная
окружения.

Каждый запуск `setup` создаёт на сервере новый ключ, а прежний остаётся
действующим: локальная копия перезаписывается, отзыва не происходит. Лимит - 30
ключей на аккаунт, лишние смотрят через `auth_list_keys` и снимают через
`auth_delete_key`.

Проверить установку: `python3 "$YG" --selfcheck`. Проверка работает без сети,
она сверяет сборку запросов, а не доступ к сервису.

Обновления приезжают штатно:

```
/plugin marketplace update senya-plugins
/plugin update yougile-tracking@senya-plugins
```

## Как пользоваться

Обычно скилл вызывается сам, когда речь заходит о задачах в YouGile. Вручную:

```bash
YG=$(ls -d ~/.claude/plugins/cache/senya-plugins/yougile-tracking/*/skills/yougile-tracking/scripts/yg.py | tail -1)
python3 "$YG" users_me '{}'
python3 "$YG" projects_list '{}'
python3 "$YG" tasks_list '{"all":true}'
python3 "$YG" tasks_create '{"title":"Починить форму входа","columnId":"<id-колонки>"}'
```

Аргументы передаются одним объектом JSON, `-` вместо него читает их из stdin.
`--list` печатает имена всех 70 инструментов, `"all": true` в списочном вызове
сам пролистает все страницы.

## Что где лежит

```
yougile-tracking/
├── .claude-plugin/
│   ├── marketplace.json         каталог маркетплейса
│   └── plugin.json              манифест плагина
└── skills/yougile-tracking/
    ├── SKILL.md                 инструкция для агента: команды, порядок работы, разметка
    ├── scripts/yg.py            клиент, он же CLI
    ├── references/api.md        справочник API: поля, цвета, пагинация, вебхуки
    ├── assets/                  скелет описания задачи, копируется в description
    └── evals/evals.json         сценарии для проверки скилла
```

## Особенности API, учтённые в клиенте

Булевы значения в query обязаны быть строчными. На `True` с большой буквы сервер
отвечает `200`, а фильтр молча игнорирует: `includeDeleted=True` возвращает
меньше задач, чем `true`, и ничто в ответе на это не указывает. Query собирается
через `urllib.parse.urlencode` с приведением булевых к нижнему регистру.

Списки отдаются страницами: по умолчанию 50 строк, максимум 1000, а
`paging.count` это размер страницы, а не общее число объектов. Флаг `"all": true`
пролистывает всё сам.

Удаления через DELETE у задач, досок, проектов и колонок нет: удаление это
обновление с `"deleted": true`, а обратно такие объекты показываются только при
`includeDeleted: true`.

Повтор запроса при 429 и пятисотых не применяется к `POST` без
`idempotencyKey`, иначе оборвавшееся создание завело бы дубль.

Нехватку прав YouGile показывает не через `403`, а через `400` с общим текстом:
на аккаунте без прав администратора так отвечают создание проекта и удаление
стикера.

## Лицензия

BSD 3-Clause, текст в `LICENSE`.
