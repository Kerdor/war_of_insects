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

Official source pages are retained as archival/context documents. The normalized layer is a retrieval layer, not a summary layer: it must preserve the useful detail from the official source while splitting large pages into focused thematic documents.

### Qwen-friendly official knowledge structure — 2026-09-04

The first normalized pass was too compressed for reliable reasoning. It has now been corrected: detailed mechanics are kept in topical files instead of being reduced to short summaries.

Current combat retrieval structure:
- `combat/damage.md` — navigation/index only;
- `combat/damage_types.md` — detailed four damage types, mixed damage and stat relationships;
- `combat/damage_effects.md` — bleeding, amputation, fractures and piercing;
- `combat/armor.md` — body coverage, independent armor checks, damage calculation example and armor classes;
- `combat/body_damage.md` — vital body parts, limbs, blood, unconsciousness, limb loss and restoration.

`basics/skills.md` was expanded from a short summary into a detailed reference containing the official descriptions, effects and training methods for the ordinary core, combat, weapon, stealth/theft, crafting and science skills. The original `official/skills.md` remains the source document, including the separate innate-skill section.

The standard for future normalized files is now:
- preserve source detail rather than summarizing it away;
- split only along meaningful retrieval boundaries;
- keep conditions, effects, requirements, restrictions, exceptions and examples;
- add lightweight frontmatter with stable `id`, `type`, `domain`, `source`, `keywords` and `related` fields;
- use index files only for navigation, not as replacements for detailed knowledge.

### Existing normalized topics

- `basics/game_overview.md`
- `basics/status.md`
- `basics/body.md`
- `basics/skills.md`
- `exploration/world.md`
- `exploration/locations.md`
- `combat/combat.md`
- `combat/damage.md`
- `combat/damage_types.md`
- `combat/damage_effects.md`
- `combat/armor.md`
- `combat/body_damage.md`
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
- `commands.md`

### Documentation history

- Tutorial knowledge: commit `79e3d8bfaf2775506ab265889a4b686dd4407cf7`.
- Exploration source page: commit `54f42c54964b684ffd5c80819d6a9f0f52d55fe5`.
- Items source page: commit `2ed86b547c645acdc3d2d6e5f36270fc1273115c`.
- Trading/crafting/clans/tournaments/squad source page: commit `d379c6a4310e7863375be660865d6474a4d7ae57`.
- Latest combat expansion: commit `7a79d7ed373ea80bfc54b1c6faf7fdc5abeb6cfb`.
- Latest detailed skills restoration: commit `b61d5389a022cd81840991ac021670bdfd2237c0`.
- Latest knowledge index standard: commit `5a09af9013e4fcf01616840b3aa6bbec71696fbb`.

### Design decision

Do not delete the original source pages. They are the canonical archival layer. The normalized files are the retrieval layer and should contain the same meaningful detail, only reorganized for targeted retrieval. This gives Qwen both fast narrow retrieval and broader source context when necessary.
