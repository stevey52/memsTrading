# Solana Shitcoin Sniper & Autonomous AI Trading Terminal

A high-performance Solana memecoin trading system, sniper engine, and autonomous AI council terminal. Combines real-time dual token discovery across DexScreener and Pump.fun with sub-second multi-agent LLM screening and a multi-tier moonbag execution engine.

---

## Key Features

### 1. Hybrid Dual Scanner
- **DexScreener Engine:** Real-time polling for momentum trends, $12k+ liquidity pool depth, 5m volume thresholds, and 1.3x buy/sell order flow ratio.
- **Pump.fun WebSocket Engine:** Direct connection to `wss://pumpportal.fun/api/data` for instant trade dispatch on fresh bonding curve launches with $\ge 0.5$ SOL developer buy-ins.
- **Pre-Graduation Migration Tracker:** Identifies tokens reaching 65–84 SOL on the bonding curve (~75%–98% progress) right before liquidity migration to Raydium.

### 2. Autonomous Multi-Agent AI Council
- **Gemini 2.5 Flash Integration:** Powered by Google Gemini structured JSON outputs with custom personas:
  - *Narrative & Virality Scout:* Evaluates meme appeal, cultural meta, and social presence (Twitter/X & Telegram).
  - *Forensic Cabal Auditor:* Analyzes holder distribution, dev wallet concentration, and RugCheck risk scores.
  - *Dynamic Trade Strategist:* Tailors Take-Profit and Stop-Loss boundaries according to token volatility and alpha conviction.
- **Quota Throttling & Cooldown:** Strictly enforces a 12 RPM client-side sliding window ceiling and 25s backoff cooldown to prevent HTTP 429 rate limit errors.
- **Multi-API Key Rotation:** Supports round-robin rotation across multiple comma-separated Gemini API keys (`key1,key2,key3`) to scale free-tier capacity.
- **Deep On-Chain Heuristic Consensus Fallback:** Zero-downtime offline fallback evaluating on-chain RugCheck, top 10 holder distribution ($< 12\%$), and verified social presence during API rate limits or network issues.

### 3. Multi-Tier Moonbag & Moonshot Engine (200% - 1000%+)
- **Tier 1 (Base Scalp):** Sells 50% of the position at +80% profit to recoup initial investment and de-risk.
- **Tier 2 (Expansion):** Sells 25% of the position at +250% profit to lock in solid net gains.
- **Runner Moonbag (25%):** Retains remaining 25% protected by dynamic trailing stops (e.g. 22% drop from peak) and extended hold times (up to 20 minutes) to capture massive 10x-100x pumps.
- **Breakeven Protection:** Automatically ratchets stop-loss to +0.5% once token price surges past +5%.

### 4. Cyberpunk Web Terminal & Dashboard
- Real-time Server-Sent Events (SSE) streaming live opportunities, execution logs, and active trade PnL.
- Interactive AI Council modal inspecting individual agent reasoning and alpha scores.
- One-click manual scalping, emergency panic sell, and runtime parameter configuration persisted to `.env`.

---

## Architecture & Project Structure

```
├── app.py                   # Flask Web Terminal & Server-Sent Events (SSE) server
├── bot_manager.py           # Concurrency orchestrator, trade execution lock, & live state
├── agent_council.py         # Autonomous Multi-Agent Council & heuristic consensus
├── pump_scanner.py          # Pump.fun WebSocket streaming client & pre-grad tracker
├── scanner.py               # DexScreener momentum scanner & token enrichment
├── scalper.py               # Position monitoring, multi-tier TP/SL, & trailing stops
├── trader.py                # Solana on-chain swap execution (Pump.fun & Raydium)
├── safety.py                # RugCheck API auditor & token holder distribution checks
├── social_checker.py        # Twitter/X, Telegram, & IPFS metadata verification
├── config.py                # Configuration loader & validation
├── test_suite.py            # Complete unit test suite (29/29 tests)
├── templates/
│   └── index.html           # Tailwind CSS cyberpunk dashboard & interactive modal UI
├── .env.example             # Template environment configuration
└── requirements.txt         # Python package dependencies
```

---

## Getting Started

### 1. Prerequisites
- Python 3.10+
- Solana CLI or Phantom/Solflare wallet with private key
- (Optional) Free Google AI Studio API key(s) from [aistudio.google.com](https://aistudio.google.com/app/apikey)
- (Optional) Free Solana RPC from [helius.dev](https://helius.dev) or [quicknode.com](https://quicknode.com)

### 2. Installation

Clone the repository and install the dependencies:

```bash
git clone https://github.com/stevey52/memsTrading.git
cd memsTrading

# Create virtual environment
python -m venv virt

# Activate virtual environment
# Windows:
.\virt\Scripts\activate
# Linux/macOS:
source virt/bin/activate

# Install required packages
pip install -r requirements.txt
```

### 3. Configuration

Copy the example environment file and edit your settings:

```bash
cp .env.example .env
```

Key environment variables in `.env`:
```env
# Solana Network & Wallet
SOLANA_RPC_URL=https://api.mainnet-beta.solana.com
SOLANA_PRIVATE_KEY=your_base58_private_key_here

# Trade Execution Parameters
TRADE_AMOUNT_SOL=0.02
SLIPPAGE_BPS=800
TAKE_PROFIT_PCT=25.0
STOP_LOSS_PCT=10.0

# Autonomous AI Council
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.5-flash
AGENT_EVAL_ENABLED=True
MIN_AGENT_ALPHA_SCORE=75.0
```

### 4. Running the Tests

Verify all components and safety checks pass:

```bash
python -m unittest test_suite.py -v
```

### 5. Launching the Web Terminal

Start the terminal server:

```bash
python app.py
```

Open your browser and navigate to:
```
http://127.0.0.1:5000
```

---

## Disclaimer

This software is for educational, research, and experimental purposes only. Cryptocurrency trading, especially micro-cap memecoins on decentralized exchanges, carries substantial financial risk. Never trade with funds you cannot afford to lose.
