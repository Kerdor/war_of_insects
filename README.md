# War of Insects Self-Learning Agent

Telegram self-bot for War of Insects with an incremental learning architecture.

## Structure

- `bot/` — agent, perception, learning, memory, reward, strategy and Telegram client modules.
- `config.py` — environment and account configuration.
- `main.py` — normal application entry point.
- `dev_runner.py` — development runner with automatic `git pull` and restart on updates.
- `self_check.py` — local preflight check for core imports, retrieval, contradiction handling and Qwen JSON parsing.
- `data/` — persistent learning data created at runtime.

## Configuration

Copy `.env.example` to `.env` and fill in the Telegram credentials and the accounts you want to run.

Use `ACCOUNT_N_ENABLED=true/false` to enable or disable an account without removing its phone/session settings.

Qwen analysis is optional. Set `QWEN_ENABLED=true` and provide `QWEN_API_KEY` to enable the asynchronous analyst. Q-learning and the Telegram agent do not require Qwen to run.

## Run

Install dependencies:

```bash
pip install -r requirements.txt
```

Before connecting to Telegram, run the local preflight:

```bash
python self_check.py
```

The preflight does not send Telegram messages and does not call the Qwen API.

For normal execution:

```bash
python main.py
```

For development with automatic Git updates every 5 seconds:

```bash
python dev_runner.py
```
