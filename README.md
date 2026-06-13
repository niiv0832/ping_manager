# Ping Manager

Ping Manager - легкий веб-сервис для Raspberry Pi или другого Linux-хоста, который проверяет доступность IP-адресов через `ping`, принимает обратные webhook heartbeat от устройств и отправляет уведомления в Telegram только при изменении состояния.

Проект вырос из простого cron-скрипта в постоянный Flask-сервис с WebUI, JSON-конфигурацией, systemd-автозапуском и поддержкой SOCKS5-прокси для Telegram.

## Возможности

- WebUI для добавления, редактирования и удаления IP-адресов.
- WebUI для добавления устройств с обратной webhook-проверкой.
- Двуязычный WebUI: English / Русский, английский язык включен по умолчанию.
- Индивидуальный интервал проверки для каждого IP.
- Индивидуальный webhook URL и token для каждого устройства.
- Автоматическая генерация команд установки heartbeat для Linux, macOS, Windows и RouterOS.
- Экспериментальные инструкции для Keenetic через Entware/cron и UniFi через SSH/cron.
- Ручной запуск проверки для любого IP из WebUI.
- Индивидуальный текст Telegram-сообщений для восстановления и падения.
- Отправка уведомлений только при смене статуса, без спама на каждой проверке.
- Отображение текущего статуса и времени последнего изменения.
- Хранение настроек в JSON-файле.
- Глобальные настройки SOCKS5-прокси для Telegram.
- Ручная проверка SOCKS5-прокси через Telegram API.
- Автозапуск через systemd.

## Состав проекта

```text
ping_manager/
  .env.example              # пример файла с Telegram-переменными
  app.py                    # Flask-приложение, ping worker, Telegram-уведомления
  templates/
    index.html              # WebUI
etc/
  systemd/
    system/
      ping-ui.service       # systemd unit для запуска сервиса
CHANGELOG.md               # история изменений
HISTORY.md                 # исходная история разработки и ручные инструкции
README.md                  # актуальная документация
```

## Архитектурная концепция

Приложение состоит из четырех основных частей:

1. `Flask WebUI` - принимает действия пользователя: открыть панель, переключить язык, добавить IP, редактировать IP, управлять webhook-устройствами, сохранить настройки прокси и webhook base URL.
2. `Webhook endpoint` - принимает `GET` или `POST` запросы на персональные URL вида `/webhook/<token>` и обновляет состояние устройства.
3. `JSON config v2` - хранит ping-хосты, webhook-устройства, интервалы, token, последние состояния, настройки прокси, webhook base URL и язык интерфейса.
4. `Background workers` - ping worker проверяет IP по интервалам, webhook worker переводит устройства в offline при просроченном heartbeat.

```mermaid
flowchart LR
    U["Пользователь"] --> W["WebUI Flask :5001"]
    W --> C["/root/ping_manager/config.json"]
    P["Background ping worker"] --> C
    R["Webhook worker"] --> C
    P --> H["ping IP-адресов"]
    D["Устройства"] --> E["/webhook/<token>"]
    E --> C
    P --> T["Telegram Bot API"]
    R --> T
    C --> P
    C --> R
    W --> B["Браузер в локальной сети"]
    S["systemd ping-ui.service"] --> W
    S --> P
```

Ключевой принцип: сервис работает постоянно. Для ping-проверок cron больше не нужен, интервалы реализованы через `last_check`. Для webhook-проверок cron/systemd/launchd/Task Scheduler запускаются на самих устройствах и регулярно дергают персональную ссылку.

## Как работает состояние

Начиная с v2 `config.json` имеет версионированную структуру:

```json
{
    "_schema_version": 2,
    "_settings": {
        "proxy_enabled": false,
        "proxy_ip": "",
        "proxy_port": "1080",
        "language": "en",
        "webhook_base_url": "",
        "trust_proxy_headers": false
    },
    "ping_hosts": {},
    "webhook_devices": {}
}
```

При первом старте v2 старый плоский конфиг автоматически мигрирует: все старые IP-ключи переносятся в `ping_hosts`, настройки из `_settings` сохраняются.

