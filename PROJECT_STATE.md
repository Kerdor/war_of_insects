# PROJECT STATE

## 2026-09-04 — Runtime fixes, self-learning loop, development runner and project structure

### Current structure

Application code is grouped into the `bot/` package instead of being kept as many Python files in the repository root.

```text
war_of_insects/
├── bot/
│   ├── __init__.py
│   ├── agent.py
│   ├── learning.py
│   ├── memory.py
│   ├── models.py
│   ├── perception.py
│   ├── reward.py
│   ├── stats.py
│   ├── strategy.py
│   ├── telegram_client.py
│   └── transitions.py
├── config.py
├── dev_runner.py
├── main.py
├── .env.example
├── .gitignore
├── requirements.txt
├── README.md
└── data/
```

`main.py`, `config.py`, and `dev_runner.py` remain at the root as entry point, configuration, and development runner.

### Runtime fixes

`learning.py`:
- fixed unpacking of `TransitionMemory.predict()` result;
- transition prediction returns `(count, next_state, average_reward)`.

`main.py`:
- fixed cleanup check to use the underlying Telethon client's `is_connected()`.

`agent.py` / `perception.py`:
- fixed `Start parameter invalid (caused by StartBotRequest)` from Telegram `KeyboardButtonSwitchInline` buttons;
- SwitchInline buttons are ignored;
- reply-keyboard actions are sent as normal messages;
- runtime logging is enabled for detected state, available actions, selected action, and failed clicks.

### Multi-account behavior

- Accounts authorize sequentially.
- Already authorized sessions skip code entry.
- Enabled accounts run concurrently after authorization.
- `ACCOUNT_N_ENABLED=true/false` controls each account.

### Development runner

`dev_runner.py`:
- starts `main.py`;
- runs `git pull` every 5 seconds;
- detects a new `HEAD` commit;
- restarts `main.py` when code changes;
- keeps the runner alive across restarts;
- does not modify `.env` or Telegram session files.

### Learning architecture

The current agent uses:
- perception/state normalization;
- Q-learning;
- transition memory;
- strategy memory;
- experience memory;
- reward calculation;
- per-account runtime context;
- learning statistics.

### Project structure commit

`4b493c846efdf60201c95302b7d9fea5f4b92f53`
