# Справочник YouGile API v2

Базовый адрес: `https://yougile.com/api-v2`. Авторизация: `Authorization: Bearer <ключ>`.
Сверено с официальной спецификацией OpenAPI (YouGile REST API v2.0), все 69
операций доступны через `scripts/yg.py`.

Правила разметки описаний задач лежат в `SKILL.md`, здесь их нет.

## Содержание

- Пагинация: сколько строк приходит и как листать
- Удаление объектов через `deleted: true`
- Поля задачи, стикеры на задаче, идемпотентность
- Цвета колонок (число 1-16)
- Стикеры: текстовые и спринтовые, состояния
- Вебхуки: события и фильтры
- Ограничения, коды ответов, повторы запросов
- Устройство данных: компания, проект, доска, колонка, задача
- Полный список инструментов с эндпоинтами
- Где хранится ключ
- Проверка скилла

## Пагинация: читать до того, как запрашивать списки

Любой список выдаётся страницами. `limit` по умолчанию **50**, максимум
**1000**, `offset` начинается с нуля. Строки приходят обёрнутыми:

```json
{"paging": {"count": 50, "limit": 50, "offset": 0, "next": true}, "content": [ ... ]}
```

`next: true` означает, что есть ещё. `count` это размер полученной страницы, а
не общее число объектов, поэтому по нему нельзя понять, сколько осталось. Доска
с тремя сотнями задач по умолчанию отдаст 50, так что страницы надо листать:

```bash
$YG tasks_list '{"columnId":"<id>","all":true}'      # клиент пролистает сам
$YG tasks_list '{"columnId":"<id>","limit":1000,"offset":1000}'   # вручную
```

Флаг `"all": true` работает только со списками: клиент запрашивает страницы по
1000 строк, пока `paging.next` не станет `false`, и возвращает всё одним
массивом.

## Удаление объектов

Эндпоинтов DELETE для проектов, досок, колонок, задач, стикеров и вебхуков не
существует. Удаление это обновление:

```bash
$YG tasks_update '{"id":"<id>","deleted":true}'
```

Удалённые объекты пропадают из списков, пока в запросе нет `includeDeleted: true`.
Вернуть объект можно, записав `deleted: false`. Настоящий DELETE есть только у
сотрудников (`users_delete`), ролей проекта (`roles_delete`) и ключей API
(`auth_delete_key`).

Чтобы вынуть задачу из колонки, не удаляя её, передайте `columnId: "-"`.

## Поля задачи

`tasks_create` и `tasks_update` передают тело целиком, поэтому все поля ниже
работают без правок клиента.

| Поле | Тип | Примечание |
|------|-----|------------|
| `title` | строка | обязательное при создании |
| `columnId` | строка | `"-"` вынимает задачу из колонки |
| `description` | строка | HTML, правила в `SKILL.md` |
| `assigned` | массив id | свой id берётся из `users_me` |
| `subtasks` | массив id задач | появляются отдельными карточками на доске |
| `completed`, `archived`, `deleted` | булево | |
| `color` | строка из списка | цвет карточки, перечень ниже |
| `checklists` | массив | при записи заменяет все чеклисты целиком |
| `stickers` | объект | см. ниже |
| `deadline` | объект | `{"deadline": 1653029146646, "startDate": 1653028146646, "withTime": true}` |
| `timeTracking` | объект | `{"plan": 5, "work": 3}`, часы |
| `timer` | объект | `{"running": true, "seconds": 600}` |
| `stopwatch` | объект | `{"running": true}` |
| `idempotencyKey` | строка | см. ниже |
| `deal`, `extensionData` | объект | сделка CRM, данные расширения |

Время везде в миллисекундах Unix.

Цвета карточки: `task-primary`, `task-gray`, `task-red`, `task-pink`,
`task-yellow`, `task-green`, `task-turquoise`, `task-blue`, `task-violet`.

Чеклисты записываются целиком: массив, который вы отправили, заменяет прежний.
Чтобы добавить один пункт, сначала прочитайте задачу, дополните массив и
запишите его полностью.

### Объект `stickers`

Ключ это id стикера, значение это состояние:

```json
{"stickers": {"id-стикера": "id-состояния"}}
```

- `"-"` открепляет стикер от задачи.
- `"empty"` прикрепляет стикер без состояния.
- Стикеры-строки принимают любой текст: `"ООО «Производство»"`.
- Числовые стикеры принимают строку с числом, дробная часть через точку: `"345.123"`.

