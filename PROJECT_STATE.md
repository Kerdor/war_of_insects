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

The first normalized pass was too compressed for reliable reasoning. The entire normalized topic layer has now been expanded so that the topic files contain substantive rules, conditions, effects, requirements, restrictions, examples and operational commands instead of short summaries.

Current combat retrieval structure:
- `combat/combat.md` — detailed combat model and relationships between skills, body state, equipment, effects, pursuit and outcomes;
- `combat/damage.md` — navigation/index only;
- `combat/damage_types.md` — detailed four damage types, mixed damage and stat relationships;
- `combat/damage_effects.md` — bleeding, amputation, fractures and piercing;
- `combat/armor.md` — body coverage, independent armor checks, damage calculation example and armor classes;
- `combat/body_damage.md` — vital body parts, limbs, blood, unconsciousness, limb loss and restoration.

`basics/skills.md` remains the detailed skill reference, including official descriptions, effects and training methods for ordinary core, combat, weapon, stealth/theft, crafting and science skills. The original `official/skills.md` remains the source document, including the separate innate-skill section.

The rest of the normalized topic layer has also been expanded from compressed summaries into detailed retrieval documents:
- `basics/game_overview.md`
- `basics/status.md`
- `basics/body.md`
- `exploration/world.md`
- `exploration/locations.md`
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

Index-oriented files remain intentionally concise:
- `official/README.md` — map of the knowledge base;
- `official/commands.md` — command-oriented lookup;
- `combat/damage.md` — combat-damage navigation.

### Retrieval document standard

Every substantive normalized document should:
- preserve meaningful source detail rather than summarizing it away;
- split only along meaningful retrieval boundaries;
- keep conditions, effects, requirements, restrictions, exceptions and examples;
- use lightweight frontmatter with stable `id`, `type`, `domain`, `source`, `keywords` and `related` fields;
- use index files only for navigation;
- avoid replacing authoritative source details with guesses when the source is ambiguous or internally inconsistent.

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
- Complete normalized knowledge expansion: current documentation update sequence ending at commit `f749abbe9788279c9b52411c4e9202c8d18841d1`.

### Design decision

Do not delete the original source pages. They are the canonical archival layer. The normalized files are the retrieval layer and should contain the same meaningful detail, only reorganized for targeted retrieval. This gives Qwen both fast narrow retrieval and broader source context when necessary.
