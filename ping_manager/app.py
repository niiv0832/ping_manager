import os
import json
import time
from datetime import datetime
import subprocess
import threading
import requests
from urllib.parse import urlencode
from flask import Flask, render_template, request, redirect

app = Flask(__name__)

CONFIG_FILE = "/root/ping_manager/config.json"
ENV_FILE = "/root/ping_manager/.env"
DEFAULT_LANGUAGE = "en"
DEFAULT_SETTINGS = {
    "proxy_enabled": False,
    "proxy_ip": "",
    "proxy_port": "1080",
    "language": DEFAULT_LANGUAGE,
}
TELEGRAM_TIMEOUT = (5, 20)
TRANSLATIONS = {
    "en": {
        "html_lang": "en",
        "title": "Network Monitor",
        "header_title": "Ping Panel",
        "system_active": "System active",
        "language": "Language",
        "english": "English",
        "russian": "Russian",
        "proxy_settings": "SOCKS5 Proxy Settings for Telegram",
        "proxy_ip": "Proxy IP",
        "proxy_port": "Port",
        "proxy_enabled": "Enable proxy",
        "save": "Save",
        "check_proxy": "Check proxy via Telegram",
        "edit_device": "Edit device",
        "add_device": "Add new device",
        "ip_address": "IP address",
        "check_interval": "Check interval (seconds)",
        "msg_up": "Message when AVAILABLE",
        "msg_down": "Message when UNAVAILABLE",
        "cancel": "Cancel",
        "save_changes": "Save changes",
        "add": "Add",
        "current_tasks": "Current check tasks",
        "status_time": "Status and Time",
        "period": "Period",
        "messages": "Messages (Up / Down)",
        "action": "Action",
        "waiting": "Waiting",
        "every_seconds": "every {interval} sec.",
        "check": "Check",
        "edit": "Edit",
        "delete": "Delete",
        "default_ip": "192.168.0.1",
        "default_msg_up": "Host is available",
        "default_msg_down": "Host access lost",
        "manual_prefix": "Manual check: ",
        "host_not_found": "Host {ip} was not found.",
        "ip_empty": "IP address cannot be empty.",
        "interval_number": "Check interval must be a number.",
        "host_exists": "Host {ip} already exists.",
        "host_updated": "Host {ip} updated.",
        "state_up": "available",
        "state_down": "unavailable",
        "telegram_sent": "Telegram message sent.",
        "telegram_failed": "Telegram message was not sent, check service logs.",
        "manual_changed": "Manual check {ip}: status changed, now {state}. {notify}",
        "manual_unchanged": "Manual check {ip}: status did not change, now {state}. {notify}",
        "token_missing": "Telegram TOKEN is not set. Check {env_file}.",
        "proxy_invalid": "SOCKS5 proxy is invalid: check IP and port.",
        "socks_missing": "SOCKS5 is not supported by requests. Install python3-socks.",
        "proxy_error": "Proxy check error: {error}",
        "proxy_ok": "SOCKS5 proxy works: Telegram API responded as {bot_name}.",
    },
    "ru": {
        "html_lang": "ru",
        "title": "Мониторинг Сети",
        "header_title": "Панель пинга",
        "system_active": "Система активна",
        "language": "Язык",
        "english": "Английский",
        "russian": "Русский",
        "proxy_settings": "Настройки SOCKS5 Прокси для Telegram",
        "proxy_ip": "IP прокси",
        "proxy_port": "Порт",
        "proxy_enabled": "Включить прокси",
        "save": "Сохранить",
        "check_proxy": "Проверить прокси через Telegram",
        "edit_device": "Редактировать устройство",
        "add_device": "Добавить новое устройство",
        "ip_address": "IP адрес",
        "check_interval": "Интервал проверки (в секундах)",
        "msg_up": "Текст сообщения если ДОСТУПЕН",
        "msg_down": "Текст сообщения если НЕ ДОСТУПЕН",
        "cancel": "Отмена",
        "save_changes": "Сохранить изменения",
        "add": "Добавить",
        "current_tasks": "Текущие задачи на проверку",
        "status_time": "Статус и Время",
        "period": "Период",
        "messages": "Сообщения (Up / Down)",
        "action": "Действие",
        "waiting": "Ожидание",
        "every_seconds": "раз в {interval} сек.",
        "check": "Проверить",
        "edit": "Редактировать",
        "delete": "Удалить",
        "default_ip": "192.168.0.1",
        "default_msg_up": "Хост доступен",
        "default_msg_down": "Доступ к хосту пропал",
        "manual_prefix": "Ручная проверка: ",
        "host_not_found": "Хост {ip} не найден.",
        "ip_empty": "IP адрес не может быть пустым.",
        "interval_number": "Интервал проверки должен быть числом.",
        "host_exists": "Хост {ip} уже существует.",
        "host_updated": "Хост {ip} обновлен.",
        "state_up": "доступен",
        "state_down": "недоступен",
        "telegram_sent": "Telegram-сообщение отправлено.",
        "telegram_failed": "Telegram-сообщение не отправлено, проверьте логи сервиса.",
        "manual_changed": "Ручная проверка {ip}: статус изменился, сейчас {state}. {notify}",
        "manual_unchanged": "Ручная проверка {ip}: статус не изменился, сейчас {state}. {notify}",
        "token_missing": "Telegram TOKEN не задан. Проверьте файл {env_file}.",
        "proxy_invalid": "SOCKS5-прокси настроен некорректно: проверьте IP и порт.",
        "socks_missing": "SOCKS5 не поддерживается requests. Установите python3-socks.",
        "proxy_error": "Ошибка проверки прокси: {error}",
        "proxy_ok": "SOCKS5-прокси работает: Telegram API ответил как {bot_name}.",
    },
}


