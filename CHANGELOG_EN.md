# Changelog

## 2026-06-14

- Added reverse webhook device checks: each device gets a personal URL with a secret token.
- Added `config.json` schema v2 with `ping_hosts`, `webhook_devices`, `_schema_version`, `webhook_base_url`, and `trust_proxy_headers`.
- Added automatic migration from the old flat `config.json` format to schema v2 on first startup.
- Switched config writes to atomic `os.replace()` guarded by a shared `threading.RLock`.
- Added `GET|POST /webhook/<token>` heartbeat endpoint.
- Added a webhook worker that marks devices `offline` when heartbeat is missing longer than `interval_seconds * missed_heartbeats`.
- Added WebUI forms and table for webhook devices: name, location, type, interval, missed heartbeats, status, last heartbeat, and last IP.
- Added `Webhook base URL` to WebUI settings.
- Added generated setup instructions and ready-to-copy commands for Linux, macOS, Windows, and RouterOS.
- Added experimental instructions for Keenetic and UniFi.
- Added webhook token rotation with device reset to `pending`.
- Expanded automated tests for config migration, webhook routes, online/offline transitions, instructions, Windows validation, and ping-check regression.
- Updated Russian and English documentation.

## 2026-06-09

- Added `pytest` automated tests and GitHub Actions workflow to run tests on push/PR.
- Fixed `.env` loading: env file path is now resolved when `load_env_file()` is called instead of being fixed at module import time.
- Added bilingual WebUI: English / Russian, with English as the default language.
- Selected UI language is stored in `_settings.language`.
- Removed personal IP/text values from WebUI placeholders and default config; defaults now use `192.168.0.1`, `Host is available`, `Host access lost`.
- Added editing for existing hosts in WebUI.
- First check for a new IP now sends a Telegram message even when previous state was `unknown`.
- Manual IP check now always sends a Telegram message with the `Manual check: ` prefix in English UI mode.
- Added manual check for every IP in WebUI.
- Added manual SOCKS5 proxy check via Telegram API in WebUI.
- Shared host-check logic is now used by both the background worker and manual check button.
- Moved Telegram settings `TOKEN` and `CHAT_ID` from `app.py` to `/root/ping_manager/.env`.
- Added example environment file `ping_manager/.env.example`.
- systemd unit now loads `/root/ping_manager/.env` via `EnvironmentFile`.
- Fixed Telegram sending after adding SOCKS5 proxy support.
- Added proxy settings validation: empty IP, invalid port, and out-of-range port no longer break sending.
- SOCKS5 uses `socks5h://`, so Telegram DNS resolution also goes through the proxy.
- Added fallback to direct sending when proxy is unavailable or SOCKS support (`python3-socks` / `PySocks`) is not installed.
- Added HTTP and Telegram API response checks so send errors are no longer silently ignored.
- Removed `parse_mode=Markdown` from Telegram messages so custom notification text is not broken by Markdown characters.