Для каждого IP в `ping_hosts` хранится:

```json
{
    "interval": 60,
    "msg_up": "Host is available",
    "msg_down": "Host access lost",
    "last_state": "unknown",
    "status_time": "",
    "last_check": 0
}
```

Для каждого устройства в `webhook_devices` хранится:

```json
{
    "device_id": "generated-id",
    "name": "NAS",
    "location": "Rack",
    "device_type": "linux",
    "interval_seconds": 60,
    "missed_heartbeats": 2,
    "token": "secret-token",
    "last_state": "pending",
    "last_seen": 0,
    "status_time": "",
    "last_ip": "",
    "last_user_agent": ""
}
```

Поддерживаемые значения языка:

- `en` - English, используется по умолчанию.
- `ru` - Русский.

Логика уведомлений:

- `unknown -> up` или `unknown -> down`: отправляется стандартное сообщение текущего состояния.
- `up -> down`: отправляется `msg_down`.
- `down -> up`: отправляется `msg_up`.
- `up -> up` или `down -> down`: уведомление не отправляется.

Так сервис не спамит в Telegram при каждом цикле проверки.

Ручная проверка IP всегда отправляет Telegram-сообщение с текущим состоянием, даже если статус не изменился. К стандартному тексту добавляется префикс `Ручная проверка: `.

Логика webhook-устройств:

- новое устройство стартует в статусе `pending`, offline-уведомления до первого heartbeat не отправляются;
- первый heartbeat переводит устройство в `online` и отправляет Telegram-сообщение;
- повторные heartbeat в состоянии `online` только обновляют `last_seen`, `last_ip` и `last_user_agent`;
- если heartbeat не приходит дольше `interval_seconds * missed_heartbeats`, webhook worker переводит устройство в `offline` и отправляет Telegram-сообщение;
- восстановление `offline -> online` снова отправляет Telegram-сообщение.

## Требования

- Linux-хост, например Raspberry Pi или DietPi.
- Python 3.
- Доступ к команде `ping`.
- Telegram-бот и `chat_id`.
- Доступ к локальной сети для открытия WebUI.

Пакеты Debian/DietPi/Raspberry Pi OS:

```bash
apt update
apt install python3 python3-flask python3-requests python3-socks iputils-ping -y
```

`python3-socks` нужен для SOCKS5-прокси. Без него прямая отправка Telegram будет работать, но отправка через SOCKS5 невозможна.

## Подготовка Telegram

1. Откройте в Telegram `@BotFather`.
2. Создайте бота командой `/newbot`.
3. Скопируйте API token вида `123456789:ABCdefGh...`.
4. Откройте созданного бота и нажмите `Start`.
5. Узнайте свой `chat_id`, например через `@userinfobot`.

В текущей версии token и `chat_id` задаются в файле `/root/ping_manager/.env`:

```bash
TOKEN=ВАШ_ТОКЕН_БОТА
CHAT_ID=ВАШ_CHAT_ID
```

Рекомендуемый формат - без кавычек. Двойные кавычки также допустимы:

```bash
TOKEN="ВАШ_ТОКЕН_БОТА"
CHAT_ID="ВАШ_CHAT_ID"
```

Одинарные кавычки приложение тоже умеет читать, но для совместимости с systemd лучше использовать значения без кавычек или в двойных кавычках. Не добавляйте префикс `bot` перед токеном.

## Установка с нуля

Команды ниже рассчитаны на установку под `root`, как в DietPi.

### 1. Установить зависимости

```bash
apt update
apt install python3 python3-flask python3-requests python3-socks iputils-ping -y
```

### 2. Создать каталог приложения

```bash
mkdir -p /root/ping_manager/templates
```

### 3. Скопировать файлы проекта

Скопируйте файлы из репозитория на Raspberry Pi:

```bash
cp ping_manager/app.py /root/ping_manager/app.py
cp ping_manager/.env.example /root/ping_manager/.env
cp ping_manager/templates/index.html /root/ping_manager/templates/index.html
cp etc/systemd/system/ping-ui.service /etc/systemd/system/ping-ui.service
```

