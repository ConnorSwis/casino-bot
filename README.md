# Casino Bot

Casino Bot is a Discord gambling bot with blackjack, slots, coin flip, dice roll, and a SQLite-backed wallet.

<img src="./pictures/blackjack.png" alt="blackjack" height="200"/>
<img src="./pictures/slots.gif" alt="slots" width="200"/>

## Requirements

- Python 3.10+
- A Discord bot token

## Setup

1. Clone the repo.
2. Create and activate a virtual environment.
3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Create `.env` in the repo root:

```bash
DISCORD_TOKEN=your_token_here
DISCORD_OWNER_IDS=123456789012345678
DISCORD_PREFIX=$
DISCORD_DEFAULT_BET=100
DISCORD_BONUS_MULTIPLIER=5
DISCORD_BONUS_COOLDOWN=12
```

## Run

```bash
uvicorn app.backend.main:app --host 0.0.0.0 --port 8000
```

The Discord bot is started during FastAPI lifespan startup.

## Notes

- Prefix commands require the **Message Content Intent** enabled in the Discord Developer Portal.
- Economy data is stored in `economy.db` at the repo root.
