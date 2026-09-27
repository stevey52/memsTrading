import os
import json
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
# Explicitly load .env from the project directory
load_dotenv(BASE_DIR / ".env")
# Also fallback to default search in current working directory
load_dotenv()

# Network & RPC
RPC_URL = os.getenv("SOLANA_RPC_URL", "https://api.mainnet-beta.solana.com")

# Token Constants
WSOL_MINT = "So11111111111111111111111111111111111111112"
JUPITER_QUOTE_API = "https://api.jup.ag/swap/v1/quote"
JUPITER_SWAP_API = "https://api.jup.ag/swap/v1/swap"

# Trade & Scalp Settings
TRADE_AMOUNT_SOL = float(os.getenv("TRADE_AMOUNT_SOL", "0.02"))
SLIPPAGE_BPS = int(os.getenv("SLIPPAGE_BPS", "800"))

TAKE_PROFIT_PCT = float(os.getenv("TAKE_PROFIT_PCT", "25.0"))
STOP_LOSS_PCT = float(os.getenv("STOP_LOSS_PCT", "10.0"))

TRAILING_STOP_ENABLED = os.getenv("TRAILING_STOP_ENABLED", "True").lower() == "true"
TRAILING_TRIGGER_PCT = float(os.getenv("TRAILING_TRIGGER_PCT", "8.0"))
TRAILING_DROP_PCT = float(os.getenv("TRAILING_DROP_PCT", "3.5"))

BREAKEVEN_PROTECTION_ENABLED = os.getenv("BREAKEVEN_PROTECTION_ENABLED", "True").lower() == "true"
BREAKEVEN_TRIGGER_PCT = float(os.getenv("BREAKEVEN_TRIGGER_PCT", "5.0"))

MAX_HOLD_SECONDS = int(os.getenv("MAX_HOLD_SECONDS", "240"))

# Scanner Filters
MIN_LIQUIDITY_USD = float(os.getenv("MIN_LIQUIDITY_USD", "12000"))
MIN_5M_VOLUME_USD = float(os.getenv("MIN_5M_VOLUME_USD", "8000"))
MIN_BUY_SELL_RATIO = float(os.getenv("MIN_BUY_SELL_RATIO", "1.3"))
MAX_RUGCHECK_SCORE = int(os.getenv("MAX_RUGCHECK_SCORE", "500"))
RUGCHECK_FAIL_OPEN = os.getenv("RUGCHECK_FAIL_OPEN", "False").lower() == "true"
SCAN_INTERVAL_SECONDS = int(os.getenv("SCAN_INTERVAL_SECONDS", "10"))

# Pump.fun WebSocket Scanner Filters
PUMP_MIN_DEV_BUY_SOL = float(os.getenv("PUMP_MIN_DEV_BUY_SOL", "0.5"))
PUMP_MAX_DEV_BUY_SOL = float(os.getenv("PUMP_MAX_DEV_BUY_SOL", "6.0"))
PUMP_MIN_MARKET_CAP_SOL = float(os.getenv("PUMP_MIN_MARKET_CAP_SOL", "30.0"))

# Social Media & OSINT Verification Filters
REQUIRE_SOCIALS = os.getenv("REQUIRE_SOCIALS", "True").lower() == "true"
REQUIRE_TWITTER = os.getenv("REQUIRE_TWITTER", "True").lower() == "true"
REQUIRE_TELEGRAM = os.getenv("REQUIRE_TELEGRAM", "False").lower() == "true"
REQUIRE_WEBSITE = os.getenv("REQUIRE_WEBSITE", "False").lower() == "true"

# On-Chain Anti-Cabal / Anti-Bundle Filters
MAX_DEV_HOLDING_PCT = float(os.getenv("MAX_DEV_HOLDING_PCT", "10.0"))
MAX_TOP10_NON_CURVE_PCT = float(os.getenv("MAX_TOP10_NON_CURVE_PCT", "25.0"))

# AI Agent Council Settings (Google Gemini 2.5 Flash)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
if GEMINI_MODEL in ("gemini-2.0-flash", "gemini-2.0-flash-exp"):
    GEMINI_MODEL = "gemini-2.5-flash"
