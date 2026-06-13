import html
import json
import os
import re
import secrets
import subprocess
import threading
import time
import uuid
from datetime import datetime
from urllib.parse import urlencode

import requests
from flask import Flask, has_request_context, jsonify, redirect, render_template, request

app = Flask(__name__)

CONFIG_FILE = "/root/ping_manager/config.json"
ENV_FILE = "/root/ping_manager/.env"
SCHEMA_VERSION = 2
DEFAULT_LANGUAGE = "en"
DEFAULT_WEBHOOK_INTERVAL = 60
DEFAULT_MISSED_HEARTBEATS = 2
CONFIG_LOCK = threading.RLock()
DEFAULT_SETTINGS = {
    "proxy_enabled": False,
    "proxy_ip": "",
    "proxy_port": "1080",
    "language": DEFAULT_LANGUAGE,
    "webhook_base_url": "",
    "trust_proxy_headers": False,
}
TELEGRAM_TIMEOUT = (5, 20)
DEVICE_TYPES = [
    ("linux", "Linux"),
    ("macos", "macOS"),
    ("windows", "Windows"),
    ("routeros", "RouterOS"),
    ("keenetic", "Keenetic (experimental)"),
    ("unifi_ap", "UniFi WiFi/AP (experimental)"),
    ("unifi_switch", "UniFi Switch (experimental)"),
]
DEVICE_TYPE_VALUES = {device_type for device_type, _ in DEVICE_TYPES}
TRANSLATIONS = {
    "en": {
        "html_lang": "en",
        "title": "Network Monitor",
        "header_title": "Ping Manager",
        "system_active": "System active",
        "language": "Language",
        "english": "English",
        "russian": "Russian",
        "service_settings": "Service settings",
        "proxy_settings": "SOCKS5 Proxy Settings for Telegram",
        "proxy_ip": "Proxy IP",
        "proxy_port": "Port",
        "proxy_enabled": "Enable proxy",
        "webhook_base_url": "Webhook base URL",
        "webhook_base_url_hint": "Example: http://raspberrypi.local:5001",
        "trust_proxy_headers": "Trust X-Forwarded-For headers",
        "save": "Save",
        "check_proxy": "Check proxy via Telegram",
        "ping_checks": "Ping checks",
        "edit_device": "Edit device",
        "add_device": "Add new ping check",
        "ip_address": "IP address",
        "check_interval": "Check interval (seconds)",
        "msg_up": "Message when AVAILABLE",
        "msg_down": "Message when UNAVAILABLE",
        "cancel": "Cancel",
        "save_changes": "Save changes",
        "add": "Add",
        "current_tasks": "Current ping checks",
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
        "interval_number": "Interval must be a number.",
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
        "webhook_devices": "Webhook devices",
        "add_webhook_device": "Add webhook device",
        "edit_webhook_device": "Edit webhook device",
        "device_name": "Device name",
        "location": "Location",
        "device_type": "Type",
        "heartbeat_interval": "Heartbeat interval (seconds)",
        "missed_heartbeats": "Missed heartbeats before offline",
        "effective_timeout": "Timeout",
        "last_seen": "Last heartbeat",
        "last_ip": "Last IP",
        "last_user_agent": "Last user agent",
        "instruction": "Instruction",
        "show_instruction": "Instruction",
        "rotate_token": "Rotate token",
        "webhook_url": "Webhook URL",
        "copy_paste_commands": "Copy/paste commands",
        "online": "Online",
        "offline": "Offline",
        "pending": "Pending",
        "never": "Never",
        "unknown": "Unknown",
        "device_name_empty": "Device name cannot be empty.",
        "device_not_found": "Device was not found.",
        "device_added": "Webhook device {name} added. Install the heartbeat command on the device.",
        "device_updated": "Webhook device {name} updated.",
        "device_deleted": "Webhook device deleted.",
        "token_rotated": "Webhook token rotated. Update the command on the device.",
        "webhook_received": "Webhook heartbeat received.",
        "windows_interval_error": "Windows Task Scheduler profile requires an interval of at least 60 seconds and a multiple of 60.",
        "timeout_seconds": "{seconds} sec.",
        "webhook_online_message": "Webhook device online: {name}{location}{ip}",
        "webhook_offline_message": "Webhook device offline: {name}{location}. Last heartbeat: {last_seen}. Timeout: {timeout}.",
        "location_part": " at {location}",
        "ip_part": " from {ip}",
        "instructions_for": "Instructions for {name}",
        "instruction_warning": "Note",
        "experimental_warning": "Experimental profile: persistence depends on firmware, installed packages, and vendor updates.",
        "linux_instruction": "Linux systemd timer",
        "macos_instruction": "macOS LaunchAgent",
        "windows_instruction": "Windows Task Scheduler",
        "routeros_instruction": "RouterOS scheduler",
        "keenetic_instruction": "Keenetic Entware cron",
        "unifi_instruction": "UniFi SSH cron",
        "install_command": "Install command",
        "remove_command": "Removal command",
        "no_ping_hosts": "No ping checks yet.",
        "no_webhook_devices": "No webhook devices yet.",
    },
    "ru": {
        "html_lang": "ru",
        "title": "Мониторинг Сети",
        "header_title": "Ping Manager",
        "system_active": "Система активна",
        "language": "Язык",
        "english": "Английский",
        "russian": "Русский",
        "service_settings": "Настройки сервиса",
        "proxy_settings": "Настройки SOCKS5 Прокси для Telegram",
        "proxy_ip": "IP прокси",
        "proxy_port": "Порт",
        "proxy_enabled": "Включить прокси",
        "webhook_base_url": "Базовый URL webhook",
        "webhook_base_url_hint": "Например: http://raspberrypi.local:5001",
        "trust_proxy_headers": "Доверять X-Forwarded-For",
        "save": "Сохранить",
        "check_proxy": "Проверить прокси через Telegram",
        "ping_checks": "Ping-проверки",
        "edit_device": "Редактировать устройство",
        "add_device": "Добавить ping-проверку",
        "ip_address": "IP адрес",
        "check_interval": "Интервал проверки (в секундах)",
        "msg_up": "Текст сообщения если ДОСТУПЕН",
        "msg_down": "Текст сообщения если НЕ ДОСТУПЕН",
        "cancel": "Отмена",
        "save_changes": "Сохранить изменения",
        "add": "Добавить",
        "current_tasks": "Текущие ping-проверки",
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
        "interval_number": "Интервал должен быть числом.",
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
        "webhook_devices": "Webhook-устройства",
        "add_webhook_device": "Добавить webhook-устройство",
        "edit_webhook_device": "Редактировать webhook-устройство",
        "device_name": "Название устройства",
        "location": "Место расположения",
        "device_type": "Тип",
        "heartbeat_interval": "Интервал heartbeat (секунды)",
        "missed_heartbeats": "Пропусков до offline",
        "effective_timeout": "Таймаут",
        "last_seen": "Последний heartbeat",
        "last_ip": "Последний IP",
        "last_user_agent": "Последний user agent",
        "instruction": "Инструкция",
        "show_instruction": "Инструкция",
        "rotate_token": "Сменить token",
        "webhook_url": "Webhook URL",
        "copy_paste_commands": "Команды для копирования",
        "online": "Онлайн",
        "offline": "Оффлайн",
        "pending": "Ожидание",
        "never": "Никогда",
        "unknown": "Неизвестно",
        "device_name_empty": "Название устройства не может быть пустым.",
        "device_not_found": "Устройство не найдено.",
        "device_added": "Webhook-устройство {name} добавлено. Установите heartbeat-команду на устройстве.",
        "device_updated": "Webhook-устройство {name} обновлено.",
        "device_deleted": "Webhook-устройство удалено.",
        "token_rotated": "Webhook token сменен. Обновите команду на устройстве.",
        "webhook_received": "Webhook heartbeat получен.",
        "windows_interval_error": "Для Windows Task Scheduler интервал должен быть не меньше 60 секунд и кратен 60.",
        "timeout_seconds": "{seconds} сек.",
        "webhook_online_message": "Webhook-устройство онлайн: {name}{location}{ip}",
        "webhook_offline_message": "Webhook-устройство оффлайн: {name}{location}. Последний heartbeat: {last_seen}. Таймаут: {timeout}.",
        "location_part": " в {location}",
        "ip_part": " с {ip}",
        "instructions_for": "Инструкция для {name}",
        "instruction_warning": "Важно",
        "experimental_warning": "Экспериментальный профиль: постоянство зависит от прошивки, установленных пакетов и обновлений производителя.",
        "linux_instruction": "Linux systemd timer",
        "macos_instruction": "macOS LaunchAgent",
        "windows_instruction": "Windows Task Scheduler",
        "routeros_instruction": "RouterOS scheduler",
        "keenetic_instruction": "Keenetic Entware cron",
        "unifi_instruction": "UniFi SSH cron",
        "install_command": "Команда установки",
        "remove_command": "Команда удаления",
        "no_ping_hosts": "Ping-проверок пока нет.",
        "no_webhook_devices": "Webhook-устройств пока нет.",
    },
}


