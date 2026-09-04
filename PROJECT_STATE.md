# PROJECT STATE

## 2026-09-04 — Runtime fixes, self-learning loop, development runner, official knowledge normalization and retrieval

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

Q-learning remains responsible for autonomous action selection. The Qwen analyst observes gameplay and extracts durable knowledge instead of hardcoding routes.

### Knowledge architecture

Knowledge is intentionally divided into:

- `data/knowledge/official/` — trusted/reference information from the official game documentation and tutorial;
- `data/knowledge/learned/` — future observations, hypotheses, discovered mechanics, action consequences and other experience-derived information.

Official source pages are retained as archival/context documents. The normalized layer is a retrieval layer, not a summary layer: it must preserve the useful detail from the official source while splitting large pages into focused thematic documents.

### Qwen-friendly official knowledge structure — 2026-09-04

The entire normalized topic layer has been expanded so that topic files preserve substantive rules, conditions, effects, requirements, restrictions, exceptions and operational commands instead of short summaries.

Index-oriented files remain intentionally concise:
- `official/README.md` — map of the knowledge base;
- `official/commands.md` — command-oriented lookup;
- `combat/damage.md` — combat-damage navigation.

### Retrieval layer — 2026-09-04

Added `bot/knowledge_retrieval.py`.

The retriever is dependency-free and currently lexical so it works offline and does not require an embedding service. It:
- recursively loads Markdown from `data/knowledge/official/` and `data/knowledge/learned/`;
- keeps source, domain, keywords and related-document metadata;
- splits documents by Markdown headings and then into bounded chunks while preserving section context;
- ranks chunks by query-term coverage, term density, metadata matches, exact phrase matches and source trust;
- gives official knowledge a higher trust bonus than learned observations;
- supports filtering by `domain` and `source`;
- can exclude learned knowledge entirely;
- builds bounded context suitable for sending to Qwen;
- explicitly tells Qwen that learned observations are hypotheses and must not override explicit official rules.

The public retrieval interface is:
- `KnowledgeRetriever.search(...)` — ranked `KnowledgeHit` objects;
- `KnowledgeRetriever.build_context(...)` — bounded source-labelled context;
- `KnowledgeRetriever.build_qwen_prompt_context(...)` — Qwen-ready context with source precedence instructions.

The design intentionally avoids hard-coding game routes. Retrieval supplies knowledge to the analyst; Q-learning remains responsible for choosing actions.

### Qwen analyst layer — 2026-09-04

Added `bot/qwen_analyst.py` and `bot/knowledge_writer.py` and connected them to `Agent.step()`.

The runtime flow is now:
1. Perception parses the current Telegram observation into `GameState`.
2. Q-learning selects and executes the action.
3. The next state and reward are recorded in the existing learning systems.
4. Every `QWEN_ANALYSIS_INTERVAL` completed transitions, the Qwen analyst is scheduled asynchronously so gameplay is not blocked by the network call.
5. The analyst receives the before/after normalized states, selected action, reward, recent actions and retrieved official/learned context.
6. Qwen returns structured knowledge candidates only; it is explicitly forbidden from selecting or executing actions.
7. `KnowledgeWriter` persists sufficiently confident candidates under `data/knowledge/learned/<domain>/` as Markdown with frontmatter and evidence.

### Repeated-evidence confirmation — 2026-09-04

`KnowledgeWriter` now maintains a persistent evidence ledger at `data/knowledge/learned/.evidence.json`.

Each learned claim is aggregated by deterministic claim hash. Every observation stores:
- stable observation ID derived from account + before/after state + action + reward;
- account ID;
- timestamp;
- analyst confidence;
- evidence supplied by Qwen.

Promotion rules are deliberately conservative:
- `< 0.55` confidence: discarded;
- otherwise, a single observation is `hypothesis`;
- at least 2 observations with average confidence `>= 0.80`: `candidate`;
- at least 3 observations from at least 2 independent accounts with confidence `>= 0.70`: `confirmed`.

Qwen itself cannot promote knowledge. Only repeated runtime evidence can do so. Confirmed knowledge remains under `learned/`; it does not become official and cannot overwrite official documentation.

The generated Markdown now exposes support counts, independent-account counts and the accumulated evidence so the retrieval layer can distinguish weak hypotheses from repeatedly observed mechanics.

### Qwen configuration

`.env.example` now documents:
- `QWEN_ENABLED=false` — opt-in switch;
- `QWEN_API_KEY`;
- `QWEN_BASE_URL` (OpenAI-compatible endpoint, default DashScope compatible-mode endpoint);
- `QWEN_MODEL`;
- `QWEN_ANALYSIS_INTERVAL=10`;
- `QWEN_MAX_TOKENS=1200`;
- `QWEN_TIMEOUT=30`.

The analyst uses Python's standard-library HTTP client, so no additional package is required.

### Current learning boundary

Q-learning still owns action selection. The Qwen analyst is an asynchronous observation/knowledge-extraction subsystem only. Retrieval supplies context; analyst output becomes learned hypotheses; repeated evidence can promote them to confirmed learned knowledge without changing the action policy directly.

### Retrieval roadmap

Future improvements can add contradiction handling, semantic claim deduplication, richer cross-account evidence aggregation and optional semantic/embedding retrieval. These are deliberately not required for the current autonomous analyst loop.

### Retrieval document standard

Every substantive normalized document should:
- preserve meaningful source detail rather than summarizing it away;
- split only along meaningful retrieval boundaries;
- keep conditions, effects, requirements, restrictions, exceptions and examples;
- use lightweight frontmatter with stable `id`, `type`, `domain`, `source`, `keywords` and `related` fields;
- use index files only for navigation;
- avoid replacing authoritative source details with guesses when the source is ambiguous or internally inconsistent.

### Design decision

Do not delete the original source pages. They are the canonical archival layer. The normalized files are the retrieval layer and should contain the same meaningful detail, only reorganized for targeted retrieval. This gives Qwen both fast narrow retrieval and broader source context when necessary.
