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

### Knowledge collection for Qwen

We are currently collecting game information, bot/gameplay guides, mechanics, descriptions, and other durable knowledge that will later be used as a knowledge base for the local Qwen model.

Knowledge is separated into two planned categories:
- `data/knowledge/official/` — official game information, tutorials, guides, skill descriptions, mechanics, and other trusted/reference material supplied by the game documentation;
- `data/knowledge/learned/` — observations, hypotheses, discovered mechanics, action consequences, and other information learned by the bot during gameplay.

The separation is intentional: official/reference information must not be mixed with uncertain observations learned from experience. Later, Qwen will use both sources as context for analysis and knowledge extraction while Q-learning remains responsible for autonomous action selection.

### Official game knowledge

Official skill documentation is being collected separately from learned observations.

- `data/knowledge/official/skills.md` contains official descriptions of Strength, Agility, Athletics, Perception, Attack, Defense, Dodge, Cutting, Slashing, Blunt, Piercing, Stealth, Lockpicking, Theft, General Crafting, Weapon Forging, Armor Forging, Alchemy, Cooking, Engineering, and Medicine;
- includes official innate-skill information for the wasp: Poison and Hunter;
- current character levels and temporary equipment/innate bonuses are not treated as permanent skill knowledge.

### Built-in tutorial knowledge

Built-in game onboarding has been recorded separately in `data/knowledge/official/tutorial.md`.

The tutorial knowledge now covers:
- initial game concept and onboarding rewards;
- insect species selection and the rule that species can be changed later;
- species-specific innate skills, including the example of the Jumping Beetle (`Бегун`, `Ассассин`) and Wasp (`Яд`, `Охотник`);
- naming restrictions;
- profile parameters: level, XP, condition, hunger, water, and current action;
- the complete skill category structure;
- body condition, blood, hunger, water, carrying capacity, body parts, regeneration, and vital body parts;
- species-specific feeding and food acquisition;
- world exploration and the three exploration ranges;
- relationship between enemy strength and XP rewards;
- battle state representation and the meaning of body-part health versus skill levels;
- basic combat effects of Strength, Agility, Attack, Defense, Dodge, and innate skills;
- a concrete two-attack tutorial battle example and the resulting victory/loot/Attack skill gain;
- stashes, their protection from combat theft, the limit of three stashes, and the `Тайник` command;
- escape mechanics and preservation of equipment/inventory after successful escape;
- `/completeTutorial`, `/handbook`, and `/FAQ`.

This tutorial is treated as official/reference knowledge rather than learned experience. It is intended to give the future Qwen analyst and the self-learning agent a reliable initial model of basic game mechanics, while Q-learning remains responsible for autonomous action selection and experience-based adaptation.

### Project structure commit

`4b493c846efdf60201c95302b7d9fea5f4b92f53`

### Documentation checkpoint — 2026-09-04

- Added `data/knowledge/official/tutorial.md` with the built-in tutorial/onboarding knowledge collected from gameplay.
- Tutorial knowledge is explicitly separated from `data/knowledge/learned/` because it comes from the game's own onboarding and should be treated as reference information.
- Commit: `79e3d8bfaf2775506ab265889a4b686dd4407cf7`
