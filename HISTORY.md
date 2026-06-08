Отличная задача! Для Raspberry Pi идеально подойдет скрипт на **Python**. Он легкий, надежный, и для него есть отличная библиотека для работы с Telegram.

Ниже представлена подробная пошаговая инструкция: от создания бота до настройки автозапуска скрипта каждую минуту.

---

## Шаг 1. Создаем Telegram-бота и получаем ID

Если у вас уже есть бот и ваш `chat_id`, можете пропустить этот шаг.

1. Найдите в Telegram бота **@BotFather** и запустите его.
2. Отправьте команду `/newbot`. Введите имя бота, а затем юзернейм (например, `VislayaPingBot`).
3. Скопируйте полученный **API Token** (строка вида `123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ`).
4. Теперь найдите своего созданного бота в поиске Telegram и нажмите **Старт** (это обязательно, чтобы бот мог писать вам).
5. Чтобы узнать свой личный `chat_id`, найдите бота **@userinfobot** и перешлите ему любое сообщение. Он вернет вам число (например, `987654321`).

---

## Шаг 2. Подготовка Raspberry Pi

Подключитесь к вашей Raspberry Pi по SSH и установите необходимые компоненты.

1. Обновите список пакетов и установите Python (обычно он уже есть):
```bash
sudo apt update
sudo apt install python3 python3-pip -y

```


2. Установите библиотеку для работы с Telegram API:
```bash
pip3 install requests

```



---

## Шаг 3. Создание скрипта

Чтобы скрипт понимал, изменился ли статус (был доступен -> стал недоступен), ему нужно где-то хранить предыдущее состояние. Самый простой и надежный способ для работы по cron (раз в минуту) — записывать текущий статус во временный файл.

1. Создайте файл скрипта:
```bash
nano ~/ping_check.py

```


2. Вставьте в него следующий код (обязательно подставьте свои **TOKEN** и **CHAT_ID**):

```python
import os
import subprocess
import requests

# --- НАСТРОЙКИ ---
IP_TO_PING = "192.168.30.1"
TOKEN = "ВАШ_ТОКЕН_БОТА"
CHAT_ID = "ВАШ_CHAT_ID"
STATUS_FILE = "/tmp/ping_vislaya_status.txt"  # Файл для хранения предыдущего состояния


def send_telegram(text):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Ошибка отправки в Telegram: {e}")


def check_ping(ip):
    # Отправляем 2 пакета ping с таймаутом в 2 секунды
    res = subprocess.run(
        ["ping", "-c", "2", "-W", "2", ip],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return res.returncode == 0


def get_last_status():
    # Если файла нет, считаем, что прошлое состояние было "доступен" (True),
    # чтобы не спамить при первом запуске, если всё ок.
    if not os.path.exists(STATUS_FILE):
        return "up"
    with open(STATUS_FILE, "r") as f:
        return f.read().strip()


def save_status(status):
    with open(STATUS_FILE, "w") as f:
        f.write(status)


def main():
    current_is_up = check_ping(IP_TO_PING)
    last_status = get_last_status()

    if current_is_up and last_status == "down":
        # Был недоступен, стал доступен
        send_telegram("🟢 Вислая на связи")
        save_status("up")
    elif not current_is_up and last_status == "up":
        # Был доступен, стал недоступен
        send_telegram("🔴 Вислая не доступна")
        save_status("down")
    else:
        # Статус не изменился — ничего не делаем
        pass


if __name__ == "__main__":
    main()

```

3. Сохраните файл (`Ctrl+O`, затем `Enter`) и выйдите из редактора (`Ctrl+X`).

---

## Шаг 4. Проверка работы

Перед тем как ставить скрипт на автоматический повтор, проверьте его вручную.

1. Запустите скрипт:
```bash
python3 ~/ping_check.py

```


*Если IP пингуется, ничего произойти не должно (так как файл статуса создался со значением `up`).*
2. Чтобы сымитировать падение, можно временно изменить IP в скрипте на несуществующий или просто вручную записать в файл статуса `up`, а в самом скрипте выключить сеть. Либо для теста измените в файле `/tmp/ping_vislaya_status.txt` значение на `down` и запустите скрипт снова — вам должно прийти сообщение «🟢 Вислая на связи».

---

## Шаг 5. Настройка запуска раз в минуту (Cron)

Идеальный инструмент для такой задачи на Linux — это планировщик **cron**.

1. Откройте планировщик cron для редактирования:
```bash
crontab -e

```