def build_proxy_config(settings):
    if not settings.get("proxy_enabled"):
        return None

    proxy_ip = str(settings.get("proxy_ip", "")).strip()
    proxy_port = str(settings.get("proxy_port", "")).strip()

    if not proxy_ip or not proxy_port:
        print("SOCKS5 прокси включен, но IP или порт не заполнены. Отправка пойдет напрямую.")
        return None

    try:
        port_number = int(proxy_port)
    except ValueError:
        print(f"Некорректный порт SOCKS5 прокси: {proxy_port}. Отправка пойдет напрямую.")
        return None

    if not 1 <= port_number <= 65535:
        print(f"Порт SOCKS5 прокси вне допустимого диапазона: {proxy_port}. Отправка пойдет напрямую.")
        return None

    proxy_url = f"socks5h://{proxy_ip}:{port_number}"
    return {"http": proxy_url, "https": proxy_url}


def post_telegram_message(url, payload, proxies=None):
    response = requests.post(url, json=payload, proxies=proxies, timeout=TELEGRAM_TIMEOUT)
    response.raise_for_status()

    result = response.json()
    if not result.get("ok"):
        description = result.get("description", "неизвестная ошибка Telegram API")
        raise RuntimeError(description)


def get_telegram_bot_info(token, proxies):
    url = f"https://api.telegram.org/bot{token}/getMe"
    response = requests.get(url, proxies=proxies, timeout=TELEGRAM_TIMEOUT)
    response.raise_for_status()

    result = response.json()
    if not result.get("ok"):
        description = result.get("description", "неизвестная ошибка Telegram API")
        raise RuntimeError(description)

    return result.get("result", {})


def normalize_language(language):
    if language in TRANSLATIONS:
        return language
    return DEFAULT_LANGUAGE


def get_settings(config):
    settings = DEFAULT_SETTINGS.copy()
    settings.update(config.get("_settings", {}))
    settings["language"] = normalize_language(settings.get("language", DEFAULT_LANGUAGE))
    return settings


def get_translations(settings):
    return TRANSLATIONS[normalize_language(settings.get("language", DEFAULT_LANGUAGE))]


def load_env_file(path=ENV_FILE):
    variables = {}

    if not os.path.exists(path):
        return variables

    with open(path, "r") as f:
        for line in f:
            line = line.strip()

            if not line or line.startswith("#") or "=" not in line:
                continue

            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip()

            if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
                value = value[1:-1]

            variables[key] = value

    return variables


def load_telegram_settings():
    file_variables = load_env_file()
    token = file_variables.get("TOKEN") or os.environ.get("TOKEN", "")
    chat_id = file_variables.get("CHAT_ID") or os.environ.get("CHAT_ID", "")
    return token.strip(), chat_id.strip()


