# PROJECT STATE

## 2026-09-04 — Per-account enable flags

Added independent account enable/disable control for up to three Telegram accounts.

### Configuration

Each account now supports:
- `ACCOUNT_1_ENABLED=true/false`
- `ACCOUNT_2_ENABLED=true/false`
- `ACCOUNT_3_ENABLED=true/false`

Default is `true` when the variable is omitted.

### Runtime behavior

`main.py` now:
- starts only accounts with `enabled=true`;
- keeps Telegram authorization/connect sequence sequential;
- runs enabled accounts concurrently after connection;
- prints the enabled accounts at startup.

### Current commits

- Config: `7d7b6ca139555a6dd6074d8946ff15dce765c4c0`
- Main: `dd7b50b30fcf40d9fcfcd4c6cc869eecac10dcae`

### Example `.env`

```env
ACCOUNT_1_ENABLED=true
ACCOUNT_2_ENABLED=true
ACCOUNT_3_ENABLED=false
```

To temporarily disable account 3, set `ACCOUNT_3_ENABLED=false`; its phone/session values can remain configured.
