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

The existing request timeout and analysis frequency were intentionally not changed in this fix. The Qwen analysis remains asynchronous and cannot directly select or execute actions.

### Qwen knowledge persistence API fix — 2026-09-05

Runtime logs showed repeated errors:

`[QWEN] Knowledge write failed for auth/kerdor: 'KnowledgeWriter' object has no attribute 'add_candidate'`

The cause was an API mismatch between `bot/qwen_analyst.py` and `bot/knowledge_writer.py`. `KnowledgeWriter` exposes `write_candidates(candidates, account_id, observation_id="")`, while `QwenAnalyst._persist_candidates()` was still calling the removed/nonexistent `add_candidate()` method.

`bot/qwen_analyst.py` was corrected to pass the complete candidate list to `KnowledgeWriter.write_candidates()` in one call. No learning or action-selection logic was changed.

Commit:
- `4f62a64` — fix KnowledgeWriter API call

### Secondary-menu navigation safety — 2026-09-04

Runtime logs showed the game's secondary menu was classified as `unknown` even when its buttons were clearly identifiable, for example `🔙Меню`, `🏕Тайник`, `📦Доставка`, `📝Инсектарий`, `🏆Турнир`, `💵Кредиты`, bonus buttons, `🏪Лавка` and `🕷Рефералы`.

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

- `bot/reward.py` now accepts an optional `stagnation_steps` value. When the agent remains in the same location across repeated transitions, the reward is reduced by `0.10` per repeated step, capped at `-0.50`. This makes useless state loops increasingly unattractive to Q-learning without changing the positive rewards for experience, levels, victories or loot.
- `bot/agent.py` now passes the repeated-state count into the reward calculation.
- `bot/agent.py` no longer treats an unchanged/stale Telegram message as a completed transition after the 5-second polling window. `_wait_for_change()` returns `None` instead, so the agent does not learn a fake zero-reward transition from an old message.

The existing `secondary_menu` action filter still restricts that state to `🔙Меню`. The goal is for Q-learning to learn that staying in a navigation-only state is bad and returning to the main menu is the useful transition.

Commits:
- `5f94d53` — add stagnation penalty to reward learning;
- `20ea10e` — penalize stagnation and ignore unchanged messages.

### Telegram keyboard compatibility fix — 2026-09-05

The local runtime failed repeatedly with:

`'MessageButton' object is not iterable`

The cause was `GameClient.get_current_buttons()` assuming every item in `message.buttons` was a row/list. Telethon can expose a flat `MessageButton` object in this path. The method now accepts both nested rows and individual `MessageButton` objects, preserving the existing button-selection logic.

Commit:
- `a629829` — fix MessageButton keyboard handling.

### Runtime connection issue — 2026-09-04

A local run with `C:\Python314\python.exe` did not reach the `Connected: auth/kerdor` log line. Telethon repeatedly reported:

`Server closed the connection: 0 bytes read on a total of 8 expected bytes`

The message is emitted by Telethon's MTProto connection layer and is known to occur when the Telegram server closes a TCP connection; it is not evidence of a Qwen or agent-state failure.

The project dependency was updated from an unpinned `telethon` to:

`telethon>=1.44.0`

This is important because the runtime uses Python 3.14, and current Telethon 1.44.0 explicitly includes Python 3.14 compatibility fixes.

### Current launch boundary

Before the next run, update the local Python environment from `requirements.txt` if that has not already been done. Then verify that `Connected: auth/kerdor` appears before judging the agent/Qwen runtime.

### Latest code changes — 2026-09-05

Commits:
- `43b98b1` — detect the game's secondary menu as `secondary_menu`;
- `0d24b95` — make Qwen JSON result parsing tolerant of wrapper text/JSON extraction failures;
- `d5ff7a4` — harden Agent action filtering for stale/ambiguous submenu buttons;
- `4f62a64` — fix KnowledgeWriter API call;
- `5f94d53` — add stagnation penalty to reward learning;
- `20ea10e` — penalize stagnation and ignore unchanged messages;
- `a629829` — fix Telethon `MessageButton` keyboard handling.