def send_telegram(text):
    token, chat_id = load_telegram_settings()

    if not token or not chat_id:
        print(f"Telegram TOKEN или CHAT_ID не заданы. Проверьте файл {ENV_FILE}.")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}

    # Подгружаем настройки прокси "на лету" из конфига
    config = load_config_raw()
    settings = config.get("_settings", DEFAULT_SETTINGS)
    proxies = build_proxy_config(settings)

    try:
        post_telegram_message(url, payload, proxies=proxies)
        return True
    except requests.exceptions.InvalidSchema as e:
        if proxies and "SOCKS" in str(e):
            print("SOCKS5 не поддерживается установленным requests. Установите пакет python3-socks.")
            try:
                post_telegram_message(url, payload)
                return True
            except Exception as direct_error:
                print(f"Ошибка прямой отправки в Telegram после сбоя SOCKS5: {direct_error}")
            return False
        print(f"Ошибка отправки в Telegram: {e}")
        return False
    except requests.exceptions.RequestException as e:
        if proxies:
            print(f"Ошибка отправки в Telegram через SOCKS5: {e}. Пробую отправить напрямую.")
            try:
                post_telegram_message(url, payload)
                return True
            except Exception as direct_error:
                print(f"Ошибка прямой отправки в Telegram после сбоя SOCKS5: {direct_error}")
            return False
        print(f"Ошибка отправки в Telegram: {e}")
        return False
    except Exception as e:
        print(f"Ошибка отправки в Telegram: {e}")
        return False


