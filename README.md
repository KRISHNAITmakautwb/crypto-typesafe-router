# crypto-typesafe-router

Routes natural-language crypto market commands to typed read-only market tools
using the TypeSafe (typesafe-sdk) System One API (Jev).

## Setup

```bash
cd /home/crypto_nn/crypto-typesafe-router
python -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'
cp .env.example .env   # set TYPESAFE_API_KEY
```

## Run

```bash
crypto-router "show sol price"
crypto-router --dry-run "compare btc and eth this week"
pytest
```
