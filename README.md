# 🐾 Pocket $DOG

> **Autonomous AI trading agent for $DOG/USD — installable on your iPhone.**  
> Built on [Kraken CLI](https://github.com/krakenfx/kraken-cli) + Claude AI · Submitted for the **Kraken Agent Zero Contest 2026**

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)
![Claude](https://img.shields.io/badge/AI-Claude%20Sonnet-blueviolet.svg)
![PWA](https://img.shields.io/badge/PWA-installable-brightgreen.svg)
![Mode](https://img.shields.io/badge/mode-paper%20trading-orange.svg)

---

## What is Pocket $DOG?

Pocket $DOG is a mobile-first Progressive Web App (PWA) that runs an autonomous $DOG/USD trading agent from your pocket. Install it to your iPhone or Android home screen like a native app — no App Store required.

The agent polls live Kraken market data every 30 seconds, but only calls Claude AI when it matters: when price moves more than 0.5% or volume shifts significantly. Every BUY barks. Every SELL sounds the alarm.

---

## Features

| # | Feature | Detail |
|---|---------|--------|
| 1 | **Live market data** | $DOG/USD price, order book, and volume via Kraken CLI WebSocket streaming |
| 2 | **Claude AI decisions** | Market analysis only triggered by meaningful price movement (>0.5%) |
| 3 | **Autonomous paper trading** | BUY / HOLD / SELL executed via `kraken paper buy/sell` with no manual input |
| 4 | **Mobile PWA** | Install on iPhone via Safari → "Add to Home Screen". Works offline. |
| 5 | **Push notifications** | Real-time alerts on BUY/SELL signals, toggle in Settings |
| 6 | **Sound effects** | Bark on BUY 🐕, alarm on SELL — independently toggleable |
| 7 | **4-tab dashboard** | Home · Chart · Portfolio · Settings |
| 8 | **Interactive settings** | Sound, BUY bark, SELL alarm toggles — persisted in localStorage |
| 9 | **Cost optimized** | ~$0.50/day typical vs $11.52/day naive — 95%+ fewer Claude API calls |

---

## Quickstart

### 1 — Install Kraken CLI

```bash
curl --proto '=https' --tlsv1.2 -LsSf \
  https://github.com/krakenfx/kraken-cli/releases/latest/download/kraken-cli-installer.sh | sh

kraken --version
kraken paper init          # initialise your paper account
```

### 2 — Configure

```bash
git clone https://github.com/YOUR_USERNAME/pocket-dog.git
cd pocket-dog
cp .env.example .env
# Edit .env — add your ANTHROPIC_API_KEY
```

Key `.env` variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | *(required)* | Your Anthropic API key |
| `INTERVAL` | `30` | Seconds between Kraken data polls |
| `CLAUDE_MIN_INTERVAL` | `120` | Minimum seconds between Claude API calls |
| `PRICE_CHANGE_THRESHOLD` | `0.005` | Price move required to trigger Claude (0.5%) |
| `MODE` | `paper` | Set to `live` to trade with real funds |

### 3 — Run

```bash
# Terminal 1 — trading agent
pip install -r requirements.txt
python agent.py

# Terminal 2 — dashboard API
python server.py
```

Open `http://localhost:5173` — or install to your phone:

> **iPhone:** Safari → Share → Add to Home Screen  
> **Android:** Chrome → ⋮ → Add to Home Screen

---

## Cost Optimization

Pocket $DOG decouples market data polling (every 30s) from Claude API calls. Claude is only invoked when the market gives a reason:

| Scenario | Claude called? |
|----------|---------------|
| Price moved >0.5% | ✅ Yes |
| Volume changed >2% | ✅ Yes |
| <2 min since last call | ❌ No — hard cooldown |
| Price and volume flat | ❌ No — cached decision reused |

| Implementation | Calls/day | Est. cost/day |
|----------------|-----------|--------------|
| Naive (every 30s) | 2,880 | ~$11.52 |
| Pocket $DOG | ~120 | ~$0.50 |

---

## Project Structure

```
pocket-dog/
├── agent.py            # Autonomous trading loop (Kraken CLI + Claude AI)
├── server.py           # Flask API — serves agent state to dashboard
├── src/
│   ├── App.jsx         # React PWA — 4-tab mobile dashboard
│   └── main.jsx        # React entry point
├── public/
│   ├── manifest.json   # PWA manifest
│   ├── sw.js           # Service worker (offline + push notifications)
│   ├── icon-192.png    # PWA icon
│   └── apple-touch-icon.png
├── index.html          # PWA entry point
├── vite.config.js      # Vite config
├── requirements.txt    # Python deps (anthropic, flask, python-dotenv)
└── .env.example
```

---

## Kraken CLI Commands Used

```bash
kraken ws ticker DOG/USD              # WebSocket streaming price
kraken ticker DOG/USD -o json         # REST price snapshot
kraken orderbook DOG/USD -o json      # Order book depth
kraken paper init                     # Initialise paper account
kraken paper buy DOG/USD <volume>     # Execute paper buy
kraken paper sell DOG/USD <volume>    # Execute paper sell
kraken paper status -o json           # Portfolio balance
kraken paper history -o json          # Trade history
kraken mcp -s all                     # Expose Kraken tools to Claude via MCP
```

---

## Stack

| Component | Tech |
|-----------|------|
| Market data & trading | Kraken CLI — `kraken ws`, `kraken paper`, `kraken ticker` |
| AI decision engine | Claude Sonnet 4.6 via Anthropic API |
| API server | Python + Flask |
| Frontend | React + Recharts + Roboto |
| PWA runtime | Service Worker + Web Push |
| Build tool | Vite |

---

## Paper → Live

The agent runs in **paper mode by default** — no real money at risk.

To switch to live trading:

```env
KRAKEN_API_KEY=your_key
KRAKEN_API_SECRET=your_secret
MODE=live
```

> ⚠️ Live trading carries real financial risk. Only trade what you can afford to lose.

---

## License

MIT