Если файлы копируются с другой машины, используйте `scp`:

```bash
scp ping_manager/app.py root@RASPBERRY_PI_IP:/root/ping_manager/app.py
scp ping_manager/.env.example root@RASPBERRY_PI_IP:/root/ping_manager/.env
scp ping_manager/templates/index.html root@RASPBERRY_PI_IP:/root/ping_manager/templates/index.html
scp etc/systemd/system/ping-ui.service root@RASPBERRY_PI_IP:/etc/systemd/system/ping-ui.service
```

### 4. Указать Telegram token и chat_id

Откройте файл переменных:

```bash
nano /root/ping_manager/.env
```

Замените значения:

```bash
TOKEN=ВАШ_ТОКЕН_БОТА
CHAT_ID=ВАШ_CHAT_ID
```

Кавычки обычно не нужны. Если хотите использовать кавычки, используйте двойные:

```bash
TOKEN="ВАШ_ТОКЕН_БОТА"
CHAT_ID="ВАШ_CHAT_ID"
```

Файл `/root/ping_manager/.env` читает само приложение. Unit-файл systemd также подключает его через `EnvironmentFile`, чтобы переменные были видны процессу сервиса.

### 5. Проверить синтаксис

```bash
python3 -m py_compile /root/ping_manager/app.py
```

Если команда ничего не вывела, синтаксис корректный.

### 6. Включить и запустить systemd-сервис

```bash
systemctl daemon-reload
systemctl enable ping-ui.service
systemctl start ping-ui.service
```

### 7. Проверить статус

```bash
systemctl status ping-ui.service
```

Ожидаемое состояние:

```text
active (running)
```

### 8. Открыть WebUI

Узнайте IP Raspberry Pi:

```bash
hostname -I
```

Откройте в браузере:

```text
http://RASPBERRY_PI_IP:5001
```

Актуальный порт в `app.py` - `5001`.

## Настройка хостов

В WebUI можно:

- добавить IP-адрес;
- редактировать IP-адрес, интервал проверки и тексты уведомлений;
- задать интервал проверки в секундах;
- задать текст сообщения при восстановлении;
- задать текст сообщения при падении;
- вручную запустить проверку конкретного IP кнопкой `Проверить`;
- удалить хост из мониторинга.

После добавления хоста первая автоматическая проверка фиксирует состояние и сразу отправляет Telegram-сообщение с текстом `msg_up` или `msg_down`.

Кнопка `Проверить` запускает ping немедленно, обновляет `last_check`, фиксирует новый статус и показывает результат в верхней части страницы. Telegram-сообщение отправляется всегда, даже если статус не изменился. Текст строится из стандартного сообщения текущего состояния с добавлением префикса `Ручная проверка: `.

Кнопка `Редактировать` открывает форму с текущими значениями хоста. При сохранении можно изменить IP, интервал и тексты уведомлений. Текущее состояние, время последнего изменения и время последней проверки сохраняются. Если IP изменен, запись переносится на новый адрес.

## Обратная webhook-проверка устройств

Webhook-проверка нужна для устройств, которые сами должны подтверждать, что они живы. В WebUI добавьте устройство в блоке `Webhook-устройства`:

- `Название устройства` - понятное имя, например `NAS`, `Router`, `Core Switch`.
- `Место расположения` - ручной ввод; ранее введенные места доступны в выпадающей подсказке.
- `Тип` - `linux`, `macos`, `windows`, `routeros`, `keenetic`, `unifi_ap`, `unifi_switch`.
- `Интервал heartbeat` - как часто устройство должно дергать ссылку.
- `Пропусков до offline` - сколько интервалов можно пропустить до статуса `offline`.

Перед добавлением устройств заполните `Webhook base URL` в верхнем блоке настроек. Это адрес Ping Manager, доступный с самих устройств, например:

```text
http://192.168.1.10:5001
http://raspberrypi.local:5001
https://monitor.example.com
```

