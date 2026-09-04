# War of Insects Self-Learning Agent

Telegram self-bot for War of Insects with an incremental learning architecture.

## Structure

- `bot/` — agent, perception, learning, memory, reward, strategy and Telegram client modules.
- `config.py` — environment and account configuration.
- `main.py` — normal application entry point.
- `dev_runner.py` — development runner with automatic `git pull` and restart on updates.
- `data/` — persistent learning data created at runtime.

## Configuration

Copy `.env.example` to `.env` and fill in the Telegram credentials and the accounts you want to run.

Use `ACCOUNT_N_ENABLED=true/false` to enable or disable an account without removing its phone/session settings.

## Run

Install dependencies:

```bash
pip install -r requirements.txt
```

For normal execution:

```bash
python main.py
```

For development with automatic Git updates every 5 seconds:

```bash
python dev_runner.py
```