*(Если предложит выбрать редактор, выбирайте `1` — nano).*
2. Прокрутите в самый низ файла и добавьте следующую строку:
```text
* * * * * /usr/bin/python3 /home/pi/ping_check.py

```


> **Важно:** Если на вашей Raspberry Pi имя пользователя не `pi`, замените `/home/pi/` на ваш актуальный путь (путь можно узнать, введя команду `pwd` в терминале).


3. Сохраните и закройте файл (`Ctrl+O`, `Enter`, `Ctrl+X`).

Теперь каждую минуту Raspberry Pi будет незаметно запускать этот скрипт. Сообщения в Telegram будут приходить **строго один раз** только в момент изменения статуса (когда связь пропала или когда восстановилась).







Всё в порядке, никакой ошибки в работе самой системы нет. Вы столкнулись с двумя стандартными особенностями современных дистрибутивов Linux (в данном случае **DietPi**):

1. **Защита системного Python (PEP 668):** Начиная с Python 3.11+ (а у вас свежий 3.13), Linux запрещает устанавливать пакеты через `pip` глобально, чтобы вы случайно не сломали зависимости самой операционной системы.
2. **Отсутствие пользователя `pi`:** В дистрибутиве DietPi по умолчанию используется пользователь `root` (или `dietpi`), а классического для Raspberry Pi OS пользователя `pi` здесь просто нет.

Поскольку вы уже находитесь под пользователем `root` и настраиваете системный скрипт автоматизации, у вас есть два простых пути решения.

---

### Вариант 1. Самый быстрый (Установить через apt)

Так как библиотека `requests` очень популярна, она уже есть в репозиториях самого дистрибутива. Её можно поставить стандартным установщиком Linux в обход `pip`:

```bash
apt install python3-requests -y

```

После этого библиотека сразу станет доступна для скрипта.

---

### Вариант 2. Использовать флаг `--break-system-packages`

Если не хочется ставить пакет через apt, можно заставить `pip` проигнорировать предупреждение. Для единичной и простой библиотеки вроде `requests` это абсолютно безопасно:

```bash
pip3 install requests --break-system-packages

```

---

## Важное исправление для Шага 5 (Cron)

Так как вы работаете на **DietPi** под пользователем `root`, а пользователя `pi` в системе нет, путь к скрипту и команда в планировщике `crontab -e` будут выглядеть немного иначе.

1. Логично сохранить скрипт в домашнюю папку рута: `/root/ping_check.py`
2. В самом скрипте (внутри кода) строку с файлом статуса лучше не менять, `/tmp/...` отлично подходит.
3. Команда в `crontab -e` должна выглядеть так:
```text
* * * * * /usr/bin/python3 /root/ping_check.py

```





Отличная идея! Переход от простого скрипта к полноценному приложению с панелью управления (WebUI) — это качественный шаг вперед.

Для реализации мы объединим две вещи:

1. **Flask** — легковесный веб-фреймворк для Python, который создаст веб-страницу прямо на вашей Raspberry Pi.
2. **JSON-файл** — база данных в виде текстового файла, где будут храниться настройки для каждого IP.
3. **Фоновый поток (Background Thread)** — часть скрипта, которая будет крутиться в памяти постоянно и проверять каждый IP со своей периодичностью, не мешая веб-интерфейсу. Cron нам больше не понадобится!

---

## Шаг 1. Установка необходимых компонентов

Зайдите на вашу Raspberry Pi под `root` и установите Flask:

```bash
apt install python3-flask -y

```

---

## Шаг 2. Создание структуры проекта

Создадим отдельную папку для нашего мини-сервиса, чтобы файлы не валялись в куче:

```bash
mkdir -p /root/ping_manager/templates
cd /root/ping_manager

```

У нас будет 3 файла:

1. `config.json` — настройки хостов (создастся автоматически).
2. `templates/index.html` — внешний вид нашей веб-панели.
3. `app.py` — сердце нашего приложения (веб-сервер + пинговальщик).

---

## Шаг 3. Создание HTML-шаблона панели управления

Создайте файл для веб-страницы:

```bash
nano /root/ping_manager/templates/index.html

```

Вставьте в него следующий код (здесь используется стильный и современный CSS-фреймворк Tailwind, чтобы панель выглядела аккуратно даже на мобильном телефоне):