### Идемпотентность

`tasks_create`, `projects_create`, `boards_create` и `columns_create` принимают
`idempotencyKey`. Повторный вызов с тем же ключом вернёт созданный в первый раз
объект вместо дубля. Стоит задавать везде, где возможен повтор запроса.

## Цвета колонок

Цвет колонки это **число от 1 до 16**, а не строка (у задач наоборот, строка,
перепутать легко):

| № | Цвет | № | Цвет | № | Цвет | № | Цвет |
|---|------|---|------|---|------|---|------|
| 1 | `#7B869E` | 5 | `#7CAE5E` | 9 | `#667085` | 13 | `#5CDC11` |
| 2 | `#FF8C8C` | 6 | `#49C5BC` | 10 | `#EB3737` | 14 | `#08A7A9` |
| 3 | `#E9A24F` | 7 | `#8CACFF` | 11 | `#F2732B` | 15 | `#5089F2` |
| 4 | `#FCE258` | 8 | `#CC8CFF` | 12 | `#F5CC00` | 16 | `#E25EF2` |

## Стикеры

Стикеры принадлежат компании, а не доске. Созданный через `stickers_create`
стикер доступен всей компании, но на доске появится только после того, как доска
перечислит его в своём поле `stickers`:

```bash
$YG stickers_create '{"name":"Приоритет","states":[{"name":"Высокий","color":"#EB3737"}]}'
$YG boards_update '{"id":"<id-доски>","stickers":{"<id-стикера>":true}}'
```

Семейств стикеров два, и это разные эндпоинты: текстовые (`stickers_*`, обычные
метки и свободные поля) и спринтовые (`sprint_stickers_*`, у состояний есть
`begin` и `end`).

Состояния заводятся по одному: `sticker_states_create`, `sticker_states_get`,
`sticker_states_update`, и такая же тройка `sprint_states_*`.

## Вебхуки

Поле `event` имеет вид `<объект>-<действие>` и принимает регулярное выражение
JavaScript.

- Объекты: `project`, `board`, `column`, `task`, `sticker`, `department`, `group_chat`, `chat_message`.
- Действия: `created`, `deleted`, `restored`, `moved`, `renamed`, `updated`. Для `user`: `added`, `removed`.
- `task-*` ловит все события задач, `.*` ловит вообще всё.
- Только события компании: личные чаты вебхук не вызывают.

`filters` это массив объектов `{"name": ..., "value": ...}`:

| Фильтр | Значение |
|--------|----------|
| `location` | id проекта, доски или колонки, либо массив таких id |
| `title` | регулярное выражение для заголовка объекта |
| `chat_message` | регулярное выражение для текста сообщения |

```bash
$YG webhooks_create '{"url":"https://example.com/hook","event":"task-*","filters":[{"name":"location","value":["<id-доски>"]}]}'
```

Вебхук выключается так же, как удаляется всё остальное: `webhooks_update` с
`deleted: true`.

## Ограничения и ошибки

- **Частота:** 50 запросов в минуту на компанию.
- **Ключи:** не больше 30 на аккаунт (именно на аккаунт, а не на компанию).
- **Срок жизни ключа:** не ограничен, действует до удаления.
- Успех это `200`, при создании `201`. Ошибка возвращает код `3xx`, `4xx` или
  `5xx` и поле `error` с описанием; `yg.py` печатает его в stderr как
  `{"error": "..."}` и выходит с кодом 1. Запросы с кодами 429 и 5xx
  повторяются трижды с растущей паузой, после чего ошибка поднимается. `POST`
  повторяется только с `idempotencyKey` в теле: иначе повтор оборвавшегося
  создания завёл бы дубль. К кодам 400, 401, 403 и 404 клиент добавляет
  подсказку о вероятной причине.
- Ключ работает с правами аккаунта, который его создал. Чего аккаунт не может в
  интерфейсе, того он не может и через API. Нехватку прав сервис показывает не
  через `403`, а через `400` с общим текстом вида «Не удалось создать проект»:
  на аккаунте без прав администратора так отвечают создание проекта и удаление
  стикера, хотя тело запроса при этом верное.
- Задачи нельзя отфильтровать по проекту. Фильтры: `columnId`, `assignedTo`,
  `stickerId`, `stickerStateId`. Зато без фильтров `GET /tasks` отдаёт все
  задачи, видимые ключу, сразу по всем проектам и доскам: для подсчёта это
  единственный надёжный путь. Обход по колонкам занижает результат, потому что
  задачи с `columnId: "-"` не принадлежат ни одной колонке.
