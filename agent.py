#!/usr/bin/env python3
"""
🐕 Agent DOG — Autonomous $DOG/USD Trading Agent
Powered by Kraken CLI + Claude (Anthropic API)

Usage:
  python agent.py

Requirements:
  - Kraken CLI installed (kraken --version)
  - ANTHROPIC_API_KEY in .env
  - Paper account initialized: kraken paper init
"""

import subprocess
import json
import time
import os
from datetime import datetime
from dotenv import load_dotenv
import anthropic

load_dotenv()

# ── Config ──────────────────────────────────────────────────────────────────
PAIR        = "DOG/USD"
INTERVAL    = 30           # seconds between market data polls (kept frequent)
SIZE_USD    = 50           # paper trade size in USD per trade
MODE        = os.getenv("MODE", "paper")   # "paper" or "live"
client      = anthropic.Anthropic()

# ── Claude call throttling ───────────────────────────────────────────────────
CLAUDE_MIN_INTERVAL     = 120    # minimum seconds between Claude API calls (2 min)
PRICE_CHANGE_THRESHOLD  = 0.005  # 0.5% price move triggers a new Claude call
VOLUME_CHANGE_THRESHOLD = 0.02   # 2% volume change also triggers a call

# ── Cost estimation (Claude Sonnet 4.6 pricing) ──────────────────────────────
COST_INPUT_PER_M  = 3.00    # $3.00 per million input tokens
COST_OUTPUT_PER_M = 15.00   # $15.00 per million output tokens
EST_INPUT_TOKENS  = 600     # estimated input tokens per call (system + user prompt)
EST_OUTPUT_TOKENS = 150     # estimated output tokens per call (JSON response)
COST_PER_CALL     = (
    EST_INPUT_TOKENS  * COST_INPUT_PER_M  / 1_000_000 +
    EST_OUTPUT_TOKENS * COST_OUTPUT_PER_M / 1_000_000
)  # ≈ $0.0040 per call


# ── Kraken CLI helpers ───────────────────────────────────────────────────────

def kraken(*args, check=True) -> dict | list | str:
    """Run a Kraken CLI command and return parsed JSON."""
    cmd = ["kraken", "-o", "json"] + list(args)
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    if check and result.returncode != 0:
        raise RuntimeError(f"kraken error: {result.stderr.strip()}")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return result.stdout.strip()


def get_ticker() -> dict:
    """Live $DOG/USD ticker snapshot."""
    data = kraken("ticker", PAIR)
    info = data.get(PAIR, {})
    return {
        "pair":   PAIR,
        "last":   float(info["c"][0]),
        "bid":    float(info["b"][0]),
        "ask":    float(info["a"][0]),
        "high":   float(info["h"][1]),   # 24h high
        "low":    float(info["l"][1]),   # 24h low
        "vwap":   float(info["p"][1]),   # 24h vwap
        "volume": float(info["v"][1]),   # 24h volume
        "trades": int(info["t"][1]),     # 24h trade count
    }


def get_orderbook() -> dict:
    """Top 5 bids/asks from order book."""
    data = kraken("orderbook", PAIR)
    return {
        "bids": data.get("bids", [])[:5],
        "asks": data.get("asks", [])[:5],
    }


def get_paper_status() -> dict:
    """Current paper portfolio status."""
    return kraken("paper", "status")


def get_paper_history() -> list:
    """Last 5 paper trades."""
    try:
        return kraken("paper", "history")[:5]
    except Exception:
        return []


def execute_paper_trade(signal: str, size_usd: float = SIZE_USD):
    """Execute a paper BUY or SELL order."""
    ticker = get_ticker()
    price  = ticker["last"]
    volume = round(size_usd / price)   # USD → DOG tokens

    if signal == "BUY":
        return kraken("paper", "buy", PAIR, str(volume))
    elif signal == "SELL":
        return kraken("paper", "sell", PAIR, str(volume))
    return None


# ── Claude AI decision engine ─────────────────────────────────────────────────