```html
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Мониторинг Сети</title>
    <script src="https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4"></script>
</head>
<body class="bg-gray-100 text-gray-800 font-sans">
    <div class="max-w-4xl mx-auto p-4 sm:p-6">
        <header class="mb-8 flex justify-between items-center">
            <h1 class="text-2xl sm:text-3xl font-bold text-gray-900">📡 Панель пинга</h1>
            <span class="bg-green-100 text-green-800 text-xs font-semibold px-2.5 py-0.5 rounded-full">Система активна</span>
        </header>

        <div class="bg-white p-6 rounded-xl shadow-sm mb-8">
            <h2 class="text-xl font-bold mb-4 text-gray-700">Добавить новое устройство</h2>
            <form action="/add" method="POST" class="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                    <label class="block text-sm font-medium mb-1 text-gray-600">IP адрес</label>
                    <input type="text" name="ip" placeholder="192.168.30.1" required class="w-full border p-2 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none">
                </div>
                <div>
                    <label class="block text-sm font-medium mb-1 text-gray-600">Интервал проверки (в секундах)</label>
                    <input type="number" name="interval" placeholder="60" min="5" value="60" required class="w-full border p-2 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none">
                </div>
                <div class="md:col-span-2">
                    <label class="block text-sm font-medium mb-1 text-gray-600">Текст сообщения если ДОСТУПЕН</label>
                    <input type="text" name="msg_up" placeholder="🟢 Вислая на связи" required class="w-full border p-2 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none">
                </div>
                <div class="md:col-span-2">
                    <label class="block text-sm font-medium mb-1 text-gray-600">Текст сообщения если НЕ ДОСТУПЕН</label>
                    <input type="text" name="msg_down" placeholder="🔴 Вислая не доступна" required class="w-full border p-2 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none">
                </div>
                <div class="md:col-span-2 text-right">
                    <button type="submit" class="bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 px-6 rounded-lg transition-colors cursor-pointer w-full md:w-auto">Добавить</button>
                </div>
            </form>
        </div>

        <div class="bg-white rounded-xl shadow-sm overflow-hidden">
            <h2 class="text-xl font-bold p-6 border-b text-gray-700">Текущие задачи на проверку</h2>
            <div class="overflow-x-auto">
                <table class="w-full text-left border-collapse">
                    <thead>
                        <tr class="bg-gray-50 text-gray-500 text-sm uppercase">
                            <th class="p-4">Статус</th>
                            <th class="p-4">IP адрес</th>
                            <th class="p-4">Период</th>
                            <th class="p-4">Сообщения (Up / Down)</th>
                            <th class="p-4 text-center">Действие</th>
                        </tr>
                    </thead>
                    <tbody class="divide-y divide-gray-100">
                        {% for ip, data in hosts.items() %}
                        <tr class="hover:bg-gray-50">
                            <td class="p-4">
                                {% if data.last_state == 'up' %}
                                <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">● OK</span>
                                {% elif data.last_state == 'down' %}
                                <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800">● DOWN</span>
                                {% else %}
                                <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-600">Ожидание</span>
                                {% endif %}
                            </td>
                            <td class="p-4 font-mono font-semibold text-gray-900">{{ ip }}</td>
                            <td class="p-4 text-gray-600 text-sm">раз в {{ data.interval }} сек.</td>
                            <td class="p-4 text-xs max-w-xs truncate">
                                <span class="text-green-600 block">{{ data.msg_up }}</span>
                                <span class="text-red-600 block">{{ data.msg_down }}</span>
                            </td>
                            <td class="p-4 text-center">
                                <a href="/delete/{{ ip }}" class="text-red-500 hover:text-red-700 font-medium text-sm transition-colors">Удалить</a>
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
    </div>
</body>
</html>

```

Сохраните файл (`Ctrl+O`, `Enter`, `Ctrl+X`).

---

## Шаг 4. Создание основного Python-приложения

Создайте главный файл скрипта:

```bash
nano /root/ping_manager/app.py

```

Вставьте следующий код. **Обязательно пропишите свои TOKEN и CHAT_ID на строках 11 и 12**:

```python
import os
import json
import time
import subprocess
import threading
from flask import Flask, render_template, request, redirect

app = Flask(__name__)

CONFIG_FILE = "/root/ping_manager/config.json"

# --- TELEGRAM НАСТРОЙКИ ---
TOKEN = "ВАШ_ТОКЕН_БОТА"
CHAT_ID = "ВАШ_CHAT_ID"

import requests


def send_telegram(text):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    try:
        requests.post(
            url, json={"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"}, timeout=5
        )
    except Exception as e:
        print(f"Ошибка Telegram: {e}")


# --- РАБОТА С ХОСТАМИ ---
def load_hosts():
    if not os.path.exists(CONFIG_FILE):
        # Дефолтные настройки для примера, если файла нет
        default = {
            "192.168.30.1": {
                "interval": 60,
                "msg_up": "🟢 Вислая на связи",
                "msg_down": "🔴 Вислая не доступна",
                "last_state": "unknown",
                "last_check": 0,
            }
        }
        save_hosts(default)
        return default
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)


def save_hosts(hosts):
    with open(CONFIG_FILE, "w") as f:
        json.dump(hosts, f, indent=4)


def check_ping(ip):
    res = subprocess.run(
        ["ping", "-c", "2", "-W", "2", ip], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    return res.returncode == 0


# --- ФОНОВЫЙ ПОТОК ПИНГОВАНИЯ ---
def ping_worker():
    while True:
        try:
            hosts = load_hosts()
            updated = False
            current_time = time.time()

            for ip, data in hosts.items():
                # Проверяем, пришло ли время пинговать этот хост
                if current_time - data.get("last_check", 0) >= int(data["interval"]):
                    is_up = check_ping(ip)
                    current_state = "up" if is_up else "down"

                    # Если состояние изменилось (и это не первая проверка "unknown")
                    if data["last_state"] != current_state:
                        if data["last_state"] != "unknown":
                            msg = data["msg_up"] if is_up else data["msg_down"]
                            send_telegram(msg)

                        data["last_state"] = current_state
                        updated = True

                    data["last_check"] = current_time

            if updated:
                save_hosts(hosts)

        except Exception as e:
            print(f"Ошибка в воркере: {e}")

        time.sleep(1)  # Спим секунду и проверяем заново тайминги хостов


# --- ВЕБ ИНТЕРФЕЙС (FLASK) ---
@app.route("/")
def index():
    hosts = load_hosts()
    return render_template("index.html", hosts=hosts)


@app.route("/add", border_v=None, methods=["POST"])
def add_host():
    ip = request.form.get("ip").strip()
    interval = request.form.get("interval")
    msg_up = request.form.get("msg_up")
    msg_down = request.form.get("msg_down")

    if ip:
        hosts = load_hosts()
        hosts[ip] = {
            "interval": int(interval),
            "msg_up": msg_up,
            "msg_down": msg_down,
            "last_state": "unknown",
            "last_check": 0,
        }
        save_hosts(hosts)
    return redirect("/")


@app.route("/delete/<ip>")
def delete_host(ip):
    hosts = load_hosts()
    if ip in hosts:
        del hosts[ip]
        save_hosts(hosts)
    return redirect("/")


if __name__ == "__main__":
    # Запуск фонового пинговалщика в отдельном потоке
    t = threading.Thread(target=ping_worker, daemon=True)
    t.start()

    # Запуск веб-сервера (доступен на порту 5000 со всех IP)
    app.run(host="0.0.0.0", port=5000)

```

Сохраните файл (`Ctrl+O`, `Enter`, `Ctrl+X`).

---

## Шаг 5. Удаляем старый Cron (Важно!)

Так как скрипт теперь сам контролирует время в памяти, старая задача в планировщике нам больше не нужна.

1. Введите команду: `crontab -e`
2. Сотрите созданную ранее строку с `ping_check.py`.
3. Сохраните и закройте.

---

## Шаг 6. Настройка автозапуска через Systemd

Сделаем так, чтобы наша панель управления автоматически включалась при перезагрузке Raspberry Pi и работала в фоне.

1. Создаем файл службы:
```bash
nano /etc/systemd/system/ping-ui.service

```


2. Вставляем в него следующее содержимое:
```ini
[Unit]
Description=Ping WebUI Manager
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/ping_manager
ExecStart=/usr/bin/python3 /root/ping_manager/app.py
Restart=always

[Install]
WantedBy=multi-user.target

```


3. Сохраняем и выходим.
4. Включаем и запускаем службу:
```bash
systemctl daemon-reload
systemctl enable ping-ui.service
systemctl start ping-ui.service

```



---

## Результат!

Откройте браузер на компьютере или телефоне, находящемся в той же сети, что и Raspberry Pi, и перейдите по адресу:
`http://IP_ВАШЕЙ_RASPBERRY_PI:5000`

Перед вами откроется красивая панель управления, где вы сможете на лету добавлять новые IP-адреса, выставлять для каждого разную периодичность (например, роутер проверять каждые 10 секунд, а сервер — каждые 300) и писать индивидуальный текст оповещений для Telegram. Изменения вступают в силу мгновенно без перезапуска программы.




