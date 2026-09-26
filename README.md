# YouGile для Claude Code

Плагин Claude Code для работы с трекером [YouGile](https://yougile.com) через REST API v2: проекты, доски, колонки, задачи, сотрудники, отделы, роли, чаты, стикеры, вебхуки, загрузка файлов и контакты CRM. 70 инструментов: все 69 операций спецификации и `setup`.

## Требования

Python 3.9 или новее, только стандартная библиотека.

## Установка

```
/plugin marketplace add boundlessend/yougile-tracking
/plugin install yougile-tracking@senya-plugins
```

Путь к клиенту в терминале:

```bash
YG=$(ls -d ~/.claude/plugins/cache/senya-plugins/yougile-tracking/*/skills/yougile-tracking/scripts/yg.py | tail -1)
```

## Ключ API

Ключ получают один раз, в своём терминале: команда спросит почту и пароль от YouGile, а если компаний несколько, то и номер компании. Пароль читается скрытым вводом, поэтому через агента команду не запустить.

```bash
python3 "$YG" setup
```

На macOS ключ сохраняется в связку ключей под именем `yougile-api-key`. На других системах `setup` печатает ключ, его кладут в переменную `YOUGILE_API_KEY`. Переменная проверяется первой на любой системе.

Каждый запуск `setup` создаёт на сервере новый ключ, прежние остаются действующими. На аккаунт положено не больше 30 ключей: лишние видны через `auth_list_keys` и снимаются через `auth_delete_key`.

Проверка установки без сети: `python3 "$YG" --selfcheck`.

## Как пользоваться

Скилл срабатывает сам, когда речь заходит о задачах в YouGile. Вручную:

```bash
python3 "$YG" users_me '{}'
python3 "$YG" tasks_list '{"all":true}'
python3 "$YG" tasks_create '{"title":"Починить форму входа","columnId":"<id-колонки>"}'
```

Аргументы передаются одним объектом JSON, `-` вместо него читает их из stdin. `--list` печатает имена всех инструментов, `"all": true` в списочном вызове пролистывает все страницы.

## Обновление

```bash
claude plugin marketplace update senya-plugins
claude plugin update yougile-tracking@senya-plugins
```

После обновления перезапустите Claude Code.

## Лицензия

BSD 3-Clause, текст в `LICENSE`.
