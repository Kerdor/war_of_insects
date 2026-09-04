# PROJECT STATE

## 2026-09-04 — Runtime fixes, self-learning loop, development runner and project structure

### Current structure

Application code is grouped into the `bot/` package. Official game knowledge is stored separately from learned observations.

```text
war_of_insects/
├── bot/
├── data/
│   └── knowledge/
│       ├── official/
│       │   ├── README.md
│       │   ├── commands.md
│       │   ├── basics/
│       │   ├── combat/
│       │   ├── exploration/
│       │   ├── items/
│       │   ├── crafting/
│       │   ├── clans/
│       │   ├── tournaments/
│       │   ├── squad/
│       │   └── source pages (*.md)
│       └── learned/
├── config.py
├── dev_runner.py
└── main.py
```

### Runtime fixes

- `learning.py`: fixed unpacking of `TransitionMemory.predict()`; prediction returns `(count, next_state, average_reward)`.
- `main.py`: cleanup uses the underlying Telethon client's `is_connected()`.
- `agent.py` / `perception.py`: SwitchInline buttons are ignored; reply-keyboard actions are sent as messages; state/action/failure logging is enabled; persistent reply keyboard is merged with the current inline keyboard.
- `telegram_client.py`: recent messages are scanned for keyboards; the persistent `ReplyKeyboardMarkup` is cached; `get_current_buttons()` combines current and persistent actions.

### Multi-account behavior

- Accounts authorize sequentially.
- Already authorized sessions skip code entry.
- Enabled accounts run concurrently after authorization.
- `ACCOUNT_N_ENABLED=true/false` controls each account.

### Development runner

`dev_runner.py` starts `main.py`, polls `git pull` every 5 seconds, detects a new HEAD and restarts the application without modifying `.env` or Telegram session files.

### Learning architecture

The agent uses perception/state normalization, Q-learning, transition memory, strategy memory, experience memory, reward calculation, per-account runtime context and learning statistics.

Q-learning remains responsible for autonomous action selection. The planned Qwen analyst observes gameplay and extracts durable knowledge instead of hardcoding routes.

### Knowledge architecture

Knowledge is intentionally divided into:

- `data/knowledge/official/` — trusted/reference information from the official game documentation and tutorial;
- `data/knowledge/learned/` — future observations, hypotheses, discovered mechanics, action consequences and other experience-derived information.

Official source pages are retained as archival/context documents. For Qwen retrieval, the same information is additionally normalized into small topical files. This is preferred over putting everything into a few giant Markdown documents because retrieval can select a narrow concept without loading an entire handbook page.

### Qwen-friendly official knowledge structure — 2026-09-04

Added `data/knowledge/official/README.md` as the knowledge map and `data/knowledge/official/commands.md` as a command-oriented lookup table.

Normalized topics:
- `basics/game_overview.md`
- `basics/status.md`
- `basics/body.md`
- `basics/skills.md`
- `exploration/world.md`
- `exploration/locations.md`
- `combat/combat.md`
- `combat/damage.md`
- `items/overview.md`
- `items/storage.md`
- `items/food.md`
- `items/potions.md`
- `items/weapons.md`
- `items/trading.md`
- `crafting/crafting.md`
- `clans/overview.md`
- `clans/rating.md`
- `clans/buildings.md`
- `clans/roles_permissions.md`
- `tournaments/tournaments.md`
- `squad/squad.md`

The original source documents remain available:
- `tutorial.md`
- `guide.md`
- `game_mechanics.md`
- `exploration.md`
- `items.md`
- `skills.md`
- `trading_crafting_clans_tournaments_squad.md`

### Documentation history

- Tutorial knowledge: commit `79e3d8bfaf2775506ab265889a4b686dd4407cf7`.
- Exploration source page: commit `54f42c54964b684ffd5c80819d6a9f0f52d55fe5`.
- Items source page: commit `2ed86b547c645acdc3d2d6e5f36270fc1273115c`.
- Trading/crafting/clans/tournaments/squad source page: commit `d379c6a4310e7863375be660865d6474a4d7ae57`.
- Qwen normalization index: commit `ebbf14548f83a5916553fa4c3da72465aa953071`.
- Qwen command index: commit `2a4803f190582986a40c9a8f43137cfc23754af6`.

### Design decision

Do not delete the original source pages. They are the canonical archival layer. The normalized files are the retrieval layer. This gives Qwen both fast narrow retrieval and broader source context when necessary.