Давайте разбираться, где именно произошел сбой. Поскольку мы объединили веб-сервер и фоновый скрипт, причин может быть несколько: от опечатки в токене до блокировки порта.

Пройдем по цепочке диагностики, чтобы найти «виновника». Выполните следующие команды в терминале вашей DietPi.

---

### Шаг 1. Проверяем, запущен ли сервис вообще

Введите команду:

```bash
systemctl status ping-ui.service

```

**Что ищем в ответе:**

* Если горит зеленым **`active (running)`**, значит, Python-скрипт работает. Идём к Шагу 2.
* Если горит красным **`failed`** или `inactive`, прокрутите вывод ниже — там будут последние строки ошибок Python.

> **Частая ошибка:** Если в логе написано что-то вроде `KeyError` или `SyntaxError`, скорее всего, где-то в коде `app.py` съехали отступы или вы случайно удалили кавычку, когда вставляли `TOKEN` и `CHAT_ID`.

---

### Шаг 2. Смотрим подробные логи

Если сервис упал, выведите последние 50 строк его логов, чтобы увидеть точную ошибку:

```bash
journalctl -u ping-ui.service -n 50 --no-pager

```

*Посмотрите на самые нижние строки. Если там есть слова `Traceback (most recent call last):`, пришлите мне то, что написано под ними — я сразу скажу, в какой строке кода проблема.*

---

### Шаг 3. Что именно не работает?

В зависимости от того, что именно "пошло не так", проверьте два сценария:

#### Сценарий А: Не открывается WebUI в браузере

Если сервис пишет `active (running)`, но сайт по адресу `http://IP_МАЛИНЫ:5000` не грузится:

1. Проверьте, слушает ли малина порт 5000:
```bash
ss -tulpn | grep 5000

```


Вы должны увидеть строку, в которой есть `0.0.0.0:5000`.
2. Проверьте, правильный ли IP-адрес малинки вы вводите в браузере. Узнать точный IP в DietPi можно командой:
```bash
ip a | grep inet

```



#### Сценарий Б: Сайт открывается, но сообщения в Telegram не приходят

Если панель работает, вы добавили IP, статус меняется (например, с `Ожидание` на `● OK` или `● DOWN`), но бот молчит:

1. Скорее всего, неверно указан `TOKEN` или `CHAT_ID` в файле `/root/ping_manager/app.py`.
2. Откройте файл заново (`nano /root/ping_manager/app.py`), проверьте, чтобы токен был внутри кавычек, без лишних пробелов и букв `bot` перед цифрами (нужны только цифры и буквы самого токена).
3. После любого изменения файла `app.py` нужно перезапускать службу:
```bash
systemctl restart ping-ui.service

```



---

**На каком из этих этапов возникает затык? Вышлите сюда лог команды `systemctl status ping-ui.service` или `journalctl`, и мы мгновенно всё починим!**




Отлично, логи — это супер-вещь. Ошибка видна как на ладони, и это мой косяк.

В строке 101 скрипта `app.py` затесался случайный технический мусор: `border_v=None`. Фреймворк Flask не понимает, что это за аргумент, и из-за этого падает при запуске.

Давайте исправим эту строчку, и всё сразу заведется.

### Шаг 1. Исправляем код

1. Откройте файл скрипта для редактирования:
```bash
nano /root/ping_manager/app.py

```


2. Найдите строку номер 101 (она находится чуть ниже середины файла, в секции `ВЕБ ИНТЕРФЕЙС`). Она выглядит так:
```python
@app.route("/add", border_v=None, methods=["POST"])

```


3. Удалите из неё лишний кусок `border_v=None, `, чтобы получилось строго вот так:
```python
@app.route("/add", methods=["POST"])

```


4. Сохраните изменения (`Ctrl+O`, затем `Enter`) и выйдете из редактора (`Ctrl+X`).

---

### Шаг 2. Перезапуск службы

Поскольку система защиты `systemd` заблокировала частые перезапуски упавшего сервиса (строка `Start request repeated too quickly`), нам нужно сбросить счетчик и запустить его заново:

```bash
systemctl reset-failed ping-ui.service
systemctl restart ping-ui.service

```

---

### Шаг 3. Проверяем статус

Убедимся, что теперь всё работает:

```bash
systemctl status ping-ui.service

```

В выводе должно загореться заветное зеленое **`active (running)`**.

---

### Шаг 4. Вход в панель

