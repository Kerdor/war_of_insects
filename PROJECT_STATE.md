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

### Qwen Telegram-message analysis — 2026-09-04

Qwen is now explicitly fed the actual Telegram game messages as the primary observation source for every completed transition when enabled.

The analyst receives:
- the complete game message text before the action;
- visible buttons before the action;
- the complete game message text after the action;
- visible buttons after the action;
- parsed before/after state as supporting structure;
- selected action, local reward and recent actions;
- retrieved official/learned knowledge as prior context.

The prompt instructs Qwen to compare the actual before/after Telegram text first, distinguish directly observed facts from hypotheses, and use parsed state only as supporting information. Ollama JSON output mode is enabled for more reliable structured responses.

Qwen remains an evaluator/mechanics analyst. It does not choose or execute gameplay actions; Q-learning remains responsible for action selection.

### Runtime connection issue — 2026-09-04

A local run with `C:\Python314\python.exe` did not reach the `Connected: auth/kerdor` log line. Telethon repeatedly reported:

`Server closed the connection: 0 bytes read on a total of 8 expected bytes`

The message is emitted by Telethon's MTProto connection layer and is known to occur when the Telegram server closes a TCP connection; it is not evidence of a Qwen or agent-state failure.

The project dependency was updated from an unpinned `telethon` to:

`telethon>=1.44.0`

This is important because the runtime uses Python 3.14, and current Telethon 1.44.0 explicitly includes Python 3.14 compatibility fixes.

The code architecture was not changed to work around the network error. The local environment must install the updated dependency before the next run.

### Current launch boundary

Before the next run, update the local Python environment from `requirements.txt`. Then verify that `Connected: auth/kerdor` appears before judging the agent/Qwen runtime.