После добавления устройства WebUI сразу показывает персональный `Webhook URL` и готовые команды установки. Эту же инструкцию можно открыть позже кнопкой `Инструкция` в таблице устройств.

Поддержанные профили:

- `Linux` - systemd `.service` + `.timer`, команда использует `curl -fsS --max-time 10`.
- `macOS` - LaunchAgent в `~/Library/LaunchAgents` с `StartInterval`.
- `Windows` - Task Scheduler через `schtasks`; интервал должен быть не меньше 60 секунд и кратен 60.
- `RouterOS` - `/tool fetch` через `/system script` и `/system scheduler`.

Экспериментальные профили:

- `Keenetic` - Entware/OPKG + cron + curl. Работает только если Entware установлен и поддерживается вашей прошивкой.
- `UniFi WiFi/AP` и `UniFi Switch` - SSH/cron профиль. Постоянство cron-задач зависит от модели, прошивки и обновлений UniFi; если задача не переживает обновления, используйте ping-проверку или внешний Linux-host как агент.

Token встроен в URL и генерируется отдельно для каждого устройства. Если token скомпрометирован, нажмите `Сменить token` и заново примените инструкцию на устройстве.

## Переключение языка

В верхней части WebUI есть переключатель `Language` / `Язык`.

Доступные языки:

- `English` - выбран по умолчанию для новых установок.
- `Русский` - русская локализация интерфейса.

Выбранный язык сохраняется в `/root/ping_manager/config.json` в поле `_settings.language` и применяется после переключения без перезапуска сервиса.

Переводится интерфейс и системные сообщения WebUI. Пользовательские тексты уведомлений `msg_up` и `msg_down` не переводятся автоматически, потому что это ваши собственные тексты Telegram-сообщений.

## Настройка SOCKS5-прокси

В верхнем блоке WebUI доступны:

- IP прокси;
- порт прокси;
- флажок включения прокси.
- кнопка `Проверить прокси через Telegram`.

После сохранения настройки применяются без перезапуска сервиса, потому что `send_telegram()` читает конфиг перед каждой отправкой.

Для SOCKS5 используется схема `socks5h://`, поэтому DNS-запросы к Telegram тоже идут через прокси.

Если прокси включен, но недоступен или в системе нет поддержки SOCKS, сервис пишет ошибку в лог и пробует отправить сообщение напрямую.

Кнопка проверки прокси делает запрос к Telegram Bot API `getMe` строго через указанные IP и порт SOCKS5-прокси. Проверку можно запускать даже до включения флажка `Включить прокси`, чтобы сначала убедиться, что адрес работает. Для проверки нужен `TOKEN` в `/root/ping_manager/.env`; `CHAT_ID` для этой операции не используется.

## Обновление установленной версии

### 1. Сделать резервную копию конфига

```bash
cp /root/ping_manager/config.json /root/ping_manager/config.json.bak
```

`config.json` содержит ваши хосты, webhook-устройства, интервалы, статусы и настройки прокси. При обновлении его обычно не нужно заменять.

При первом запуске v2 старый формат конфига автоматически переносится в schema v2:

- старые IP-записи становятся элементами `ping_hosts`;
- `_settings.language`, настройки SOCKS5-прокси и пользовательские тексты сохраняются;
- новые поля `webhook_base_url`, `trust_proxy_headers` и `webhook_devices` добавляются автоматически.

### 2. Остановить сервис

```bash
systemctl stop ping-ui.service
```

### 3. Скопировать новые файлы приложения

```bash
cp ping_manager/app.py /root/ping_manager/app.py
cp ping_manager/templates/index.html /root/ping_manager/templates/index.html
```

Если изменился unit-файл:

```bash
cp etc/systemd/system/ping-ui.service /etc/systemd/system/ping-ui.service
systemctl daemon-reload
```

### 4. Проверить Telegram token и chat_id

Telegram-настройки хранятся отдельно от кода, поэтому при обычном обновлении `app.py` их переносить не нужно. Проверьте файл:

```bash
nano /root/ping_manager/.env
```

Формат:

```bash
TOKEN=ВАШ_ТОКЕН_БОТА
CHAT_ID=ВАШ_CHAT_ID
```

### 5. Проверить синтаксис

```bash
python3 -m py_compile /root/ping_manager/app.py
```

### 6. Запустить сервис

```bash
systemctl start ping-ui.service
systemctl status ping-ui.service
```

Если systemd заблокировал частые перезапуски после ошибок:

```bash
systemctl reset-failed ping-ui.service
systemctl restart ping-ui.service
```

## Диагностика

### Сервис не запускается

Проверьте статус:

```bash
systemctl status ping-ui.service
```

Посмотрите последние логи:

```bash
journalctl -u ping-ui.service -n 50 --no-pager
```

Частые причины:

- синтаксическая ошибка в `app.py`;
- не создан или неверно заполнен `/root/ping_manager/.env`;
- не установлен `python3-flask`;
- неправильный путь в `/etc/systemd/system/ping-ui.service`.

### WebUI не открывается

Проверьте, слушает ли сервис порт:

```bash
ss -tulpn | grep 5001
```

Проверьте IP устройства:

```bash
hostname -I
```

Откройте:

```text
http://RASPBERRY_PI_IP:5001
```

### Telegram не отправляет сообщения

Проверьте:

- бот был запущен пользователем через `Start`;
- `TOKEN` в `/root/ping_manager/.env` указан без префикса `bot`;
- `CHAT_ID` в `/root/ping_manager/.env` указан правильно;
- устройство имеет доступ к `api.telegram.org`;
- при включенном SOCKS5 установлен пакет `python3-socks`;
- если прокси включен, IP и порт прокси доступны с Raspberry Pi.

Логи отправки:

```bash
journalctl -u ping-ui.service -n 100 --no-pager
```

### Проверка прокси из WebUI падает

Проверьте:

- IP и порт прокси указаны корректно;
- пакет `python3-socks` установлен;
- Telegram `TOKEN` задан в `/root/ping_manager/.env`;
- Raspberry Pi может подключиться к SOCKS5-прокси по указанному адресу.

Команда для установки поддержки SOCKS5:

```bash
apt install python3-socks -y
```

## Автотесты

В проект добавлен набор `pytest`-тестов для проверки конфигурации, локализации, Telegram-отправки, SOCKS5-прокси и основных Flask routes.

Локальный запуск:

```bash
python3 -m pip install -r requirements-dev.txt
python3 -m pytest -q
```

Автоматический запуск настроен в GitHub Actions: `.github/workflows/tests.yml`.

Workflow запускается при:

- push в ветку `main`;
- pull request.

## Удаление старого cron

Ранняя версия проекта запускалась через cron. Актуальная версия работает постоянно через systemd, поэтому cron-запись для старого `ping_check.py` нужно удалить.

```bash
crontab -e
```

Удалите строку вида:

```text
* * * * * /usr/bin/python3 /root/ping_check.py
```

## Безопасность и ограничения

- WebUI не имеет авторизации. Используйте его только в доверенной локальной сети или закройте доступ firewall-ом.
- Webhook URL содержит секретный token. Не публикуйте ссылки из инструкций и меняйте token кнопкой `Сменить token`, если ссылка могла попасть посторонним.
- Если Ping Manager работает за reverse proxy, включайте `Доверять X-Forwarded-For` только для доверенного proxy. Иначе IP устройства берется из прямого подключения.
- Telegram token хранится в `/root/ping_manager/.env`. Не публикуйте этот файл с реальным token.
- `config.json` создается автоматически в `/root/ping_manager/config.json`.
- Tailwind CSS подключается с CDN в HTML-шаблоне, поэтому для красивого оформления браузеру нужен доступ к интернету. Базовая HTML-страница при этом остается доступной.

## Быстрая шпаргалка

Перезапуск:

```bash
systemctl restart ping-ui.service
```

Статус:

```bash
systemctl status ping-ui.service
```

Логи:

```bash
journalctl -u ping-ui.service -n 100 --no-pager
```

Адрес WebUI:

```text
http://RASPBERRY_PI_IP:5001
```
