# PROJECT STATE

## 2026-09-04 — Runtime fixes, self-learning loop, navigation safety and knowledge architecture

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

### Runtime fixes

- `learning.py`: fixed unpacking of `TransitionMemory.predict()`; prediction returns `(count, next_state, average_reward)`.
- `main.py`: cleanup uses the underlying Telethon client's `is_connected()`.
- `agent.py` / `perception.py`: SwitchInline buttons are ignored; reply-keyboard actions are sent as messages; state/action/failure logging is enabled; persistent reply keyboard is merged with the current inline keyboard.
- `telegram_client.py`: recent messages are scanned for keyboards; the persistent `ReplyKeyboardMarkup` is cached; `get_current_buttons()` combines current and persistent actions.
- `telegram_client.py` / `agent.py`: optimized post-action polling so the agent no longer performs a second `get_messages()` request just to rebuild the already-cached persistent reply keyboard on every 0.5-second poll. This removes redundant Telegram API calls from the action-wait loop without changing Q-learning decisions.

### Multi-account behavior

- Accounts authorize sequentially.
- Already authorized sessions skip code entry.
- Enabled accounts run concurrently after authorization.
- `ACCOUNT_N_ENABLED=true/false` controls each account.

### Development runner

`dev_runner.py` starts `main.py`, polls `git pull` every 5 seconds, detects a new HEAD and restarts the application without modifying `.env` or Telegram session files.

### Learning architecture

The agent uses perception/state normalization, Q-learning, transition memory, strategy memory, experience memory, reward calculation, per-account runtime context and learning statistics.

Q-learning remains responsible for autonomous action selection. Qwen observes gameplay and evaluates observed outcomes instead of hardcoding routes or directly executing commands.

### Knowledge architecture

Knowledge is intentionally divided into:

- `data/knowledge/official/` — trusted/reference information from the official game documentation and tutorial;
- `data/knowledge/learned/` — observations, hypotheses, discovered mechanics, action consequences and other experience-derived information.

Official source pages are retained as archival/context documents. The normalized layer is a retrieval layer, not a summary layer: it must preserve useful detail while splitting large pages into focused thematic documents.

### Retrieval layer

`bot/knowledge_retrieval.py` provides dependency-free lexical retrieval over official and learned Markdown.

It:
- recursively loads both knowledge trees;
- preserves source, domain, status, keywords and related metadata;
- splits documents by headings and bounded chunks;
- ranks by query coverage, density, metadata matches, exact phrase matches and source trust;
- gives official knowledge higher trust;
- supports domain/source filtering;
- excludes `conflicted` learned documents from normal retrieval;
- can explicitly include conflicted documents for analyst investigation;
- labels conflicted context as `LEARNED-CONFLICT`;
- builds bounded Qwen context and explicitly states source precedence.

### Qwen analyst layer

`bot/qwen_analyst.py` is connected to `Agent.step()` and remains asynchronous. Qwen analysis is configured for every completed transition by default (`QWEN_ANALYSIS_INTERVAL=1`) whenever Qwen is enabled.

The analyst receives:
- the actual full Telegram game message before the action;
- the actual full Telegram game message after the action;
- visible Telegram buttons before and after the action;
- before/after normalized state and parsed characteristics;
- selected action;
- local reward;
- recent actions;
- retrieved official/learned knowledge, including conflicted learned entries for investigation.

The Telegram messages are now explicit first-class fields in the Qwen observation payload: `telegram_message_before`, `telegram_buttons_before`, `telegram_message_after` and `telegram_buttons_after`. Raw message text is no longer truncated to 5000 characters inside `_state_dict()`; the complete `state.raw_text` is passed to the analyst.

The analyst prompt explicitly tells Qwen to treat the actual Telegram game text and buttons as the primary evidence, compare the before/after messages, and use parsed state only as supporting structure.

Qwen returns:
- structured durable-knowledge candidates;
- a bounded `learning_signal` from `-5.0` to `+5.0` evaluating the observed outcome only.

Qwen does not select or execute gameplay actions.

### Qwen local Ollama backend — 2026-09-04

The Qwen backend was switched from the remote DashScope OpenAI-compatible API to the user's already-installed local Ollama instance.

Current defaults in `bot/qwen_analyst.py`:
- `QWEN_ENABLED=false` — enable explicitly in the local environment;
- `QWEN_BASE_URL=http://localhost:11434`;
- `QWEN_MODEL=qwen3:4b`;
- `QWEN_ANALYSIS_INTERVAL=1`;
- `QWEN_MAX_TOKENS=1200`;
- `QWEN_TIMEOUT=120` seconds.

The analyst calls Ollama's native `/api/chat` endpoint and does not require `QWEN_API_KEY`. The request uses non-streaming output, disables Qwen thinking for this fast structured-analysis workload, and requests JSON output.