- Выдача ограничена правами ключа, а не компанией целиком. Сквозная нумерация
  `idTaskCommon` растёт по всей компании, поэтому по ней видно, что задач в
  компании обычно больше, чем возвращает API конкретному аккаунту.
- Булевы значения в query обязаны быть строчными. На `True` с большой буквы
  сервер отвечает `200` и молча игнорирует фильтр: на живом аккаунте
  `includeDeleted=True` вернул 18 задач там, где `true` возвращает 19.

## Устройство данных

```
Компания
└── Проект            (права доступа задаются здесь)
    └── Доска         (стикеры включаются на уровне доски)
        └── Колонка   (цвет числом 1-16)
            └── Задача
                ├── Чеклисты        (внутри карточки)
                ├── Подзадачи       (отдельные карточки)
                ├── Сообщения чата  (id задачи он же id чата)
                └── Стикеры         (общие для компании, по id)
```

## Инструменты

`python3 "${CLAUDE_PLUGIN_ROOT}/skills/yougile-tracking/scripts/yg.py" <инструмент> '<json>'`. Вместо
JSON можно передать `-`, тогда аргументы читаются из stdin. `--list` печатает
имена, `--selfcheck` прогоняет встроенные проверки.

| Инструмент | Эндпоинт | Что делает |
|------------|----------|------------|
| `setup` | - | Получить ключ API и сохранить в хранилище системы |
| `auth_companies` | `POST /auth/companies` | Список компаний по логину и паролю |
| `auth_create_key` | `POST /auth/keys` | Создать ключ. Нужны login, password, companyId |
| `auth_list_keys` | `POST /auth/keys/get` | Список ключей. Нужны login, password |
| `auth_delete_key` | `DELETE /auth/keys/{key}` | Удалить ключ. Нужен key |
| `company_get` | `GET /companies` | Данные компании, к которой привязан ключ |
| `company_update` | `PUT /companies` | Изменить компанию. Можно title, apiData, deleted |
| `projects_list` | `GET /projects` | Список проектов |
| `projects_get` | `GET /projects/{id}` | Проект по id |
| `projects_create` | `POST /projects` | Создать проект. Нужен title |
| `projects_update` | `PUT /projects/{id}` | Изменить проект |
| `roles_list` | `GET /projects/{projectId}/roles` | Список ролей проекта |
| `roles_get` | `GET /projects/{projectId}/roles/{id}` | Роль по id |
| `roles_create` | `POST /projects/{projectId}/roles` | Создать роль. Нужны projectId, name, permissions |
| `roles_update` | `PUT /projects/{projectId}/roles/{id}` | Изменить роль |
| `roles_delete` | `DELETE /projects/{projectId}/roles/{id}` | Удалить роль |
| `boards_list` | `GET /boards` | Список досок |
| `boards_get` | `GET /boards/{id}` | Доска по id |
| `boards_create` | `POST /boards` | Создать доску. Нужны title, projectId |
| `boards_update` | `PUT /boards/{id}` | Изменить доску |
| `columns_list` | `GET /columns` | Список колонок |
| `columns_get` | `GET /columns/{id}` | Колонка по id |
| `columns_create` | `POST /columns` | Создать колонку. Нужны title, boardId |
| `columns_update` | `PUT /columns/{id}` | Изменить колонку |
| `tasks_list` | `GET /tasks` | Задачи, свежие сверху |
| `tasks_list_chrono` | `GET /task-list` | Задачи в прямом порядке |
| `tasks_get` | `GET /tasks/{id}` | Задача по id |
| `tasks_create` | `POST /tasks` | Создать задачу. Нужен title |
| `tasks_update` | `PUT /tasks/{id}` | Изменить задачу |
| `task_subscribers_get` | `GET /tasks/{id}/chat-subscribers` | Участники чата задачи |
| `task_subscribers_update` | `PUT /tasks/{id}/chat-subscribers` | Заменить участников чата. Нужны id, content |
| `users_list` | `GET /users` | Список сотрудников |
| `users_get` | `GET /users/{id}` | Сотрудник по id |
| `users_me` | `GET /users/me` | Текущий пользователь |
| `users_invite` | `POST /users` | Пригласить в компанию. Нужен email |
| `users_update` | `PUT /users/{id}` | Изменить сотрудника |
| `users_delete` | `DELETE /users/{id}` | Убрать сотрудника из компании |
| `departments_list` | `GET /departments` | Список отделов |
| `departments_get` | `GET /departments/{id}` | Отдел по id |
| `departments_create` | `POST /departments` | Создать отдел. Нужен title |
| `departments_update` | `PUT /departments/{id}` | Изменить отдел |
| `chat_messages` | `GET /chats/{chatId}/messages` | История чата. Нужен chatId |
| `chat_send` | `POST /chats/{chatId}/messages` | Написать в чат. Нужны chatId, text, textHtml, label |
| `chat_message_get` | `GET /chats/{chatId}/messages/{id}` | Сообщение по id |
| `chat_message_update` | `PUT /chats/{chatId}/messages/{id}` | Изменить сообщение. Можно label, react, deleted |
| `chat_typing` | `POST /chats/{chatId}/typing` | Показать, что пользователь печатает |
| `group_chats_list` | `GET /group-chats` | Список групповых чатов |
| `group_chats_get` | `GET /group-chats/{id}` | Групповой чат по id |
| `group_chats_create` | `POST /group-chats` | Создать групповой чат |
| `group_chats_update` | `PUT /group-chats/{id}` | Изменить групповой чат |
| `stickers_list` | `GET /string-stickers` | Список текстовых стикеров |
| `stickers_get` | `GET /string-stickers/{id}` | Стикер по id |
| `stickers_create` | `POST /string-stickers` | Создать стикер. Нужен name |
| `stickers_update` | `PUT /string-stickers/{id}` | Изменить стикер |
| `sticker_states_create` | `POST /string-stickers/{stickerId}/states` | Добавить состояние. Нужны stickerId, name |
| `sticker_states_get` | `GET /string-stickers/{stickerId}/states/{stateId}` | Состояние по id |
| `sticker_states_update` | `PUT /string-stickers/{stickerId}/states/{stateId}` | Изменить состояние |
| `sprint_stickers_list` | `GET /sprint-stickers` | Список спринтовых стикеров |
| `sprint_stickers_get` | `GET /sprint-stickers/{id}` | Спринтовый стикер по id |
| `sprint_stickers_create` | `POST /sprint-stickers` | Создать спринтовый стикер. Нужен name |
| `sprint_stickers_update` | `PUT /sprint-stickers/{id}` | Изменить спринтовый стикер |
| `sprint_states_create` | `POST /sprint-stickers/{stickerId}/states` | Добавить спринт. Нужны stickerId, name |
| `sprint_states_get` | `GET /sprint-stickers/{stickerId}/states/{stateId}` | Спринт по id |
| `sprint_states_update` | `PUT /sprint-stickers/{stickerId}/states/{stateId}` | Изменить спринт |
| `webhooks_list` | `GET /webhooks` | Список подписок |
| `webhooks_create` | `POST /webhooks` | Подписаться. Нужны url, event, filters |
| `webhooks_update` | `PUT /webhooks/{id}` | Изменить подписку |
| `crm_contact_create` | `POST /crm/contact-persons` | Создать контактное лицо. Нужны projectId, title |
| `crm_contact_find` | `GET /crm/contacts/by-external-id` | Найти контакт по внешнему id. Нужны provider, chatId |
| `upload_file` | `POST /upload-file` | Загрузить файл, возвращает его адрес. Нужен `path` |

## Где хранится ключ

Порядок поиска: переменная окружения `YOUGILE_API_KEY`, затем связка ключей
macOS, затем диспетчер учётных данных Windows. Имя записи везде
`yougile-api-key`.

```bash
# macOS: ключ спрашивается отдельно и не попадает в историю команд
security add-generic-password -a "$USER" -s yougile-api-key -w
```

`yg.py setup` делает это сам, но ему нужен настоящий терминал: пароль читается
скрытым вводом.

## Проверка скилла

`scripts/yg.py --selfcheck` прогоняет утверждения о сборке запроса: приведение
булевых, разбор шаблона пути, отделение фильтров от тела, проверку обязательных
полей. Сеть при этом не нужна.

`evals/evals.json` описывает четыре сценария для проверки скилла целиком:
создание задачи по названию доски, полная выгрузка списка, удаление задачи,
описание задачи разметкой. Формат совпадает с тем, что ожидает официальный
skill-creator: у каждого сценария есть запрос, ожидаемый результат и набор
проверяемых утверждений.
