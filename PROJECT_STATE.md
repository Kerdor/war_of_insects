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

Q-learning remains responsible for autonomous action selection. Qwen observes gameplay and extracts durable knowledge instead of hardcoding routes.

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

`bot/qwen_analyst.py` is connected to `Agent.step()` and remains asynchronous. It now analyzes **every completed transition by default** (`QWEN_ANALYSIS_INTERVAL=1`) whenever Qwen is enabled and an API key is configured. Analysis runs in a background task and does not block the gameplay loop.

The analyst receives:
- before/after normalized state;
- selected action;
- reward;
- recent actions;
- retrieved official/learned knowledge, including conflicted learned entries for investigation.

Qwen returns structured candidates only. It does not select or execute gameplay actions.

Important runtime behavior:
- Qwen does not need a separate local process when using the configured OpenAI-compatible DashScope endpoint; the agent calls the remote API directly.
- If `QWEN_ENABLED` is false or `QWEN_API_KEY` is empty, gameplay continues normally and Qwen analysis is simply skipped.
- Therefore the current bot can run without Qwen, but it will not receive Qwen-derived knowledge until the API is enabled and configured.

Candidate metadata includes:
- `mechanic_key` — stable identifier for the underlying mechanic;
- `relation` — `new`, `supports`, `contradicts` or `unclear`;
- `conflicts_with` — exact learned claim text when a material contradiction is identified.

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

### Qwen integration correction

The Qwen analyst now uses the current retrieval API correctly and explicitly requests conflicted knowledge so it can compare new observations against unresolved claims. Normal agent retrieval still excludes those claims.

### Local preflight

Added `self_check.py` for a safe local verification before Telegram execution. It checks:
- imports of the core agent modules;
- loading of the knowledge base;
- retrieval returning context;
- contradiction persistence and conflict status;
- Qwen JSON parsing.

The preflight does not connect to Telegram and does not call the Qwen API.

### Static launch audit — 2026-09-04

The repository was audited across the current agent, Q-learning, Telegram client, configuration, Qwen analyst, retrieval and knowledge writer integration points.

Critical integration issue found and corrected:
- `QwenAnalyst` was calling `build_qwen_prompt_context()` with the obsolete `include_learned` argument. The call now matches the current retrieval interface.

Additional consistency correction:
- conflicted knowledge is now explicitly labelled `LEARNED-CONFLICT` when included for analyst investigation, matching the documented architecture.

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

The runtime Q-learning file showed many visits but almost all learned Q-values remained `0.0`. The current `RewardEngine` and `QLearning.update()` path confirms that Q-values only change when the calculated reward or future Q-value is non-zero. Qwen was previously configured to analyze only every 10th completed transition.

Change applied:
- `QWEN_ANALYSIS_INTERVAL` default changed from `10` to `1`;
- when Qwen is enabled, every completed transition now schedules an asynchronous analyst call;
- no gameplay action-selection authority was given to Qwen;
- Qwen remains a learning/knowledge analysis layer, while Q-learning remains the action selector.

This does **not** require a separate local Qwen process. The existing analyst uses the configured OpenAI-compatible DashScope API. Without `QWEN_ENABLED=true` and a valid `QWEN_API_KEY`, the new every-transition path remains inactive by design.

### Current launch boundary

The next local run should verify the context-aware action filtering and, when credentials are configured, the every-transition Qwen analyst.

Recommended order:
1. let `dev_runner.py` pull the latest commit and restart automatically;
2. run with one enabled account;
3. verify skills/equipment/exploration/battle screens expose only context-relevant actions;
4. verify the agent no longer jumps from a submenu into `⭐️Задания`, `🏆Турнир`, `🏪Лавка` or similar global actions merely because those buttons are present;
5. verify payment/purchase/discard actions are never selected autonomously;
6. verify battle control screens are recognized or at least filtered to battle actions;
7. verify real gameplay state → action → next state → reward → Q-learning flow;
8. if Qwen credentials are available, set `QWEN_ENABLED=true` and verify one analyst request per completed transition and learned output;
9. inspect whether rewards are non-zero and whether Q-values begin moving away from `0.0`;
10. only then enable additional accounts and long autonomous runs.

### Current learning boundary

Q-learning still owns action selection. Qwen is an asynchronous observation/knowledge-extraction subsystem. Retrieval supplies context; writer persists learned hypotheses and evidence. Confirmed learned knowledge does not become official and does not directly override Q-learning.

### Roadmap after the navigation fix

The next improvements should be driven by observed runtime behavior. Likely areas are:
- improving state representation where real Telegram states are still ambiguous;
- tuning reward signals from real outcomes;
- semantic deduplication of paraphrased claims;
- stronger automatic contradiction detection independent of LLM labels;
- eventually allowing validated learned knowledge to influence action scoring without bypassing Q-learning.

### Design decision

Do not delete original source pages. They remain the canonical archival layer. Normalized files are the retrieval layer and should preserve meaningful source detail in targeted documents.