AGENT_EVAL_ENABLED = os.getenv("AGENT_EVAL_ENABLED", "True").lower() == "true"
MIN_AGENT_ALPHA_SCORE = float(os.getenv("MIN_AGENT_ALPHA_SCORE", "75.0"))
AGENT_DYNAMIC_TP_SL = os.getenv("AGENT_DYNAMIC_TP_SL", "True").lower() == "true"
AGENT_FAIL_OPEN = os.getenv("AGENT_FAIL_OPEN", "False").lower() == "true"
RUNNER_MIN_ALPHA_SCORE = float(os.getenv("RUNNER_MIN_ALPHA_SCORE", "82.0"))
AGENT_MAX_RPM = int(os.getenv("AGENT_MAX_RPM", "12")) # Max 12 requests/min to strictly respect 15 RPM free tier
AGENT_COOLDOWN_SECONDS = int(os.getenv("AGENT_COOLDOWN_SECONDS", "25")) # Backoff window upon HTTP 429

# Multi-Tier Moonbag & Moonshot Engine (Capture 200% - 1000%+ runs)
MOONBAG_ENABLED = os.getenv("MOONBAG_ENABLED", "True").lower() == "true"
TIER1_TP_PCT = float(os.getenv("TIER1_TP_PCT", "80.0"))        # Tier 1 (+80%): Sell 50% to recover initial capital
TIER1_SELL_PCT = float(os.getenv("TIER1_SELL_PCT", "50.0"))
TIER2_TP_PCT = float(os.getenv("TIER2_TP_PCT", "250.0"))      # Tier 2 (+250%): Sell 25% for high profit
TIER2_SELL_PCT = float(os.getenv("TIER2_SELL_PCT", "25.0"))
MOONBAG_TRAILING_DROP_PCT = float(os.getenv("MOONBAG_TRAILING_DROP_PCT", "22.0")) # Wide trail for remaining 25% moonbag
RUNNER_HOLD_SECONDS = int(os.getenv("RUNNER_HOLD_SECONDS", "1200"))                # 20 min hold window for runners

# Pre-Graduation Raydium Migration Tracker (~70% to ~98% bonding curve)
PUMP_PRE_GRADUATION_TRACKING = os.getenv("PUMP_PRE_GRADUATION_TRACKING", "True").lower() == "true"
PUMP_GRADUATION_MIN_SOL = float(os.getenv("PUMP_GRADUATION_MIN_SOL", "65.0"))
PUMP_GRADUATION_MAX_SOL = float(os.getenv("PUMP_GRADUATION_MAX_SOL", "84.0"))

# Quantitative Machine Learning Engine (XGBoost, Pandas, Vector Clone Auditor)
ML_FILTER_ENABLED = os.getenv("ML_FILTER_ENABLED", "True").lower() == "true"
MAX_RUG_PROBABILITY = float(os.getenv("MAX_RUG_PROBABILITY", "0.45"))   # Max 45% rug probability allowed
MIN_ML_ALPHA_SCORE = float(os.getenv("MIN_ML_ALPHA_SCORE", "60.0"))     # Min 60/100 Breakout Alpha
MAX_CLONE_RISK = float(os.getenv("MAX_CLONE_RISK", "70.0"))             # Max 70% template clone similarity
ML_AUTO_RETRAIN = os.getenv("ML_AUTO_RETRAIN", "True").lower() == "true"




def load_wallet():
    """
    Safely loads the Solana Keypair from environment.
    Supports Base58 string (Phantom/Solflare) or JSON byte array.
    Returns (keypair, wallet_address) or (None, None) if not configured.
    """
    private_key_str = os.getenv("SOLANA_PRIVATE_KEY")
    if not private_key_str:
        return None, None

    raw = private_key_str.strip().strip("'\"")
    if raw in ["your_private_key_here", ""]:
        return None, None

    try:
        from solders.keypair import Keypair
        import base58

        if raw.startswith("["):
            key_bytes = bytes(json.loads(raw))
        else:
            key_bytes = base58.b58decode(raw)

        kp = Keypair.from_bytes(key_bytes)
        return kp, str(kp.pubkey())
    except Exception as e:
        print(f"⚠️ Error parsing SOLANA_PRIVATE_KEY: {e}")
        return None, None