Судя по выводу вашей команды `ip a`, локальный IP-адрес вашей Raspberry Pi в локальной сети: **`192.168.3.115`**.

Открывайте браузер на компьютере или телефоне (главное, чтобы они были подключены к той же сети/роутеру) и переходите по адресу:

```text
http://192.168.3.115:5000

```

Панель откроется, и вы сможете добавлять любые IP для мониторинга!





Отличные улучшения. Для поддержки SOCKS5 прокси в Python нам понадобится небольшое дополнение к библиотеке `requests`, чтобы она умела заворачивать трафик через SOCKS-протокол.

Поскольку у нас добавляются глобальные настройки (включение прокси, IP и порт), мы будем хранить их в том же JSON-файле под специальным ключом `_settings`.

Вот обновленная пошаговая инструкция.

---

## Шаг 1. Установка поддержки SOCKS5

Зайдите на вашу Raspberry Pi и установите системный пакет для работы `requests` с SOCKS-прокси:

```bash
apt install python3-socks -y

```

---

## Шаг 2. Обновление HTML-шаблона (`index.html`)

Нам нужно добавить блок настроек прокси в самом верху и обновить таблицу, чтобы она выводила время изменения статуса.

Откройте файл:

```bash
nano /root/ping_manager/templates/index.html

```

Полностью удалите старое содержимое и вставьте этот обновленный код:

```html
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Мониторинг Сети</title>
    <script src="https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4"></script>
</head>
<body class="bg-gray-100 text-gray-800 font-sans">
    <div class="max-w-4xl mx-auto p-4 sm:p-6">
        <header class="mb-8 flex justify-between items-center">
            <h1 class="text-2xl sm:text-3xl font-bold text-gray-900">📡 Панель пинга</h1>
            <span class="bg-green-100 text-green-800 text-xs font-semibold px-2.5 py-0.5 rounded-full">Система активна</span>
        </header>

        <div class="bg-white p-6 rounded-xl shadow-sm mb-8 border-l-4 border-indigo-500">
            <h2 class="text-xl font-bold mb-4 text-gray-700">Настройки SOCKS5 Прокси для Telegram</h2>
            <form action="/save_proxy" method="POST" class="grid grid-cols-1 md:grid-cols-4 gap-4 items-end">
                <div>
                    <label class="block text-sm font-medium mb-1 text-gray-600">IP прокси</label>
                    <input type="text" name="proxy_ip" value="{{ settings.proxy_ip }}" placeholder="127.0.0.1" class="w-full border p-2 rounded-lg focus:ring-2 focus:ring-indigo-500 outline-none">
                </div>
                <div>
                    <label class="block text-sm font-medium mb-1 text-gray-600">Порт</label>
                    <input type="number" name="proxy_port" value="{{ settings.proxy_port }}" placeholder="1080" class="w-full border p-2 rounded-lg focus:ring-2 focus:ring-indigo-500 outline-none">
                </div>
                <div class="flex items-center h-11">
                    <input type="checkbox" name="proxy_enabled" id="proxy_enabled" class="w-4 h-4 text-indigo-600 border-gray-300 rounded focus:ring-indigo-500" {% if settings.proxy_enabled %}checked{% endif %}>
                    <label for="proxy_enabled" class="ml-2 block text-sm font-medium text-gray-700">Включить прокси</label>
                </div>
                <div class="text-right">
                    <button type="submit" class="bg-indigo-600 hover:bg-indigo-700 text-white font-medium py-2 px-6 rounded-lg transition-colors cursor-pointer w-full">Сохранить</button>
                </div>
            </form>
        </div>

        <div class="bg-white p-6 rounded-xl shadow-sm mb-8">
            <h2 class="text-xl font-bold mb-4 text-gray-700">Добавить новое устройство</h2>
            <form action="/add" method="POST" class="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                    <label class="block text-sm font-medium mb-1 text-gray-600">IP адрес</label>
                    <input type="text" name="ip" placeholder="192.168.30.1" required class="w-full border p-2 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none">
                </div>
                <div>
                    <label class="block text-sm font-medium mb-1 text-gray-600">Интервал проверки (в секундах)</label>
                    <input type="number" name="interval" placeholder="60" min="5" value="60" required class="w-full border p-2 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none">
                </div>
                <div class="md:col-span-2">
                    <label class="block text-sm font-medium mb-1 text-gray-600">Текст сообщения если ДОСТУПЕН</label>
                    <input type="text" name="msg_up" placeholder="🟢 Вислая на связи" required class="w-full border p-2 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none">
                </div>
                <div class="md:col-span-2">
                    <label class="block text-sm font-medium mb-1 text-gray-600">Текст сообщения если НЕ ДОСТУПЕН</label>
                    <input type="text" name="msg_down" placeholder="🔴 Вислая не доступна" required class="w-full border p-2 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none">
                </div>
                <div class="md:col-span-2 text-right">
                    <button type="submit" class="bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 px-6 rounded-lg transition-colors cursor-pointer w-full md:w-auto">Добавить</button>
                </div>
            </form>
        </div>

        <div class="bg-white rounded-xl shadow-sm overflow-hidden">
            <h2 class="text-xl font-bold p-6 border-b text-gray-700">Текущие задачи на проверку</h2>
            <div class="overflow-x-auto">
                <table class="w-full text-left border-collapse">
                    <thead>
                        <tr class="bg-gray-50 text-gray-500 text-sm uppercase">
                            <th class="p-4">Статус и Время</th>
                            <th class="p-4">IP адрес</th>
                            <th class="p-4">Период</th>
                            <th class="p-4">Сообщения (Up / Down)</th>
                            <th class="p-4 text-center">Действие</th>
                        </tr>
                    </thead>
                    <tbody class="divide-y divide-gray-100">
                        {% for ip, data in hosts.items() %}
                        <tr class="hover:bg-gray-50">
                            <td class="p-4">
                                <div class="mb-1">
                                    {% if data.last_state == 'up' %}
                                    <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">● OK</span>
                                    {% elif data.last_state == 'down' %}
                                    <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800">● DOWN</span>
                                    {% else %}
                                    <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-600">Ожидание</span>
                                    {% endif %}
                                </div>
                                <div class="text-xs text-gray-500 font-mono">
                                    {{ data.status_time if data.status_time else '--:--:-- --.--.----' }}
                                </div>
                            </td>
                            <td class="p-4 font-mono font-semibold text-gray-900">{{ ip }}</td>
                            <td class="p-4 text-gray-600 text-sm">раз в {{ data.interval }} сек.</td>
                            <td class="p-4 text-xs max-w-xs truncate">
                                <span class="text-green-600 block">{{ data.msg_up }}</span>
                                <span class="text-red-600 block">{{ data.msg_down }}</span>
                            </td>
                            <td class="p-4 text-center">
                                <a href="/delete/{{ ip }}" class="text-red-500 hover:text-red-700 font-medium text-sm transition-colors">Удалить</a>
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
    </div>
</body>
</html>

```