def current_status_time():
    return datetime.now().strftime("%H:%M:%S %d.%m.%Y")


def timestamp_to_label(value, default=""):
    try:
        timestamp = float(value)
    except (TypeError, ValueError):
        return default

    if timestamp <= 0:
        return default

    return datetime.fromtimestamp(timestamp).strftime("%H:%M:%S %d.%m.%Y")


def normalize_language(language):
    if language in TRANSLATIONS:
        return language
    return DEFAULT_LANGUAGE


def normalize_bool(value):
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def normalize_int(value, default, minimum=None):
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = default

    if minimum is not None and number < minimum:
        return minimum
    return number


def get_settings(config):
    settings = DEFAULT_SETTINGS.copy()
    settings.update(config.get("_settings", {}))
    settings["language"] = normalize_language(settings.get("language", DEFAULT_LANGUAGE))
    settings["proxy_enabled"] = normalize_bool(settings.get("proxy_enabled", False))
    settings["trust_proxy_headers"] = normalize_bool(settings.get("trust_proxy_headers", False))
    settings["webhook_base_url"] = str(settings.get("webhook_base_url", "")).strip()
    return settings


def get_translations(settings):
    return TRANSLATIONS[normalize_language(settings.get("language", DEFAULT_LANGUAGE))]


def get_device_type_label(device_type):
    for value, label in DEVICE_TYPES:
        if value == device_type:
            return label
    return device_type


