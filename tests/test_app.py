import importlib.util
import json
from pathlib import Path
from unittest.mock import Mock

import pytest
import requests


PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = PROJECT_ROOT / "ping_manager" / "app.py"


@pytest.fixture()
def app_module(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("ping_manager_app_under_test", APP_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    monkeypatch.setattr(module, "CONFIG_FILE", str(tmp_path / "config.json"))
    monkeypatch.setattr(module, "ENV_FILE", str(tmp_path / ".env"))
    module.app.template_folder = str(PROJECT_ROOT / "ping_manager" / "templates")
    module.app.config.update(TESTING=True)

    return module


@pytest.fixture()
def sample_config():
    return {
        "_schema_version": 2,
        "_settings": {
            "proxy_enabled": False,
            "proxy_ip": "",
            "proxy_port": "1080",
            "language": "en",
            "webhook_base_url": "http://monitor.local:5001",
            "trust_proxy_headers": False,
        },
        "ping_hosts": {
            "192.168.0.1": {
                "interval": 60,
                "msg_up": "Host is available",
                "msg_down": "Host access lost",
                "last_state": "unknown",
                "status_time": "",
                "last_check": 0,
            },
        },
        "webhook_devices": {},
    }


def webhook_device(app_module, **overrides):
    data = {
        "device_id": "device-1",
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
        "last_user_agent": "",
        "created_at": "12:00:00 01.01.2026",
        "updated_at": "12:00:00 01.01.2026",
    }
    data.update(overrides)
    return app_module.normalize_webhook_device(data["device_id"], data)


def write_config(app_module, config):
    Path(app_module.CONFIG_FILE).write_text(json.dumps(config), encoding="utf-8")


def read_config(app_module):
    return json.loads(Path(app_module.CONFIG_FILE).read_text(encoding="utf-8"))


def test_load_env_file_supports_comments_and_quotes(app_module):
    Path(app_module.ENV_FILE).write_text(
        """
        # Comment
        TOKEN="token-value"
        CHAT_ID='12345'
        BROKEN_LINE
        EMPTY=
        """,
        encoding="utf-8",
    )

    variables = app_module.load_env_file()

    assert variables["TOKEN"] == "token-value"
    assert variables["CHAT_ID"] == "12345"
    assert variables["EMPTY"] == ""
    assert "BROKEN_LINE" not in variables


def test_default_config_uses_v2_schema_english_language_and_generic_messages(app_module):
    config = app_module.load_config_raw()

    assert config["_schema_version"] == 2
    assert config["_settings"]["language"] == "en"
    assert config["_settings"]["webhook_base_url"] == ""
    assert config["ping_hosts"]["192.168.0.1"]["msg_up"] == "Host is available"
    assert config["ping_hosts"]["192.168.0.1"]["msg_down"] == "Host access lost"
    assert config["webhook_devices"] == {}


def test_load_config_migrates_legacy_flat_hosts(app_module):
    legacy_config = {
        "_settings": {
            "proxy_enabled": True,
            "proxy_ip": "127.0.0.1",
            "proxy_port": "1080",
            "language": "ru",
        },
        "192.168.0.1": {
            "interval": 60,
            "msg_up": "Up",
            "msg_down": "Down",
            "last_state": "up",
            "status_time": "12:00:00 01.01.2026",
            "last_check": 123,
        },
    }
    write_config(app_module, legacy_config)

    config = app_module.load_config_raw()
    raw_file = read_config(app_module)

    assert config["_schema_version"] == 2
    assert raw_file["_schema_version"] == 2
    assert "192.168.0.1" not in config
    assert config["ping_hosts"]["192.168.0.1"]["msg_up"] == "Up"
    assert config["ping_hosts"]["192.168.0.1"]["last_state"] == "up"
    assert config["_settings"]["language"] == "ru"
    assert config["_settings"]["webhook_base_url"] == ""
    assert config["webhook_devices"] == {}


@pytest.mark.parametrize(
    ("settings", "expected"),
    [
        ({"proxy_enabled": False, "proxy_ip": "127.0.0.1", "proxy_port": "1080"}, None),
        (
            {"proxy_enabled": True, "proxy_ip": "127.0.0.1", "proxy_port": "1080"},
            {"http": "socks5h://127.0.0.1:1080", "https": "socks5h://127.0.0.1:1080"},
        ),
        ({"proxy_enabled": True, "proxy_ip": "", "proxy_port": "1080"}, None),
        ({"proxy_enabled": True, "proxy_ip": "127.0.0.1", "proxy_port": "bad"}, None),
        ({"proxy_enabled": True, "proxy_ip": "127.0.0.1", "proxy_port": "70000"}, None),
    ],
)
def test_build_proxy_config(app_module, settings, expected):
    assert app_module.build_proxy_config(settings) == expected


def test_check_config_host_notifies_on_first_check(app_module, sample_config, monkeypatch):
    monkeypatch.setattr(app_module, "check_ping", lambda ip: True)
    send_telegram = Mock(return_value=True)
    monkeypatch.setattr(app_module, "send_telegram", send_telegram)

    result = app_module.check_config_host(sample_config, "192.168.0.1", notify=True)
    host = sample_config["ping_hosts"]["192.168.0.1"]

    assert result["changed"] is True
    assert result["notified"] is True
    assert host["last_state"] == "up"
    assert host["last_check"] > 0
    assert host["status_time"]
    send_telegram.assert_called_once_with("Host is available")


def test_check_config_host_manual_check_notifies_when_state_unchanged(app_module, sample_config, monkeypatch):
    sample_config["ping_hosts"]["192.168.0.1"]["last_state"] = "up"
    monkeypatch.setattr(app_module, "check_ping", lambda ip: True)
    send_telegram = Mock(return_value=True)
    monkeypatch.setattr(app_module, "send_telegram", send_telegram)

    result = app_module.check_config_host(
        sample_config,
        "192.168.0.1",
        notify=True,
        force_notify=True,
        notification_prefix="Manual check: ",
    )

    assert result["changed"] is False
    assert result["notified"] is True
    send_telegram.assert_called_once_with("Manual check: Host is available")


def test_send_telegram_falls_back_to_direct_send_when_socks_support_is_missing(app_module, sample_config, monkeypatch):
    sample_config["_settings"].update(
        {
            "proxy_enabled": True,
            "proxy_ip": "127.0.0.1",
            "proxy_port": "1080",
        }
    )
    write_config(app_module, sample_config)
    Path(app_module.ENV_FILE).write_text("TOKEN=token\nCHAT_ID=123\n", encoding="utf-8")

    calls = []

    def fake_post(url, json, proxies=None, timeout=None):
        calls.append({"url": url, "json": json, "proxies": proxies, "timeout": timeout})
        if proxies:
            raise requests.exceptions.InvalidSchema("Missing dependencies for SOCKS support.")

        response = Mock()
        response.json.return_value = {"ok": True}
        response.raise_for_status.return_value = None
        return response

    monkeypatch.setattr(app_module.requests, "post", fake_post)

    assert app_module.send_telegram("test") is True
    assert len(calls) == 2
    assert calls[0]["proxies"]["https"] == "socks5h://127.0.0.1:1080"
    assert calls[1]["proxies"] is None


def test_index_renders_english_by_default(app_module):
    client = app_module.app.test_client()

    response = client.get("/")
    body = response.data.decode("utf-8")

    assert response.status_code == 200
    assert '<html lang="en">' in body
    assert "Ping Manager" in body
    assert "Add new ping check" in body
    assert "Webhook devices" in body
    assert "Host is available" in body


def test_set_language_switches_to_russian(app_module):
    client = app_module.app.test_client()

    response = client.post("/set_language", data={"language": "ru"}, follow_redirects=True)
    body = response.data.decode("utf-8")
    config = read_config(app_module)

    assert response.status_code == 200
    assert config["_settings"]["language"] == "ru"
    assert '<html lang="ru">' in body
    assert "Ping Manager" in body
    assert "Добавить ping-проверку" in body


def test_update_host_preserves_state_and_moves_record_when_ip_changes(app_module, sample_config):
    sample_config["ping_hosts"]["192.168.0.1"].update(
        {
            "last_state": "up",
            "status_time": "12:00:00 01.01.2026",
            "last_check": 123,
        }
    )
    write_config(app_module, sample_config)
    client = app_module.app.test_client()

    response = client.post(
        "/update_host",
        data={
            "original_ip": "192.168.0.1",
            "ip": "192.168.0.2",
            "interval": "120",
            "msg_up": "New up",
            "msg_down": "New down",
        },
        follow_redirects=False,
    )
    config = read_config(app_module)
    ping_hosts = config["ping_hosts"]

    assert response.status_code == 302
    assert "192.168.0.1" not in ping_hosts
    assert ping_hosts["192.168.0.2"]["interval"] == 120
    assert ping_hosts["192.168.0.2"]["msg_up"] == "New up"
    assert ping_hosts["192.168.0.2"]["msg_down"] == "New down"
    assert ping_hosts["192.168.0.2"]["last_state"] == "up"
    assert ping_hosts["192.168.0.2"]["status_time"] == "12:00:00 01.01.2026"
    assert ping_hosts["192.168.0.2"]["last_check"] == 123


def test_manual_check_route_sends_prefixed_message(app_module, sample_config, monkeypatch):
    sample_config["ping_hosts"]["192.168.0.1"]["last_state"] = "up"
    write_config(app_module, sample_config)
    monkeypatch.setattr(app_module, "check_ping", lambda ip: True)
    send_telegram = Mock(return_value=True)
    monkeypatch.setattr(app_module, "send_telegram", send_telegram)
    client = app_module.app.test_client()

    response = client.post("/check_host", data={"ip": "192.168.0.1"}, follow_redirects=True)
    body = response.data.decode("utf-8")

    assert response.status_code == 200
    assert "Manual check 192.168.0.1" in body
    send_telegram.assert_called_once_with("Manual check: Host is available")


def test_check_proxy_uses_configured_proxy_and_token(app_module, sample_config, monkeypatch):
    sample_config["_settings"].update(
        {
            "proxy_ip": "127.0.0.1",
            "proxy_port": "1080",
        }
    )
    write_config(app_module, sample_config)
    Path(app_module.ENV_FILE).write_text("TOKEN=token\nCHAT_ID=123\n", encoding="utf-8")
    get_bot_info = Mock(return_value={"username": "test_bot"})
    monkeypatch.setattr(app_module, "get_telegram_bot_info", get_bot_info)
    client = app_module.app.test_client()

    response = client.post("/check_proxy", follow_redirects=True)
    body = response.data.decode("utf-8")

    assert response.status_code == 200
    assert "SOCKS5 proxy works" in body
    get_bot_info.assert_called_once_with(
        "token",
        {"http": "socks5h://127.0.0.1:1080", "https": "socks5h://127.0.0.1:1080"},
    )


def test_add_webhook_device_route_creates_pending_device_and_shows_instruction(app_module, sample_config):
    write_config(app_module, sample_config)
    client = app_module.app.test_client()

    response = client.post(
        "/webhook_devices/add",
        data={
            "name": "NAS",
            "location": "Rack",
            "device_type": "linux",
            "interval_seconds": "60",
            "missed_heartbeats": "2",
        },
        follow_redirects=True,
    )
    body = response.data.decode("utf-8")
    config = read_config(app_module)
    devices = config["webhook_devices"]
    device = next(iter(devices.values()))

    assert response.status_code == 200
    assert len(devices) == 1
    assert device["name"] == "NAS"
    assert device["location"] == "Rack"
    assert device["last_state"] == "pending"
    assert device["token"]
    assert "Instructions for NAS" in body
    assert "systemctl enable --now" in body


def test_webhook_unknown_token_returns_404(app_module, sample_config):
    write_config(app_module, sample_config)
    client = app_module.app.test_client()

    response = client.get("/webhook/missing")

    assert response.status_code == 404


def test_webhook_heartbeat_marks_online_and_does_not_repeat_notifications(app_module, sample_config, monkeypatch):
    device = webhook_device(app_module)
    sample_config["webhook_devices"] = {device["device_id"]: device}
    write_config(app_module, sample_config)
    send_telegram = Mock(return_value=True)
    monkeypatch.setattr(app_module, "send_telegram", send_telegram)
    client = app_module.app.test_client()

    response = client.get("/webhook/secret-token", headers={"User-Agent": "curl-test"})
    config = read_config(app_module)
    updated = config["webhook_devices"]["device-1"]

    assert response.status_code == 200
    assert response.json == {"status": "ok"}
    assert updated["last_state"] == "online"
    assert updated["last_seen"] > 0
    assert updated["last_ip"] == "127.0.0.1"
    assert updated["last_user_agent"] == "curl-test"
    send_telegram.assert_called_once()
    assert "Webhook device online: NAS at Rack from 127.0.0.1" == send_telegram.call_args.args[0]

    response = client.post("/webhook/secret-token")

    assert response.status_code == 200
    assert send_telegram.call_count == 1


def test_webhook_heartbeat_uses_forwarded_ip_only_when_enabled(app_module, sample_config, monkeypatch):
    sample_config["_settings"]["trust_proxy_headers"] = True
    device = webhook_device(app_module)
    sample_config["webhook_devices"] = {device["device_id"]: device}
    write_config(app_module, sample_config)
    monkeypatch.setattr(app_module, "send_telegram", Mock(return_value=True))
    client = app_module.app.test_client()

    response = client.get("/webhook/secret-token", headers={"X-Forwarded-For": "10.10.10.5, 127.0.0.1"})
    config = read_config(app_module)

    assert response.status_code == 200
    assert config["webhook_devices"]["device-1"]["last_ip"] == "10.10.10.5"


def test_webhook_offline_checker_skips_pending_and_notifies_online_timeout(app_module, sample_config, monkeypatch):
    online_device = webhook_device(
        app_module,
        device_id="online-device",
        token="online-token",
        name="Server",
        last_state="online",
        last_seen=100,
        interval_seconds=60,
        missed_heartbeats=2,
    )
    pending_device = webhook_device(
        app_module,
        device_id="pending-device",
        token="pending-token",
        name="New device",
        last_state="pending",
        last_seen=0,
    )
    sample_config["webhook_devices"] = {
        "online-device": online_device,
        "pending-device": pending_device,
    }
    send_telegram = Mock(return_value=True)
    monkeypatch.setattr(app_module, "send_telegram", send_telegram)

    result = app_module.check_webhook_devices(sample_config, current_time=221, notify=True)

    assert result["updated"] is True
    assert result["changes"] == [
        {
            "device_id": "online-device",
            "previous_state": "online",
            "current_state": "offline",
            "notified": True,
        }
    ]
    assert sample_config["webhook_devices"]["online-device"]["last_state"] == "offline"
    assert sample_config["webhook_devices"]["pending-device"]["last_state"] == "pending"
    send_telegram.assert_called_once()
    assert "Webhook device offline: Server at Rack." in send_telegram.call_args.args[0]


@pytest.mark.parametrize(
    ("device_type", "expected"),
    [
        ("linux", "systemctl enable --now"),
        ("macos", "launchctl load"),
        ("windows", "schtasks /Create"),
        ("routeros", "/system scheduler add"),
    ],
)
def test_instruction_generator_for_stable_profiles(app_module, sample_config, device_type, expected):
    device = webhook_device(app_module, device_type=device_type, interval_seconds=60)
    instructions = app_module.build_device_instructions(
        device,
        app_module.get_settings(sample_config),
        app_module.TRANSLATIONS["en"],
    )

    command_text = "\n".join(step["command"] for step in instructions["steps"])

    assert "http://monitor.local:5001/webhook/secret-token" in instructions["webhook_url"]
    assert expected in command_text


def test_windows_profile_requires_minute_interval(app_module, sample_config):
    write_config(app_module, sample_config)
    client = app_module.app.test_client()

    response = client.post(
        "/webhook_devices/add",
        data={
            "name": "Win host",
            "location": "Office",
            "device_type": "windows",
            "interval_seconds": "30",
            "missed_heartbeats": "2",
        },
        follow_redirects=True,
    )
    body = response.data.decode("utf-8")
    config = read_config(app_module)

    assert response.status_code == 200
    assert "Windows Task Scheduler profile requires" in body
    assert config["webhook_devices"] == {}


def test_rotate_webhook_token_resets_device_to_pending_and_shows_instruction(app_module, sample_config):
    device = webhook_device(app_module, last_state="online", last_seen=1000, last_ip="10.0.0.5")
    sample_config["webhook_devices"] = {device["device_id"]: device}
    write_config(app_module, sample_config)
    client = app_module.app.test_client()

    response = client.post("/webhook_devices/device-1/rotate_token", follow_redirects=True)
    body = response.data.decode("utf-8")
    config = read_config(app_module)
    updated = config["webhook_devices"]["device-1"]

    assert response.status_code == 200
    assert updated["token"] != "secret-token"
    assert updated["last_state"] == "pending"
    assert updated["last_seen"] == 0
    assert updated["last_ip"] == ""
    assert "Webhook token rotated" in body
    assert "Instructions for NAS" in body
