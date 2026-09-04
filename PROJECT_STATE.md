# PROJECT STATE

## 2026-09-04 — Explicit per-account Telegram authorization

Telegram authorization was changed from Telethon `start(phone=...)` to an explicit sequential login flow.

### Runtime behavior

`telegram_client.py` now:
- connects the session first;
- skips code entry when the session is already authorized;
- explicitly calls `send_code_request()` for a new session;
- prints when the login code request is sent;
- accepts the Telegram code for the specific account/session;
- handles Telegram 2FA when requested.

`main.py` still:
- starts only accounts with `enabled=true`;
- authorizes enabled accounts sequentially;
- runs enabled accounts concurrently after connection.

This makes it possible to distinguish a real Telegram code-request/delivery problem from a local session/login-flow problem.

### Account enable flags

Each account supports:
- `ACCOUNT_1_ENABLED=true/false`
- `ACCOUNT_2_ENABLED=true/false`
- `ACCOUNT_3_ENABLED=true/false`

Default is `true` when the variable is omitted.

### Current commits

- Config: `7d7b6ca139555a6dd6074d8946ff15dce765c4c0`
- Main: `dd7b50b30fcf40d9fcfcd4c6cc869eecac10dcae`
- Telegram authorization: `02833f912879a0ed839397d0a9ae66d54fe32af0`
