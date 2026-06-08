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
        "_settings": {
            "proxy_enabled": False,
            "proxy_ip": "",
            "proxy_port": "1080",
            "language": "en",
        },
        "192.168.0.1": {
            "interval": 60,
            "msg_up": "Host is available",
            "msg_down": "Host access lost",
            "last_state": "unknown",
            "status_time": "",
            "last_check": 0,
        },
    }


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


def test_default_config_uses_english_language_and_generic_messages(app_module):
    config = app_module.load_config_raw()

    assert config["_settings"]["language"] == "en"
    assert config["192.168.0.1"]["msg_up"] == "Host is available"
    assert config["192.168.0.1"]["msg_down"] == "Host access lost"


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

    assert result["changed"] is True
    assert result["notified"] is True
    assert sample_config["192.168.0.1"]["last_state"] == "up"
    assert sample_config["192.168.0.1"]["last_check"] > 0
    assert sample_config["192.168.0.1"]["status_time"]
    send_telegram.assert_called_once_with("Host is available")


def test_check_config_host_manual_check_notifies_when_state_unchanged(app_module, sample_config, monkeypatch):
    sample_config["192.168.0.1"]["last_state"] = "up"
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
    assert "Ping Panel" in body
    assert "Add new device" in body
    assert "Host is available" in body


def test_set_language_switches_to_russian(app_module):
    client = app_module.app.test_client()

    response = client.post("/set_language", data={"language": "ru"}, follow_redirects=True)
    body = response.data.decode("utf-8")
    config = read_config(app_module)

    assert response.status_code == 200
    assert config["_settings"]["language"] == "ru"
    assert '<html lang="ru">' in body
    assert "Панель пинга" in body
    assert "Добавить новое устройство" in body


def test_update_host_preserves_state_and_moves_record_when_ip_changes(app_module, sample_config):
    sample_config["192.168.0.1"].update(
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

    assert response.status_code == 302
    assert "192.168.0.1" not in config
    assert config["192.168.0.2"]["interval"] == 120
    assert config["192.168.0.2"]["msg_up"] == "New up"
    assert config["192.168.0.2"]["msg_down"] == "New down"
    assert config["192.168.0.2"]["last_state"] == "up"
    assert config["192.168.0.2"]["status_time"] == "12:00:00 01.01.2026"
    assert config["192.168.0.2"]["last_check"] == 123


def test_manual_check_route_sends_prefixed_message(app_module, sample_config, monkeypatch):
    sample_config["192.168.0.1"]["last_state"] = "up"
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