def normalize_device_type(device_type):
    if device_type in DEVICE_TYPE_VALUES:
        return device_type
    return "linux"


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


def load_env_file(path=None):
    if path is None:
        path = ENV_FILE

    variables = {}

    if not os.path.exists(path):
        return variables

    with open(path, "r", encoding="utf-8") as f:
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

    config = load_config_raw()
    settings = get_settings(config)
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


def default_ping_host():
    return {
        "interval": 60,
        "msg_up": TRANSLATIONS[DEFAULT_LANGUAGE]["default_msg_up"],
        "msg_down": TRANSLATIONS[DEFAULT_LANGUAGE]["default_msg_down"],
        "last_state": "unknown",
        "status_time": "",
        "last_check": 0,
    }


def build_default_config():
    return {
        "_schema_version": SCHEMA_VERSION,
        "_settings": DEFAULT_SETTINGS.copy(),
        "ping_hosts": {
            "192.168.0.1": default_ping_host(),
        },
        "webhook_devices": {},
    }


def normalize_ping_host(data):
    normalized = dict(data or {})
    normalized["interval"] = normalize_int(normalized.get("interval"), 60, minimum=5)
    normalized["msg_up"] = str(normalized.get("msg_up") or TRANSLATIONS[DEFAULT_LANGUAGE]["default_msg_up"])
    normalized["msg_down"] = str(normalized.get("msg_down") or TRANSLATIONS[DEFAULT_LANGUAGE]["default_msg_down"])
    if normalized.get("last_state") not in {"unknown", "up", "down"}:
        normalized["last_state"] = "unknown"
    normalized["status_time"] = str(normalized.get("status_time", ""))
    try:
        normalized["last_check"] = float(normalized.get("last_check", 0))
    except (TypeError, ValueError):
        normalized["last_check"] = 0
    return normalized


def normalize_webhook_device(device_id, data):
    normalized = dict(data or {})
    now_label = current_status_time()
    normalized["device_id"] = str(normalized.get("device_id") or device_id)
    normalized["name"] = str(normalized.get("name") or "Webhook device").strip()
    normalized["location"] = str(normalized.get("location") or "").strip()
    normalized["device_type"] = normalize_device_type(normalized.get("device_type", "linux"))
    normalized["interval_seconds"] = normalize_int(
        normalized.get("interval_seconds"),
        DEFAULT_WEBHOOK_INTERVAL,
        minimum=5,
    )
    normalized["missed_heartbeats"] = normalize_int(
        normalized.get("missed_heartbeats"),
        DEFAULT_MISSED_HEARTBEATS,
        minimum=1,
    )
    normalized["token"] = str(normalized.get("token") or secrets.token_urlsafe(32))
    if normalized.get("last_state") not in {"pending", "online", "offline"}:
        normalized["last_state"] = "pending"
    try:
        normalized["last_seen"] = float(normalized.get("last_seen", 0))
    except (TypeError, ValueError):
        normalized["last_seen"] = 0
    normalized["status_time"] = str(normalized.get("status_time", ""))
    normalized["last_ip"] = str(normalized.get("last_ip", ""))
    normalized["last_user_agent"] = str(normalized.get("last_user_agent", ""))
    normalized["created_at"] = str(normalized.get("created_at") or now_label)
    normalized["updated_at"] = str(normalized.get("updated_at") or normalized["created_at"])
    return normalized