# --- РАБОТА С КОНФИГУРАЦИЕЙ ---
def load_config_raw():
    if not os.path.exists(CONFIG_FILE):
        default = {
            "_settings": DEFAULT_SETTINGS.copy(),
            "192.168.0.1": {
                "interval": 60,
                "msg_up": TRANSLATIONS[DEFAULT_LANGUAGE]["default_msg_up"],
                "msg_down": TRANSLATIONS[DEFAULT_LANGUAGE]["default_msg_down"],
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
    settings = get_settings(config)
    # Изолируем хосты от служебных настроек для вывода в таблицу
    hosts = {k: v for k, v in config.items() if not k.startswith("_")}
    return hosts, settings


def check_ping(ip):
    res = subprocess.run(
        ["ping", "-c", "2", "-W", "2", ip], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    return res.returncode == 0


def check_config_host(config, ip, notify=True, force_notify=False, notification_prefix=""):
    if ip not in config or ip.startswith("_"):
        return None

    data = config[ip]
    is_up = check_ping(ip)
    current_state = "up" if is_up else "down"
    previous_state = data.get("last_state", "unknown")

    data["last_check"] = time.time()

    changed = previous_state != current_state

    if changed:
        data["status_time"] = datetime.now().strftime("%H:%M:%S %d.%m.%Y")

        data["last_state"] = current_state

    notified = False
    if notify and (changed or force_notify):
        msg = data["msg_up"] if is_up else data["msg_down"]
        if notification_prefix:
            msg = f"{notification_prefix}{msg}"
        notified = send_telegram(msg)

    return {
        "ip": ip,
        "current_state": current_state,
        "previous_state": previous_state,
        "changed": changed,
        "notified": notified,
    }


def redirect_with_message(message, message_type="info"):
    query = urlencode({"message": message, "message_type": message_type})
    return redirect(f"/?{query}")


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
                    check_config_host(config, ip, notify=True)
                    updated = True

            if updated:
                save_config_raw(config)

        except Exception as e:
            print(f"Ошибка в воркере пинга: {e}")

        time.sleep(1)


# --- ВЕБ ИНТЕРФЕЙС (FLASK) ---
@app.route("/")
def index():
    hosts, settings = load_hosts_and_settings()
    translations = get_translations(settings)
    edit_ip = request.args.get("edit_ip", "")
    edit_host = hosts.get(edit_ip) if edit_ip else None

    return render_template(
        "index.html",
        hosts=hosts,
        settings=settings,
        t=translations,
        edit_ip=edit_ip,
        edit_host=edit_host,
        message=request.args.get("message", ""),
        message_type=request.args.get("message_type", "info"),
    )


@app.route("/add", methods=["POST"])
def add_host():
    ip = request.form.get("ip", "").strip()
    interval = request.form.get("interval", "60")
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


@app.route("/update_host", methods=["POST"])
def update_host():
    config = load_config_raw()
    translations = get_translations(get_settings(config))
    original_ip = request.form.get("original_ip", "").strip()
    new_ip = request.form.get("ip", "").strip()
    interval = request.form.get("interval", "60")
    msg_up = request.form.get("msg_up", "")
    msg_down = request.form.get("msg_down", "")

    if not original_ip or not new_ip:
        return redirect_with_message(translations["ip_empty"], "error")

    try:
        interval_value = int(interval)
    except ValueError:
        return redirect_with_message(translations["interval_number"], "error")

    if original_ip not in config or original_ip.startswith("_"):
        return redirect_with_message(translations["host_not_found"].format(ip=original_ip), "error")

    data = config[original_ip]
    data["interval"] = interval_value
    data["msg_up"] = msg_up
    data["msg_down"] = msg_down

    if new_ip != original_ip:
        if new_ip in config:
            return redirect_with_message(translations["host_exists"].format(ip=new_ip), "error")
        del config[original_ip]
        config[new_ip] = data

    save_config_raw(config)
    return redirect_with_message(translations["host_updated"].format(ip=new_ip), "success")


@app.route("/delete/<ip>")
def delete_host(ip):
    config = load_config_raw()
    if ip in config:
        del config[ip]
        save_config_raw(config)
    return redirect("/")


@app.route("/check_host", methods=["POST"])
def check_host():
    ip = request.form.get("ip", "").strip()
    config = load_config_raw()
    translations = get_translations(get_settings(config))
    result = check_config_host(
        config,
        ip,
        notify=True,
        force_notify=True,
        notification_prefix=translations["manual_prefix"],
    )

    if not result:
        return redirect_with_message(translations["host_not_found"].format(ip=ip), "error")

    save_config_raw(config)

    state_label = translations["state_up"] if result["current_state"] == "up" else translations["state_down"]
    notify_label = (
        translations["telegram_sent"]
        if result["notified"]
        else translations["telegram_failed"]
    )
    message_type = "success" if result["notified"] else "error"

    if result["changed"]:
        return redirect_with_message(
            translations["manual_changed"].format(ip=ip, state=state_label, notify=notify_label),
            message_type,
        )

    return redirect_with_message(
        translations["manual_unchanged"].format(ip=ip, state=state_label, notify=notify_label),
        message_type,
    )


@app.route("/check_proxy", methods=["POST"])
def check_proxy():
    config = load_config_raw()
    settings = get_settings(config)
    translations = get_translations(settings)

    token, _ = load_telegram_settings()
    if not token:
        return redirect_with_message(translations["token_missing"].format(env_file=ENV_FILE), "error")

    proxy_settings = settings.copy()
    proxy_settings["proxy_enabled"] = True
    proxies = build_proxy_config(proxy_settings)
    if not proxies:
        return redirect_with_message(translations["proxy_invalid"], "error")

    try:
        bot_info = get_telegram_bot_info(token, proxies)
    except requests.exceptions.InvalidSchema as e:
        if "SOCKS" in str(e):
            return redirect_with_message(translations["socks_missing"], "error")
        return redirect_with_message(translations["proxy_error"].format(error=e), "error")
    except Exception as e:
        return redirect_with_message(translations["proxy_error"].format(error=e), "error")

    bot_name = bot_info.get("username") or bot_info.get("first_name") or "Telegram bot"
    return redirect_with_message(translations["proxy_ok"].format(bot_name=bot_name), "success")


@app.route("/save_proxy", methods=["POST"])
def save_proxy():
    proxy_ip = request.form.get("proxy_ip", "").strip()
    proxy_port = request.form.get("proxy_port", "").strip()
    proxy_enabled = bool(request.form.get("proxy_enabled"))

    config = load_config_raw()
    settings = get_settings(config)
    config["_settings"] = {
        "proxy_enabled": proxy_enabled,
        "proxy_ip": proxy_ip,
        "proxy_port": proxy_port,
        "language": settings["language"],
    }
    save_config_raw(config)
    return redirect("/")


@app.route("/set_language", methods=["POST"])
def set_language():
    language = normalize_language(request.form.get("language", DEFAULT_LANGUAGE))
    config = load_config_raw()
    settings = get_settings(config)
    settings["language"] = language
    config["_settings"] = settings
    save_config_raw(config)
    return redirect("/")


if __name__ == "__main__":
    t = threading.Thread(target=ping_worker, daemon=True)
    t.start()
    app.run(host="0.0.0.0", port=5001)