The local model confirmed by the user is `qwen3:4b` (approximately 2.5 GB installed through Ollama).

This keeps the intended pipeline local:

`Telegram game message → Perception → Q-learning action → Telegram → next Telegram game message → local reward/Q update → local Ollama Qwen3 4B analysis → optional Qwen learning signal → second Q update + knowledge storage`

No Qwen credentials are required for the local backend.

### Qwen → Q-learning feedback

The local reward path remains authoritative as the immediate baseline:

`state → action → next_state → local reward → normal Q update`

After that update, an enabled Qwen analyst evaluates the same completed transition asynchronously. If its bounded `learning_signal` is non-zero, `Agent` performs a second Q-learning update using:

`adjusted_reward = local reward + learning_signal`

The signal is clamped to `[-5.0, +5.0]`. A disabled, failed, malformed or uncertain Qwen response contributes `0.0`, so Qwen cannot halt gameplay or corrupt the local learning path.

This makes Qwen an evaluator/teacher rather than a policy: Q-learning still chooses the next action.

### Qwen transition delivery

Every eligible transition creates an asynchronous analysis task. Per-account Qwen calls are serialized with an asyncio lock and are no longer silently discarded merely because a previous Qwen request is still running.

### Qwen raw Telegram message analysis — 2026-09-04

The analyst was adjusted so the Telegram message itself is the central observation rather than merely a derived state representation.

For every analyzed transition Qwen receives:

`BEFORE`
- complete raw Telegram message text;
- all visible parsed button labels;
- normalized location/action/statistics/inventory/events.

`ACTION`
- the exact action selected by Q-learning;
- local reward assigned after the resulting state arrives.

`AFTER`
- complete raw Telegram message text;
- all visible parsed button labels;
- normalized location/action/statistics/inventory/events.

It also receives the recent action sequence and retrieved knowledge as context.

The prompt now explicitly instructs Qwen to:
1. compare the actual before/after Telegram messages;
2. identify what the game actually reported as changed;
3. use buttons and parsed fields to understand the message structure;
4. extract only mechanics supported by the observed evidence;
5. avoid choosing the next action.

Ollama JSON mode is enabled for the response so the structured analyst result is less dependent on free-form output formatting.

### Repeated-evidence confirmation

`KnowledgeWriter` maintains `data/knowledge/learned/.evidence.json`.

Each claim stores stable observation IDs, account IDs, timestamps, analyst confidence and evidence. Promotion remains conservative:
- `< 0.55` — discarded;
- single observation — `hypothesis`;
- at least 2 observations and average confidence `>= 0.80` — `candidate`;
- at least 3 observations, at least 2 independent accounts and confidence `>= 0.70` — `confirmed`.

Qwen cannot promote knowledge directly.

### Contradiction handling

The writer accepts a contradiction only when the candidate identifies the same `mechanic_key` and an exact existing learned claim target.

When detected:
- both claims remain stored;
- both become `conflicted`;
- both retain their evidence;
- neither can be promoted while the conflict is active;
- the conflicting claim references are persisted;
- the target Markdown is updated immediately;
- nothing is silently deleted or merged.

Different conditions or exceptions are not automatically treated as contradictions. The analyst is instructed to preserve uncertainty when the evidence does not prove incompatibility.

### Local preflight

Added `self_check.py` for a safe local verification before Telegram execution. It checks:
- imports of the core agent modules;
- loading of the knowledge base;
- retrieval returning context;
- contradiction persistence and conflict status;
- Qwen JSON parsing.

The preflight does not connect to Telegram and does not call the Qwen API.

### Runtime observation and performance fix — 2026-09-04

First real local launch reached Telegram successfully with one enabled account and an already-authorized session.

Observed behavior:
- the agent detected the initial menu and available buttons;
- Q-learning selected actions successfully;
- however, the next state was taking roughly the full 5-second polling window to resolve in the observed log;
- `Agent._wait_for_change()` was polling every 0.5 seconds, while each poll called `get_latest()` and then `get_current_buttons()`, which performed another Telegram history request to rebuild the persistent reply keyboard.

Fix applied:
- `GameClient.get_reply_keyboard_message()` now reuses the cached reply-keyboard message when available;
- `Agent._wait_for_change()` now parses the buttons already returned by `get_latest()` and combines them with the cached reply keyboard directly;
- the Q-learning decision logic, epsilon behavior and action-selection architecture were not changed.

The user's subsequent runtime log showed the action loop becoming fast. The remaining issue was not latency but action quality: untrained Q-learning was exploring arbitrary menu actions.

### Autonomous navigation safety and state recognition — 2026-09-04