def normalize_config(raw_config):
    raw_config = raw_config if isinstance(raw_config, dict) else {}

    if raw_config.get("_schema_version") == SCHEMA_VERSION:
        settings = get_settings(raw_config)
        ping_hosts = {
            str(ip): normalize_ping_host(data)
            for ip, data in raw_config.get("ping_hosts", {}).items()
        }
        webhook_devices = {
            str(device_id): normalize_webhook_device(str(device_id), data)
            for device_id, data in raw_config.get("webhook_devices", {}).items()
        }
        return {
            "_schema_version": SCHEMA_VERSION,
            "_settings": settings,
            "ping_hosts": ping_hosts,
            "webhook_devices": webhook_devices,
        }

    settings = DEFAULT_SETTINGS.copy()
    settings.update(raw_config.get("_settings", {}))
    settings = get_settings({"_settings": settings})

    legacy_hosts = {}
    for key, value in raw_config.items():
        if key.startswith("_") or key in {"ping_hosts", "webhook_devices"}:
            continue
        legacy_hosts[str(key)] = normalize_ping_host(value)

    if not legacy_hosts and isinstance(raw_config.get("ping_hosts"), dict):
        legacy_hosts = {
            str(ip): normalize_ping_host(data)
            for ip, data in raw_config.get("ping_hosts", {}).items()
        }

    return {
        "_schema_version": SCHEMA_VERSION,
        "_settings": settings,
        "ping_hosts": legacy_hosts,
        "webhook_devices": {},
    }


def load_config_raw():
    with CONFIG_LOCK:
        if not os.path.exists(CONFIG_FILE):
            default = build_default_config()
            save_config_raw(default)
            return default

        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            raw_config = json.load(f)

        normalized = normalize_config(raw_config)
        if normalized != raw_config:
            save_config_raw(normalized)
        return normalized


def save_config_raw(config):
    with CONFIG_LOCK:
        normalized = normalize_config(config)
        config_dir = os.path.dirname(CONFIG_FILE) or "."
        os.makedirs(config_dir, exist_ok=True)
        temp_path = f"{CONFIG_FILE}.tmp"

        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(normalized, f, indent=4, ensure_ascii=False)
            f.write("\n")

        os.replace(temp_path, CONFIG_FILE)


def get_config_ping_hosts(config):
    if "ping_hosts" in config:
        return config["ping_hosts"]
    return {k: v for k, v in config.items() if not k.startswith("_")}


def load_hosts_and_settings():
    config = load_config_raw()
    return config["ping_hosts"], get_settings(config)