SYSTEM_PROMPT = """You are Agent DOG — an autonomous AI trading agent for the $DOG Army.
You analyze live $DOG/USD market data from Kraken and make trading decisions.

RESPOND WITH VALID JSON ONLY. No markdown, no preamble, no explanation outside the JSON.

{
  "signal": "BUY" | "HOLD" | "SELL",
  "confidence": 0-100,
  "mood": "HOPEFUL" | "BULLISH" | "STEADY" | "CAUTIOUS" | "TACTICAL" | "PATIENT" | "EXCITED",
  "commentary": "<punchy DOG Army one-liner, max 80 chars, can include 🐾>",
  "reasoning": "<brief technical reasoning, 1-2 sentences>",
  "size_usd": 25-100
}

Style guide:
- You are data-driven, loyal to the $DOG Army, speak in pack lingo
- You do NOT panic-bark on small dips
- Base decisions on momentum, volume, spread, and price vs VWAP
- If price < VWAP and volume is rising → lean BUY
- If price at resistance and volume dropping → lean SELL or HOLD
- Default to HOLD when signals are unclear"""


def analyze_with_claude(snapshot: dict, history: list) -> dict:
    """Ask Claude for a trading decision based on current market data."""

    prompt = f"""Current $DOG/USD market snapshot from Kraken:

TICKER:
  Last price: ${snapshot['ticker']['last']:.8f}
  Bid / Ask:  ${snapshot['ticker']['bid']:.8f} / ${snapshot['ticker']['ask']:.8f}
  24h High:   ${snapshot['ticker']['high']:.8f}
  24h Low:    ${snapshot['ticker']['low']:.8f}
  24h VWAP:   ${snapshot['ticker']['vwap']:.8f}
  24h Volume: {snapshot['ticker']['volume']:,.0f} DOG
  24h Trades: {snapshot['ticker']['trades']:,}

ORDER BOOK (top 5):
  Bids: {snapshot['orderbook']['bids']}
  Asks: {snapshot['orderbook']['asks']}

PAPER PORTFOLIO:
{json.dumps(snapshot['portfolio'], indent=2)}

LAST 5 DECISIONS:
{json.dumps(history[-5:] if history else [], indent=2)}

Make your trading decision for $DOG/USD now."""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=400,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}]
    )

    raw = message.content[0].text.strip()
    # Strip any accidental markdown fences
    raw = raw.replace("```json", "").replace("```", "").strip()
    return json.loads(raw)


def should_call_claude(
    now: float,
    last_claude_time: float,
    last_price: float | None,
    last_volume: float | None,
    current_price: float,
    current_volume: float,
) -> tuple[bool, str]:
    """
    Return (True, reason) if a Claude API call is warranted, else (False, skip_reason).

    Rules (all must pass):
    1. Minimum 2-minute interval between calls.
    2. At least one of: price moved ≥0.5% OR volume moved ≥2% since last call.
       (First call always proceeds regardless of movement.)
    """
    time_since_last = now - last_claude_time
    if time_since_last < CLAUDE_MIN_INTERVAL:
        remaining = int(CLAUDE_MIN_INTERVAL - time_since_last)
        return False, f"cooldown ({remaining}s left)"

    if last_price is None:
        return True, "first call"

    price_delta_pct  = abs(current_price  - last_price)  / last_price
    volume_delta_pct = abs(current_volume - last_volume) / last_volume if last_volume else 1.0

    reasons = []
    if price_delta_pct >= PRICE_CHANGE_THRESHOLD:
        reasons.append(f"price moved {price_delta_pct*100:.2f}%")
    if volume_delta_pct >= VOLUME_CHANGE_THRESHOLD:
        reasons.append(f"volume moved {volume_delta_pct*100:.1f}%")

    if reasons:
        return True, " + ".join(reasons)

    return False, (
        f"price flat ({price_delta_pct*100:.3f}% < {PRICE_CHANGE_THRESHOLD*100}%), "
        f"volume flat ({volume_delta_pct*100:.1f}% < {VOLUME_CHANGE_THRESHOLD*100}%)"
    )


# ── Logging ───────────────────────────────────────────────────────────────────

def log(
    decision: dict,
    ticker: dict,
    *,
    cached: bool = False,
    skip_reason: str = "",
    api_calls: int = 0,
    session_cost: float = 0.0,
):
    """Pretty-print the agent's decision to terminal."""
    ts   = datetime.now().strftime("%H:%M:%S")
    sig  = decision["signal"]
    mood = decision["mood"]
    conf = decision["confidence"]
    text = decision["commentary"]

    colors = {"BUY": "\033[92m", "SELL": "\033[91m", "HOLD": "\033[94m"}
    reset  = "\033[0m"
    c      = colors.get(sig, "")

    source = "📦 cached" if cached else "🤖 claude"

    print(f"\n{'─'*60}")
    print(f"🐕 [{ts}] ${ticker['last']:.8f}  |  {c}{sig}{reset}  ({mood}, {conf}%)  [{source}]")
    print(f"   {text}")
    print(f"   → {decision['reasoning']}")
    if cached:
        print(f"   ⏭  Skipped API call — {skip_reason}")
    # Cost summary line
    max_daily = 86_400 / CLAUDE_MIN_INTERVAL * COST_PER_CALL
    print(
        f"   💰 ${COST_PER_CALL:.4f}/call · session: {api_calls} calls / ${session_cost:.4f} "
        f"· est. max/day: ${max_daily:.2f}"
    )
    print(f"{'─'*60}")


