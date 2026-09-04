# PROJECT STATE

## 2026-09-05 — Qwen knowledge writer API fix

### Current structure

Application code is grouped into the `bot/` package. Official game knowledge is stored separately from learned observations.

```text
war_of_insects/
├── bot/
│   ├── knowledge_retrieval.py
│   ├── knowledge_writer.py
│   ├── qwen_analyst.py
│   └── ...
├── data/
│   └── knowledge/
│       ├── official/
│       └── learned/
├── config.py
├── self_check.py
├── dev_runner.py
└── main.py
```

### Qwen Telegram-message analysis — 2026-09-04

Qwen is explicitly fed the actual Telegram game messages as the primary observation source for every completed transition when enabled.

The analyst receives:
- the complete game message text before the action;
- visible buttons before the action;
- the complete game message text after the action;
- visible buttons after the action;
- parsed before/after state as supporting structure;
- selected action, local reward and recent actions;
- retrieved official/learned knowledge as prior context.

The prompt instructs Qwen to compare the actual before/after Telegram text first, distinguish directly observed facts from hypotheses, and use parsed state only as supporting information. Ollama JSON output mode is enabled.

Qwen remains an evaluator/mechanics analyst. It does not choose or execute gameplay actions; Q-learning remains responsible for action selection.

### Qwen runtime robustness — 2026-09-04

A runtime test showed two independent Qwen-side failures:
- request timeout;
- malformed JSON returned inside `message.content`.

`bot/qwen_analyst.py` has tolerant result parsing: it first parses the complete response as JSON and, when that fails, attempts to parse the outermost JSON object from the returned content. Invalid/unrecoverable output still produces a zero learning signal instead of stopping the agent.

The existing request timeout and analysis frequency were intentionally not changed in this fix. The Qwen analysis remains asynchronous and cannot directly select or execute gameplay actions.

### Qwen knowledge persistence API fix — 2026-09-05

Runtime logs showed repeated errors:

`[QWEN] Knowledge write failed for auth/kerdor: 'KnowledgeWriter' object has no attribute 'add_candidate'`

The cause was an API mismatch between `bot/qwen_analyst.py` and `bot/knowledge_writer.py`. `KnowledgeWriter` exposes `write_candidates(candidates, account_id, observation_id="")`, while `QwenAnalyst._persist_candidates()` was still calling the removed/nonexistent `add_candidate()` method.

`bot/qwen_analyst.py` was corrected to pass the complete candidate list to `KnowledgeWriter.write_candidates()` in one call. No learning or action-selection logic was changed.

Commit:
- `4f62a64` — fix KnowledgeWriter API call

### Secondary-menu navigation safety — 2026-09-04

Runtime logs showed the game's secondary menu was classified as `unknown` even when its buttons were clearly identifiable, for example `🔙Меню`, `🏕Тайник`, `📦Доставка`, `📝Инсектарий`, `🏆Турнир`, `💵Кредиты`, `🏪Лавка` and `🕷Рефералы`.

`bot/perception.py` detects this screen as `secondary_menu` when `🔙Меню` is present together with one of the known secondary-menu entries.

### Battle/submenu button filtering hardening — 2026-09-04

Runtime logs also showed that Telethon can expose stale battle reply-keyboard buttons together with a submenu's actual buttons. This caused the untrained Q-learning policy to select unrelated controls such as `Состояние (Вы)`, `Предметы` or `Снаряжение` while the agent was on a submenu.

`bot/agent.py` now:
- recognizes a complete battle-button signature when perception is ambiguous;
- keeps battle actions available on an actually ambiguous battle screen;
- prevents stale battle buttons from being selectable on `skills` and `equipment` screens when their own submenu actions are present;
- falls back to `Назад`/`🔙Назад`/`🔙Меню` on ambiguous navigation-only screens;
- avoids treating a small ambiguous submenu as a free-for-all action set.

The change is limited to action filtering; Q-learning remains the action-selection layer and Qwen remains an evaluator.

### Stagnation reward and stale-message handling — 2026-09-05

Runtime behavior showed that the agent could get trapped on a submenu/secondary-menu state. Two changes were made:

- `bot/reward.py` now accepts an optional `stagnation_steps` value. When the agent remains in the same location across repeated transitions, the reward is reduced by `0.10` per repeated step, capped at `-0.50`.
- `bot/agent.py` passes the repeated-state count into the reward calculation.
- `bot/agent.py` no longer treats an unchanged/stale Telegram message as a completed transition after the 5-second polling window.

### Telegram keyboard compatibility fix — 2026-09-05

`bot/telegram_client.py` and `bot/perception.py` now accept both nested button rows and flat Telethon `MessageButton` objects.

Commits:
- `a629829` — fix Telethon `MessageButton` handling in `GameClient`;
- `950ebcc` — fix flat `MessageButton` handling in `Perception`.

### Secondary-menu `Далее` priority bug — 2026-09-05

A global `🔘Далее` rule previously overrode the dedicated `secondary_menu` policy and caused `secondary_menu -> help -> secondary_menu` loops. The fix restricts `secondary_menu` to `🔙Меню`, `help` to `🔙Назад`, and `tutorial` to `🔘Далее`.

Commit:
- `0425b69` — fix secondary-menu navigation priority and flat button clicking.

### Deterministic navigation policy — 2026-09-05

Navigation states are treated as strict policies:
- `tutorial` may select `🔘Далее`;
- `secondary_menu` may select only `🔙Меню`;
- `help` may select only `🔙Назад`;
- `quests` may select only `🔙Назад`/`🔙Меню` unless recognizable main-menu buttons are present.

Commit:
- `2c89268` — make navigation states deterministic instead of exploratory.

### Main/quests keyboard misclassification — 2026-09-05

A main keyboard containing `⭐️Задания` was being classified as `quests`. `bot/agent.py` was hardened to recognize main-menu buttons inside that misclassified state and prefer `🏜Исследовать`.

Commit:
- `fe6bd06` — handle misclassified main keyboard as quests.

### Busy exploration detection — 2026-09-05

Runtime showed that after starting exploration the game replied:

`В данный момент ваше насекомое занято и не может исследовать мир.`

The Telegram reply keyboard remained visible, so perception classified that response as `quests`, causing the agent to repeatedly press `🏜Исследовать` even though exploration was already running.

`bot/perception.py` now checks the actual message text for the exploration-in-progress messages before interpreting the keyboard. Such messages are classified as `busy`, preventing stale main-menu buttons from being treated as executable actions.

Commit:
- `235debd` — fix busy exploration state detection.