def check_ping(ip):
    res = subprocess.run(
        ["ping", "-c", "2", "-W", "2", ip], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    return res.returncode == 0


def check_config_host(config, ip, notify=True, force_notify=False, notification_prefix=""):
    ping_hosts = get_config_ping_hosts(config)
    if ip not in ping_hosts:
        return None

    data = ping_hosts[ip]
    is_up = check_ping(ip)
    current_state = "up" if is_up else "down"
    previous_state = data.get("last_state", "unknown")

    data["last_check"] = time.time()

    changed = previous_state != current_state

    if changed:
        data["status_time"] = current_status_time()
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


def webhook_timeout_seconds(device):
    return int(device.get("interval_seconds", DEFAULT_WEBHOOK_INTERVAL)) * int(
        device.get("missed_heartbeats", DEFAULT_MISSED_HEARTBEATS)
    )


def build_webhook_notification(device, state, translations):
    location = ""
    if device.get("location"):
        location = translations["location_part"].format(location=device["location"])

    ip = ""
    if device.get("last_ip"):
        ip = translations["ip_part"].format(ip=device["last_ip"])

    if state == "online":
        return translations["webhook_online_message"].format(
            name=device["name"],
            location=location,
            ip=ip,
        )

    return translations["webhook_offline_message"].format(
        name=device["name"],
        location=location,
        last_seen=timestamp_to_label(device.get("last_seen"), translations["never"]),
        timeout=translations["timeout_seconds"].format(seconds=webhook_timeout_seconds(device)),
    )


def find_webhook_device_by_token(config, token):
    for device_id, device in config.get("webhook_devices", {}).items():
        if secrets.compare_digest(str(device.get("token", "")), str(token)):
            return device_id, device
    return None, None


def request_client_ip(settings):
    if settings.get("trust_proxy_headers"):
        forwarded = request.headers.get("X-Forwarded-For", "")
        if forwarded:
            return forwarded.split(",", 1)[0].strip()

        real_ip = request.headers.get("X-Real-IP", "")
        if real_ip:
            return real_ip.strip()

    return request.remote_addr or ""


def mark_webhook_seen(config, token, client_ip="", user_agent="", notify=True, current_time=None):
    device_id, device = find_webhook_device_by_token(config, token)
    if not device:
        return None

    settings = get_settings(config)
    translations = get_translations(settings)
    now = time.time() if current_time is None else current_time
    previous_state = device.get("last_state", "pending")

    device["last_seen"] = now
    device["last_ip"] = client_ip
    device["last_user_agent"] = user_agent[:250]
    device["updated_at"] = current_status_time()

    changed = previous_state != "online"
    notified = False
    if changed:
        device["last_state"] = "online"
        device["status_time"] = current_status_time()
        if notify:
            notified = send_telegram(build_webhook_notification(device, "online", translations))

    return {
        "device_id": device_id,
        "device": device,
        "previous_state": previous_state,
        "current_state": "online",
        "changed": changed,
        "notified": notified,
    }


def check_webhook_devices(config, current_time=None, notify=True):
    settings = get_settings(config)
    translations = get_translations(settings)
    now = time.time() if current_time is None else current_time
    changes = []

    for device_id, device in config.get("webhook_devices", {}).items():
        if device.get("last_state") == "pending" or not device.get("last_seen"):
            continue

        if device.get("last_state") == "offline":
            continue

        if now - float(device.get("last_seen", 0)) <= webhook_timeout_seconds(device):
            continue

        previous_state = device.get("last_state", "online")
        device["last_state"] = "offline"
        device["status_time"] = current_status_time()
        device["updated_at"] = device["status_time"]
        notified = False
        if notify:
            notified = send_telegram(build_webhook_notification(device, "offline", translations))

        changes.append(
            {
                "device_id": device_id,
                "previous_state": previous_state,
                "current_state": "offline",
                "notified": notified,
            }
        )

    return {"updated": bool(changes), "changes": changes}


def redirect_with_message(message, message_type="info", extra=None):
    query_data = {"message": message, "message_type": message_type}
    if extra:
        query_data.update(extra)
    query = urlencode(query_data)
    return redirect(f"/?{query}")


def parse_webhook_form(translations):
    name = request.form.get("name", "").strip()
    if not name:
        return None, translations["device_name_empty"]

    try:
        interval_seconds = int(request.form.get("interval_seconds", DEFAULT_WEBHOOK_INTERVAL))
        missed_heartbeats = int(request.form.get("missed_heartbeats", DEFAULT_MISSED_HEARTBEATS))
    except ValueError:
        return None, translations["interval_number"]

    if interval_seconds < 5 or missed_heartbeats < 1:
        return None, translations["interval_number"]

    device_type = normalize_device_type(request.form.get("device_type", "linux"))
    if device_type == "windows" and (interval_seconds < 60 or interval_seconds % 60 != 0):
        return None, translations["windows_interval_error"]

    return {
        "name": name,
        "location": request.form.get("location", "").strip(),
        "device_type": device_type,
        "interval_seconds": interval_seconds,
        "missed_heartbeats": missed_heartbeats,
    }, None


def safe_slug(value):
    value = re.sub(r"[^a-zA-Z0-9_-]+", "-", str(value).strip().lower())
    value = value.strip("-")
    return value[:48] or "device"


def shell_quote(value):
    return "'" + str(value).replace("'", "'\"'\"'") + "'"


def xml_escape(value):
    return html.escape(str(value), quote=True)


def routeros_escape(value):
    return str(value).replace("\\", "\\\\").replace('"', '\\"')


def format_routeros_interval(seconds):
    seconds = int(seconds)
    if seconds % 86400 == 0:
        return f"{seconds // 86400}d"
    if seconds % 3600 == 0:
        return f"{seconds // 3600}h"
    if seconds % 60 == 0:
        return f"{seconds // 60}m"
    return f"{seconds}s"


def cron_minutes(seconds):
    return max(1, (int(seconds) + 59) // 60)


def get_webhook_url(device, settings):
    base_url = settings.get("webhook_base_url", "").strip().rstrip("/")
    if not base_url and has_request_context():
        base_url = request.host_url.rstrip("/")

    path = f"/webhook/{device['token']}"
    if not base_url:
        return path
    return f"{base_url}{path}"


def instruction_step(title, command, description=""):
    return {"title": title, "command": command.strip(), "description": description}


def build_device_instructions(device, settings, translations):
    webhook_url = get_webhook_url(device, settings)
    quoted_url = shell_quote(webhook_url)
    escaped_url = xml_escape(webhook_url)
    routeros_url = routeros_escape(webhook_url)
    slug = safe_slug(device.get("name") or device.get("device_id"))
    interval = int(device.get("interval_seconds", DEFAULT_WEBHOOK_INTERVAL))
    device_type = normalize_device_type(device.get("device_type", "linux"))
    warning = ""
    steps = []

    if device_type == "linux":
        unit_name = f"ping-manager-heartbeat-{slug}"
        install = f"""
sudo tee /etc/systemd/system/{unit_name}.service >/dev/null <<'EOF'
[Unit]
Description=Ping Manager heartbeat for {slug}
Wants=network-online.target
After=network-online.target

[Service]
Type=oneshot
ExecStart=/usr/bin/curl -fsS --max-time 10 {quoted_url}
EOF

sudo tee /etc/systemd/system/{unit_name}.timer >/dev/null <<'EOF'
[Unit]
Description=Run Ping Manager heartbeat for {slug}

[Timer]
OnBootSec=30s
OnUnitActiveSec={interval}s
AccuracySec=1s
Unit={unit_name}.service

[Install]
WantedBy=timers.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now {unit_name}.timer
systemctl list-timers {unit_name}.timer
"""
        remove = f"""
sudo systemctl disable --now {unit_name}.timer
sudo rm -f /etc/systemd/system/{unit_name}.timer /etc/systemd/system/{unit_name}.service
sudo systemctl daemon-reload
"""
        steps = [
            instruction_step(translations["install_command"], install),
            instruction_step(translations["remove_command"], remove),
        ]
        title = translations["linux_instruction"]

    elif device_type == "macos":
        plist_name = f"com.pingmanager.heartbeat.{slug}.plist"
        install = f"""
mkdir -p "$HOME/Library/LaunchAgents"
cat > "$HOME/Library/LaunchAgents/{plist_name}" <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.pingmanager.heartbeat.{slug}</string>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/bin/curl</string>
    <string>-fsS</string>
    <string>--max-time</string>
    <string>10</string>
    <string>{escaped_url}</string>
  </array>
  <key>RunAtLoad</key>
  <true/>
  <key>StartInterval</key>
  <integer>{interval}</integer>
</dict>
</plist>
EOF

launchctl unload "$HOME/Library/LaunchAgents/{plist_name}" 2>/dev/null || true
launchctl load "$HOME/Library/LaunchAgents/{plist_name}"
launchctl list | grep "com.pingmanager.heartbeat.{slug}"
"""
        remove = f"""
launchctl unload "$HOME/Library/LaunchAgents/{plist_name}" 2>/dev/null || true
rm -f "$HOME/Library/LaunchAgents/{plist_name}"
"""
        steps = [
            instruction_step(translations["install_command"], install),
            instruction_step(translations["remove_command"], remove),
        ]
        title = translations["macos_instruction"]

    elif device_type == "windows":
        task_name = f"PingManager\\Heartbeat-{slug}"
        minutes = interval // 60
        command = (
            f'powershell.exe -NoProfile -ExecutionPolicy Bypass -Command '
            f'"try {{ Invoke-WebRequest -UseBasicParsing -TimeoutSec 10 -Uri '
            f"'{webhook_url}' | Out-Null }} catch {{ exit 1 }}\""
        )
        install = f"""
schtasks /Create /TN "{task_name}" /SC MINUTE /MO {minutes} /TR "{command}" /F
schtasks /Query /TN "{task_name}"
"""
        remove = f"""
schtasks /Delete /TN "{task_name}" /F
"""
        steps = [
            instruction_step(translations["install_command"], install),
            instruction_step(translations["remove_command"], remove),
        ]
        title = translations["windows_instruction"]

    elif device_type == "routeros":
        script_name = f"ping-manager-heartbeat-{slug}"
        routeros_interval = format_routeros_interval(interval)
        install = f"""
/system script add name={script_name} source="/tool fetch url=\\"{routeros_url}\\" keep-result=no output=none"
/system scheduler add name={script_name} interval={routeros_interval} on-event={script_name}
/system scheduler print where name={script_name}
"""
        remove = f"""
/system scheduler remove [find name={script_name}]
/system script remove [find name={script_name}]
"""
        steps = [
            instruction_step(translations["install_command"], install),
            instruction_step(translations["remove_command"], remove),
        ]
        title = translations["routeros_instruction"]

    elif device_type == "keenetic":
        minutes = cron_minutes(interval)
        warning = translations["experimental_warning"]
        install = f"""
opkg update
opkg install curl cronie
grep -q "Ping Manager heartbeat {slug}" /opt/etc/crontab || cat >> /opt/etc/crontab <<'EOF'
# Ping Manager heartbeat {slug}
*/{minutes} * * * * root /opt/bin/curl -fsS --max-time 10 {quoted_url} >/dev/null 2>&1
EOF
/opt/etc/init.d/S10cron restart
"""
        remove = f"""
sed -i '/Ping Manager heartbeat {slug}/,+1d' /opt/etc/crontab
/opt/etc/init.d/S10cron restart
"""
        steps = [
            instruction_step(translations["install_command"], install),
            instruction_step(translations["remove_command"], remove),
        ]
        title = translations["keenetic_instruction"]

    else:
        minutes = cron_minutes(interval)
        warning = translations["experimental_warning"]
        cron_file = f"/tmp/ping-manager-heartbeat-{slug}.cron"
        install = f"""
crontab -l > {cron_file} 2>/dev/null || true
grep -q "Ping Manager heartbeat {slug}" {cron_file} || echo "*/{minutes} * * * * /usr/bin/curl -fsS --max-time 10 {quoted_url} >/dev/null 2>&1 # Ping Manager heartbeat {slug}" >> {cron_file}
crontab {cron_file}
crontab -l | grep "Ping Manager heartbeat {slug}"
"""
        remove = f"""
crontab -l | grep -v "Ping Manager heartbeat {slug}" > {cron_file}
crontab {cron_file}
"""
        steps = [
            instruction_step(translations["install_command"], install),
            instruction_step(translations["remove_command"], remove),
        ]
        title = translations["unifi_instruction"]

    return {
        "title": title,
        "device": device,
        "webhook_url": webhook_url,
        "warning": warning,
        "steps": steps,
    }


def build_webhook_device_view(device, settings):
    view = dict(device)
    view["device_type_label"] = get_device_type_label(device.get("device_type"))
    view["last_seen_label"] = timestamp_to_label(device.get("last_seen"))
    view["effective_timeout"] = webhook_timeout_seconds(device)
    view["webhook_url"] = get_webhook_url(device, settings)
    return view


def collect_locations(webhook_devices):
    locations = {
        device.get("location", "").strip()
        for device in webhook_devices.values()
        if device.get("location", "").strip()
    }
    return sorted(locations, key=str.lower)


def ping_worker():
    while True:
        try:
            with CONFIG_LOCK:
                config = load_config_raw()
                updated = False
                current_time = time.time()

                for ip, data in config["ping_hosts"].items():
                    if current_time - data.get("last_check", 0) >= int(data["interval"]):
                        check_config_host(config, ip, notify=True)
                        updated = True

                if updated:
                    save_config_raw(config)

        except Exception as e:
            print(f"Ошибка в воркере пинга: {e}")

        time.sleep(1)


def webhook_worker():
    while True:
        try:
            with CONFIG_LOCK:
                config = load_config_raw()
                result = check_webhook_devices(config, notify=True)
                if result["updated"]:
                    save_config_raw(config)

        except Exception as e:
            print(f"Ошибка в webhook worker: {e}")

        time.sleep(1)


@app.route("/")
def index():
    config = load_config_raw()
    settings = get_settings(config)
    translations = get_translations(settings)
    hosts = config["ping_hosts"]
    webhook_devices = config["webhook_devices"]

    edit_ip = request.args.get("edit_ip", "")
    edit_host = hosts.get(edit_ip) if edit_ip else None
    edit_webhook_id = request.args.get("edit_webhook_id", "")
    edit_webhook_device = webhook_devices.get(edit_webhook_id) if edit_webhook_id else None
    instruction_device_id = request.args.get("instruction_device", "")
    instruction = None
    if instruction_device_id in webhook_devices:
        instruction = build_device_instructions(webhook_devices[instruction_device_id], settings, translations)

    webhook_devices_view = {
        device_id: build_webhook_device_view(device, settings)
        for device_id, device in webhook_devices.items()
    }

    return render_template(
        "index.html",
        hosts=hosts,
        webhook_devices=webhook_devices_view,
        settings=settings,
        t=translations,
        edit_ip=edit_ip,
        edit_host=edit_host,
        edit_webhook_id=edit_webhook_id,
        edit_webhook_device=edit_webhook_device,
        instruction=instruction,
        locations=collect_locations(webhook_devices),
        device_types=DEVICE_TYPES,
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
        settings = get_settings(config)
        translations = get_translations(settings)

        try:
            interval_value = int(interval)
        except ValueError:
            return redirect_with_message(translations["interval_number"], "error")

        config["ping_hosts"][ip] = normalize_ping_host(
            {
                "interval": interval_value,
                "msg_up": msg_up,
                "msg_down": msg_down,
                "last_state": "unknown",
                "status_time": "",
                "last_check": 0,
            }
        )
        save_config_raw(config)
    return redirect("/")


@app.route("/update_host", methods=["POST"])
def update_host():
    config = load_config_raw()
    translations = get_translations(get_settings(config))
    ping_hosts = config["ping_hosts"]
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

    if original_ip not in ping_hosts:
        return redirect_with_message(translations["host_not_found"].format(ip=original_ip), "error")

    data = ping_hosts[original_ip]
    data["interval"] = interval_value
    data["msg_up"] = msg_up
    data["msg_down"] = msg_down

    if new_ip != original_ip:
        if new_ip in ping_hosts:
            return redirect_with_message(translations["host_exists"].format(ip=new_ip), "error")
        del ping_hosts[original_ip]
        ping_hosts[new_ip] = data

    save_config_raw(config)
    return redirect_with_message(translations["host_updated"].format(ip=new_ip), "success")


@app.route("/delete/<ip>")
def delete_host(ip):
    config = load_config_raw()
    if ip in config["ping_hosts"]:
        del config["ping_hosts"][ip]
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


@app.route("/webhook/<token>", methods=["GET", "POST"])
def receive_webhook(token):
    with CONFIG_LOCK:
        config = load_config_raw()
        settings = get_settings(config)
        result = mark_webhook_seen(
            config,
            token,
            client_ip=request_client_ip(settings),
            user_agent=request.headers.get("User-Agent", ""),
            notify=True,
        )
        if not result:
            return jsonify({"status": "not_found"}), 404

        save_config_raw(config)

    return jsonify({"status": "ok"})


@app.route("/webhook_devices/add", methods=["POST"])
def add_webhook_device():
    config = load_config_raw()
    translations = get_translations(get_settings(config))
    form_data, error = parse_webhook_form(translations)
    if error:
        return redirect_with_message(error, "error")

    device_id = uuid.uuid4().hex
    now_label = current_status_time()
    config["webhook_devices"][device_id] = normalize_webhook_device(
        device_id,
        {
            **form_data,
            "device_id": device_id,
            "token": secrets.token_urlsafe(32),
            "last_state": "pending",
            "last_seen": 0,
            "status_time": "",
            "last_ip": "",
            "last_user_agent": "",
            "created_at": now_label,
            "updated_at": now_label,
        },
    )
    save_config_raw(config)
    return redirect_with_message(
        translations["device_added"].format(name=form_data["name"]),
        "success",
        {"instruction_device": device_id},
    )


@app.route("/webhook_devices/<device_id>/update", methods=["POST"])
def update_webhook_device(device_id):
    config = load_config_raw()
    translations = get_translations(get_settings(config))
    device = config["webhook_devices"].get(device_id)
    if not device:
        return redirect_with_message(translations["device_not_found"], "error")

    form_data, error = parse_webhook_form(translations)
    if error:
        return redirect_with_message(error, "error", {"edit_webhook_id": device_id})

    device.update(form_data)
    device["updated_at"] = current_status_time()
    config["webhook_devices"][device_id] = normalize_webhook_device(device_id, device)
    save_config_raw(config)
    return redirect_with_message(translations["device_updated"].format(name=form_data["name"]), "success")


@app.route("/webhook_devices/<device_id>/delete", methods=["POST"])
def delete_webhook_device(device_id):
    config = load_config_raw()
    translations = get_translations(get_settings(config))
    if device_id not in config["webhook_devices"]:
        return redirect_with_message(translations["device_not_found"], "error")

    del config["webhook_devices"][device_id]
    save_config_raw(config)
    return redirect_with_message(translations["device_deleted"], "success")


@app.route("/webhook_devices/<device_id>/rotate_token", methods=["POST"])
def rotate_webhook_token(device_id):
    config = load_config_raw()
    translations = get_translations(get_settings(config))
    device = config["webhook_devices"].get(device_id)
    if not device:
        return redirect_with_message(translations["device_not_found"], "error")

    device["token"] = secrets.token_urlsafe(32)
    device["last_state"] = "pending"
    device["last_seen"] = 0
    device["last_ip"] = ""
    device["last_user_agent"] = ""
    device["status_time"] = current_status_time()
    device["updated_at"] = device["status_time"]
    save_config_raw(config)
    return redirect_with_message(
        translations["token_rotated"],
        "success",
        {"instruction_device": device_id},
    )


@app.route("/instructions/<device_id>")
def show_device_instruction(device_id):
    config = load_config_raw()
    translations = get_translations(get_settings(config))
    if device_id not in config["webhook_devices"]:
        return redirect_with_message(translations["device_not_found"], "error")
    return redirect(f"/?{urlencode({'instruction_device': device_id})}")


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
    webhook_base_url = request.form.get("webhook_base_url", "").strip().rstrip("/")
    trust_proxy_headers = bool(request.form.get("trust_proxy_headers"))

    config = load_config_raw()
    settings = get_settings(config)
    config["_settings"] = {
        "proxy_enabled": proxy_enabled,
        "proxy_ip": proxy_ip,
        "proxy_port": proxy_port,
        "language": settings["language"],
        "webhook_base_url": webhook_base_url,
        "trust_proxy_headers": trust_proxy_headers,
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
    webhook_thread = threading.Thread(target=webhook_worker, daemon=True)
    webhook_thread.start()
    app.run(host="0.0.0.0", port=5001)