Runtime observation showed a critical bootstrap problem:
- many menu screens were classified as `unknown` because perception relied mainly on message text;
- a new/weakly trained Q-table therefore treated unrelated menu buttons as equally viable actions;
- this caused random navigation into help, tutorial, payment and other non-game screens.

Fix applied:
- `Perception` now parses buttons before location detection and uses distinctive button signatures in addition to text markers;
- exploration, skills, equipment, inventory, tutorial, main menu and help screens can now be recognized from their button sets;
- `Agent` filters obviously dangerous/non-game actions such as payment, purchasing, deletion and discarding before passing actions to Q-learning;
- tutorial screens with `🔘Далее` are bootstrapped deterministically when that action is available;
- help screens prefer navigation (`🔙Назад` / `🔘Далее`) instead of random topic/external actions;
- the Q-learning algorithm itself remains unchanged and continues to choose among the remaining meaningful actions.

### Context-aware action filtering — 2026-09-04

The next runtime log showed that button recognition alone was insufficient because Telegram persistent reply-keyboard actions are also present on submenu screens.

Observed examples:
- equipment screen exposed both equipment actions and the global battle/menu keyboard;
- skills screen exposed skill actions together with global menu actions such as `⭐️Задания`;
- pressing `🔘Далее` from the main menu opened a secondary menu containing `🏆Турнир`, `🏪Лавка`, `💵Кредиты` and other unrelated options;
- battle control screens were still sometimes reported as `unknown`.

Fix applied in `Agent._selectable_actions()`:
- skills screens now pass skill-specific actions and valid battle controls to Q-learning, excluding the persistent global menu;
- equipment screens now pass equipment-specific actions and valid battle controls, excluding the persistent global menu;
- exploration screens now pass only exploration controls;
- battle screens now pass only battle controls when the state is recognized;
- main menus exclude `🔘Далее` when real main-menu actions are available, preventing accidental pagination into unrelated menus;
- secondary menus use `🔙Меню` as the safe return path instead of randomly entering tournaments, shops, credits or bonuses;
- dangerous actions remain filtered before Q-learning.

The Q-learning algorithm itself was not modified. This layer only prevents persistent global buttons from contaminating the action set for a more specific current context.

### Qwen every-transition activation — 2026-09-04

The Q-learning file showed many visits but almost all learned Q-values remained `0.0`. The local `RewardEngine` and `QLearning.update()` path confirms that Q-values remain zero when both the calculated reward and future Q-values are zero.

The Qwen analyst was previously configured to analyze only every 10th completed transition. That was changed so the default interval is `1`.

### Qwen learning feedback — 2026-09-04

The Qwen analyst now returns a bounded `learning_signal` in addition to knowledge candidates, and `Agent` can perform an additional Q-learning update from that signal. Qwen remains an evaluator/teacher and never selects actions.

### Current launch boundary

The next local run should verify the context-aware action filtering, local reward path and local Ollama Qwen feedback path.

Recommended order:
1. let `dev_runner.py` pull the latest commit and restart automatically;
2. ensure Ollama is running and `qwen3:4b` is available;
3. set `QWEN_ENABLED=true` in the local `.env`;
4. run with one enabled account;
5. verify skills/equipment/exploration/battle screens expose only context-relevant actions;
6. verify the agent no longer jumps from a submenu into `⭐️Задания`, `🏆Турнир`, `🏪Лавка`, `💵Кредиты` or similar global actions merely because those buttons are present;
7. verify payment/purchase/discard actions are never selected autonomously;
8. verify battle control screens are recognized or at least filtered to battle actions;
9. verify every transition prints a non-ambiguous local `Reward` and `Q` line;
10. verify `Qwen learning signal` appears for completed transitions;
11. verify non-zero Qwen signals produce `Qwen-adjusted reward` and move the Q-value;
12. inspect `data/knowledge/learned/` for durable observations produced by Qwen;
13. only then enable additional accounts and long autonomous runs.

### Current learning boundary

Q-learning owns action selection. Qwen is an asynchronous evaluator/teacher and knowledge-extraction subsystem. Retrieval supplies context; writer persists learned hypotheses and evidence. Confirmed learned knowledge does not become official and does not directly override Q-learning.

### Roadmap after the navigation fix

The next improvements should be driven by observed runtime behavior. Likely areas are:
- improving state representation where real Telegram states are still ambiguous;
- tuning reward signals from real outcomes;
- semantic deduplication of paraphrased claims;
- stronger automatic contradiction detection independent of LLM labels;
- eventually allowing validated learned knowledge to influence action scoring without bypassing Q-learning.

### Design decision

Do not delete original source pages. They remain the canonical archival layer. Normalized files are the retrieval layer and should preserve meaningful source detail in targeted documents.
