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
- runtime logging is enabled for detected state, available actions, selected action, and failed clicks;
- added explicit logging when no actions are detected;
- the agent now merges the active reply keyboard with the current inline-keyboard message before perception and learning;
- this prevents the agent from losing the persistent reply keyboard when an inline menu message appears.

`telegram_client.py`:
- the agent no longer relies strictly on the single latest Telegram message for the keyboard;
- `get_latest()` scans recent bot-chat messages and returns the newest message that currently contains a keyboard;
- falls back to the newest message when no keyboard is present;
- added detection of the most recent `ReplyKeyboardMarkup` in recent bot messages;
- added `get_current_buttons()` to combine buttons from the current message with the persistent reply keyboard;
- added an in-memory `reply_keyboard_message` cache so a previously detected persistent Reply Keyboard remains available after its message leaves the recent-message window;
- new Reply Keyboard messages refresh the cache automatically.

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

The keyboard is treated as part of the perceived state/action space, so changing the keyboard changes the learned state rather than bypassing the learning system with hardcoded action sequences.

### Current UI perception model

Telegram can leave a persistent reply keyboard active while a newer bot message displays a separate inline keyboard. The agent therefore treats these as two layers of the actionable UI:
- the current message supplies its inline/reply buttons;
- the newest recent bot message containing `ReplyKeyboardMarkup` supplies the persistent navigation buttons;
- once discovered, the persistent Reply Keyboard is cached in `GameClient` and remains available even when its source message is older than the recent-message window;
- both are passed into perception as available actions;
- inline callback actions are clicked on their source message;
- reply-keyboard actions are sent as normal messages.

This is a perception/input fix only. It does not hardcode a route or force the agent to choose a particular action.

### Planned AI analyst layer

A separate AI analyst layer is planned on top of the existing Q-learning agent. Its role will be observation and knowledge extraction rather than direct control:
- analyze game messages, buttons, perceived state, selected actions, transitions, and rewards;
- identify useful game mechanics and consequences that are difficult to infer from raw Q-learning data alone;
- store durable observations/knowledge for later decisions;
- provide contextual information to the learning system without replacing autonomous action selection.

The AI analyst will not hardcode routes or bypass the self-learning architecture.

### Official game knowledge

Official skill documentation is being collected separately from learned observations.

- `data/knowledge/official/skills.md` created;
- currently contains official descriptions of Strength, Agility, Athletics, Perception, Attack, Defense, Dodge, Cutting, Slashing, Blunt, Piercing, Stealth, Lockpicking, Theft, General Crafting, and Weapon Forging;
- skill categories/names for Armor Forging, Alchemy, Cooking, Engineering, and Medicine are recorded as pending documentation;
- current character levels and temporary equipment/innate bonuses are not treated as permanent skill knowledge.

### Project structure commit

`4b493c846efdf60201c95302b7d9fea5f4b92f53`