---

## Шаг 3. Обновление серверного скрипта (`app.py`)

Теперь обновим логику бэкенда: добавим чтение/сохранение настроек прокси, динамическое формирование словаря `proxies` для `requests` перед отправкой сообщения, а также фиксацию времени изменения статуса в формате `ЧЧ:ММ:СС ДД.ММ.ГГГГ`.

Откройте файл:

```bash
nano /root/ping_manager/app.py

```

Замените всё содержимое на этот код:

```python
import os
import json
import time
from datetime import datetime
import subprocess
import threading
import requests
from flask import Flask, render_template, request, redirect

app = Flask(__name__)

CONFIG_FILE = "/root/ping_manager/config.json"

# --- TELEGRAM НАСТРОЙКИ ---
TOKEN = "ВАШ_ТОКЕН_БОТА"
CHAT_ID = "ВАШ_CHAT_ID"


def send_telegram(text):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"}

    # Подгружаем настройки прокси "на лету" из конфига
    config = load_config_raw()
    settings = config.get(
        "_settings", {"proxy_enabled": False, "proxy_ip": "", "proxy_port": ""}
    )

    proxies = None
    if (
        settings.get("proxy_enabled")
        and settings.get("proxy_ip")
        and settings.get("proxy_port")
    ):
        p_str = f"socks5://{settings['proxy_ip']}:{settings['proxy_port']}"
        proxies = {"http": p_str, "https": p_str}

    try:
        requests.post(url, json=payload, proxies=proxies, timeout=10)
    except Exception as e:
        print(f"Ошибка отправки в Telegram (Прокси: {settings.get('proxy_enabled')}): {e}")


# --- РАБОТА С КОНФИГУРАЦИЕЙ ---
def load_config_raw():
    if not os.path.exists(CONFIG_FILE):
        default = {
            "_settings": {"proxy_enabled": False, "proxy_ip": "", "proxy_port": "1080"},
            "192.168.30.1": {
                "interval": 60,
                "msg_up": "🟢 Вислая на связи",
                "msg_down": "🔴 Вислая не доступна",
                "last_state": "unknown",
                "status_time": "",
                "last_check": 0,
            },
        }
        with open(CONFIG_FILE, "w") as f:
            json.dump(default, f, indent=4)
        return default

    with open(CONFIG_FILE, "r") as f:
        return json.load(f)


def save_config_raw(config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=4)


def load_hosts_and_settings():
    config = load_config_raw()
    settings = config.get(
        "_settings", {"proxy_enabled": False, "proxy_ip": "", "proxy_port": "1080"}
    )
    # Изолируем хосты от служебных настроек для вывода в таблицу
    hosts = {k: v for k, v in config.items() if not k.startswith("_")}
    return hosts, settings


def check_ping(ip):
    res = subprocess.run(
        ["ping", "-c", "2", "-W", "2", ip], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    return res.returncode == 0


# --- ФОНОВЫЙ ПОТОК ПИНГОВАНИЯ ---
def ping_worker():
    while True:
        try:
            config = load_config_raw()
            updated = False
            current_time = time.time()

            for ip, data in config.items():
                if ip.startswith("_"):
                    continue  # Пропускаем блок настроек прокси

                if current_time - data.get("last_check", 0) >= int(data["interval"]):
                    is_up = check_ping(ip)
                    current_state = "up" if is_up else "down"

                    if data["last_state"] != current_state:
                        # Форматируем время по стандарту: 12:01:02 08.06.2026
                        formatted_time = datetime.now().strftime("%H:%M:%S %d.%m.%Y")
                        data["status_time"] = formatted_time

                        if data["last_state"] != "unknown":
                            msg = data["msg_up"] if is_up else data["msg_down"]
                            send_telegram(msg)

                        data["last_state"] = current_state
                        updated = True

                    data["last_check"] = current_time

            if updated:
                save_config_raw(config)

        except Exception as e:
            print(f"Ошибка в воркере пинга: {e}")

        time.sleep(1)


# --- ВЕБ ИНТЕРФЕЙС (FLASK) ---
@app.route("/")
def index():
    hosts, settings = load_hosts_and_settings()
    return render_template("index.html", hosts=hosts, settings=settings)


@app.route("/add", methods=["POST"])
def add_host():
    ip = request.form.get("ip").strip()
    interval = request.form.get("interval")
    msg_up = request.form.get("msg_up")
    msg_down = request.form.get("msg_down")

    if ip:
        config = load_config_raw()
        config[ip] = {
            "interval": int(interval),
            "msg_up": msg_up,
            "msg_down": msg_down,
            "last_state": "unknown",
            "status_time": "",
            "last_check": 0,
        }
        save_config_raw(config)
    return redirect("/")


@app.route("/delete/<ip>")
def delete_host(ip):
    config = load_config_raw()
    if ip in config:
        del config[ip]
        save_config_raw(config)
    return redirect("/")


@app.route("/save_proxy", methods=["POST"])
def save_proxy():
    proxy_ip = request.form.get("proxy_ip").strip()
    proxy_port = request.form.get("proxy_port").strip()
    proxy_enabled = True if request.form.get("proxy_enabled") else False

    config = load_config_raw()
    config["_settings"] = {
        "proxy_enabled": proxy_enabled,
        "proxy_ip": proxy_ip,
        "proxy_port": proxy_port,
    }
    save_config_raw(config)
    return redirect("/")


if __name__ == "__main__":
    t = threading.Thread(target=ping_worker, daemon=True)
    t.start()
    app.run(host="0.0.0.0", port=5000)

```

*(Не забудьте вернуть ваши реальные токен и ID на строках 13 и 14).*

---

## Шаг 4. Перезапуск службы

Перезапустите ваш сервис, чтобы применился новый Python-код:

```bash
systemctl restart ping-ui.service

```

---

## Что изменилось в WebUI?

1. **Блок SOCKS5**: Сверху появилась фиолетовая панель. Вы можете ввести туда IP прокси, порт, поставить галочку "Включить прокси" и нажать "Сохранить". Скрипт мгновенно начнет пускать запросы к Telegram через указанный сервер, перезапускать службу не требуется.
2. **Время статуса**: В таблице в колонке "Статус" теперь под кнопками `OK` / `DOWN` выводится точное время и дата последнего изменения состояния. При первом запуске или добавлении нового IP там будет отображаться заглушка `--:--:--`, но как только скрипт сделает первую проверку, там зафиксируется время.