# ── Main agent loop ───────────────────────────────────────────────────────────

def main():
    print("🐕 Agent DOG starting up...")
    print(f"   Pair:           {PAIR}")
    print(f"   Mode:           {MODE}")
    print(f"   Poll interval:  {INTERVAL}s  (market data)")
    print(f"   Claude min gap: {CLAUDE_MIN_INTERVAL}s  (API calls)")
    print(f"   Price trigger:  >{PRICE_CHANGE_THRESHOLD*100}% move")
    print(f"   Volume trigger: >{VOLUME_CHANGE_THRESHOLD*100}% move")
    print(f"   Est. cost/call: ${COST_PER_CALL:.4f}")
    max_calls_day = 86_400 / CLAUDE_MIN_INTERVAL
    print(f"   Max calls/day:  {max_calls_day:.0f}  (${max_calls_day * COST_PER_CALL:.2f}/day cap)\n")

    # Sanity check — make sure paper account exists
    try:
        status = get_paper_status()
        print(f"📋 Paper account ready: {status}")
    except Exception as e:
        print(f"⚠️  Paper account not found. Run: kraken paper init")
        print(f"   Error: {e}")
        return

    decision_history  = []
    last_claude_time  = 0.0
    last_price        = None
    last_volume       = None
    last_decision     = None
    api_calls_session = 0
    session_cost      = 0.0

    while True:
        try:
            # 1. Always poll fresh market data (every 30s)
            ticker    = get_ticker()
            orderbook = get_orderbook()
            portfolio = get_paper_status()
            trades    = get_paper_history()

            snapshot = {
                "ticker":    ticker,
                "orderbook": orderbook,
                "portfolio": portfolio,
                "timestamp": datetime.now().isoformat(),
            }

            current_price  = ticker["last"]
            current_volume = ticker["volume"]
            now            = time.time()

            # 2. Decide whether to call Claude
            call_claude, reason = should_call_claude(
                now, last_claude_time,
                last_price, last_volume,
                current_price, current_volume,
            )

            if call_claude:
                decision = analyze_with_claude(snapshot, decision_history)
                decision_history.append(decision)
                last_claude_time = now
                last_price       = current_price
                last_volume      = current_volume
                last_decision    = decision
                api_calls_session += 1
                session_cost      += COST_PER_CALL
                log(decision, ticker, cached=False,
                    api_calls=api_calls_session, session_cost=session_cost)
            else:
                # Re-use last decision; still update dashboard price
                decision = last_decision
                log(decision, ticker, cached=True, skip_reason=reason,
                    api_calls=api_calls_session, session_cost=session_cost)

            # 3. Execute trade (only on fresh Claude decisions to avoid repeat fills)
            if call_claude and MODE == "paper" and decision["signal"] in ("BUY", "SELL"):
                size = decision.get("size_usd", SIZE_USD)
                trade_result = execute_paper_trade(decision["signal"], size)
                if trade_result:
                    print(f"   ✅ Trade executed: {trade_result}")

            # 4. Write state for dashboard
            state = {
                "timestamp":       snapshot["timestamp"],
                "price":           ticker["last"],
                "decision":        decision,
                "portfolio":       portfolio,
                "api_calls_today": api_calls_session,
                "session_cost_usd": round(session_cost, 6),
                "decision_source": "claude" if call_claude else "cached",
            }
            with open("/tmp/agent_dog_state.json", "w") as f:
                json.dump(state, f, indent=2)

            # 5. Wait before next poll
            time.sleep(INTERVAL)

        except KeyboardInterrupt:
            print(f"\n🐕 Agent DOG signing off. Session: {api_calls_session} Claude calls / ${session_cost:.4f}")
            break
        except Exception as e:
            print(f"[ERROR] {e}")
            time.sleep(10)


if __name__ == "__main__":
    main()
