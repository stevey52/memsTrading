import sys
import json
import time
import ssl
from websockets.sync.client import connect
from safety import check_token_safety, check_token_holders_distribution
from social_checker import check_token_socials
from trader import get_quote
import config
from config import (
    WSOL_MINT,
    PUMP_MIN_DEV_BUY_SOL,
    PUMP_MAX_DEV_BUY_SOL,
    PUMP_MIN_MARKET_CAP_SOL,
    REQUIRE_SOCIALS,
    PUMP_PRE_GRADUATION_TRACKING,
    PUMP_GRADUATION_MIN_SOL,
    PUMP_GRADUATION_MAX_SOL,
)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

PUMPPORTAL_WS_URL = "wss://pumpportal.fun/api/data"

try:
    import certifi
    SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
except Exception:
    SSL_CONTEXT = ssl.create_default_context()


class PumpFunScanner:
    def __init__(
        self,
        min_dev_buy_sol: float = PUMP_MIN_DEV_BUY_SOL,
        max_dev_buy_sol: float = PUMP_MAX_DEV_BUY_SOL,
        min_market_cap_sol: float = PUMP_MIN_MARKET_CAP_SOL,
        log_callback=None,
    ):
        self.min_dev_buy_sol = min_dev_buy_sol
        self.max_dev_buy_sol = max_dev_buy_sol
        self.min_market_cap_sol = min_market_cap_sol
        self.log_callback = log_callback
        self.seen_tokens = set()

    def log(self, text: str, level: str = "info", ticker: str | None = None):
        if self.log_callback:
            try:
                self.log_callback(text, level, ticker)
            except TypeError:
                self.log_callback(text, level)
        else:
            ts = time.strftime("%H:%M:%S")
            print(f"[{ts}] 💊 {text}")

    def stream_candidates(self):
        """
        Connects to PumpPortal WebSocket, filters for committed dev launches
        and pre-graduation Raydium migration surges, validates social OSINT,
        audits on-chain holder distribution, and yields verified tokens.
        """
        while True:
            try:
                self.log(f"Connecting to Pump.fun live stream ({PUMPPORTAL_WS_URL})...", "info")
                with connect(PUMPPORTAL_WS_URL, ping_interval=None, close_timeout=5, ssl_context=SSL_CONTEXT) as ws:
                    ws.send(json.dumps({"method": "subscribeNewToken"}))
                    if config.PUMP_PRE_GRADUATION_TRACKING:
                        ws.send(json.dumps({"method": "subscribeRaydiumLiquidity"}))

                    self.log(
                        f"Subscribed to Pump.fun launches & Raydium graduations! "
                        f"(Dev: {self.min_dev_buy_sol}-{self.max_dev_buy_sol} SOL, "
                        f"Pre-Grad: {'ON' if config.PUMP_PRE_GRADUATION_TRACKING else 'OFF'}, "
                        f"Socials: {'REQUIRED' if REQUIRE_SOCIALS else 'OFF'})",
                        "success",
                    )

                    while True:
                        try:
                            msg = ws.recv()
                        except Exception:
                            break
                        try:
                            data = json.loads(msg)
                        except Exception:
                            continue

                        mint = data.get("mint")
                        if not mint or mint in self.seen_tokens:
                            continue

                        self.seen_tokens.add(mint)
                        sol_amount = float(data.get("solAmount") or 0.0)
                        symbol = data.get("symbol") or "PUMP"
                        name = data.get("name") or "Unknown"
                        market_cap_sol = float(data.get("marketCapSol") or 30.0)
                        uri = data.get("uri")
                        bonding_curve = data.get("bondingCurveKey")

                        # Calculate bonding curve progress (30 SOL = 0%, 85 SOL = 100% Raydium migration)
                        curve_progress_pct = round(min(100.0, max(0.0, ((market_cap_sol - 30.0) / (85.0 - 30.0)) * 100)), 1)
                        is_pre_grad = config.PUMP_PRE_GRADUATION_TRACKING and (
                            (config.PUMP_GRADUATION_MIN_SOL <= market_cap_sol <= config.PUMP_GRADUATION_MAX_SOL) or
                            data.get("raydiumPool") is not None
                        )

                        # Filter 1: Dev Initial Buy Commitment (for fresh tokens; pre-grad tokens already proved market demand)
                        if not is_pre_grad and not (self.min_dev_buy_sol <= sol_amount <= self.max_dev_buy_sol):
                            continue

                        # Filter 2: Market Cap / Bonding Curve Stage
                        if market_cap_sol < self.min_market_cap_sol:
                            continue

                        if is_pre_grad:
                            self.log(
                                f"🎓 Pre-Graduation / Raydium Breakout: {symbol} ({mint[:6]}...) | Curve: {curve_progress_pct}% | MC: {market_cap_sol:.1f} SOL",
                                "success",
                                ticker=symbol,
                            )
                        else:
                            self.log(
                                f"Inspecting fresh token: {symbol} ({mint[:6]}...) | Dev Buy: {sol_amount:.2f} SOL | MC: {market_cap_sol:.1f} SOL",
                                "info",
                                ticker=symbol,
                            )

                        # Filter 3: Social Footprint & OSINT Verification (Twitter, Telegram, Web)
                        social_ok, social_reason, social_data = check_token_socials(uri, symbol=symbol, name=name)
                        if not social_ok:
                            self.log(f"⛔ Skipped {symbol}: {social_reason}", "warning", ticker=symbol)
                            continue
                        self.log(f"📱 Socials Approved: {social_reason}", "info", ticker=symbol)

                        # Filter 4: RugCheck Safety Analysis (Danger flags, rug score)
                        is_safe, rug_reason = check_token_safety(mint)
                        if not is_safe:
                            self.log(f"⛔ Safety Skipped {symbol}: {rug_reason}", "danger", ticker=symbol)
                            continue

                        # Filter 5: On-Chain Cabal & Top Holder Distribution Check
                        holders_ok, holder_reason, holder_stats = check_token_holders_distribution(
                            mint, bonding_curve_key=bonding_curve
                        )
                        if not holders_ok:
                            self.log(f"⛔ Holders Skipped {symbol}: {holder_reason}", "warning", ticker=symbol)
                            continue
                        self.log(f"👥 Holders Approved: {holder_reason}", "info", ticker=symbol)

                        # Filter 6: Jupiter Routability Check
                        test_quote = get_quote(WSOL_MINT, mint, 10_000_000, slippage_bps=1000)
                        if not test_quote:
                            self.log(f"⚠️ {symbol} not yet routable on Jupiter, skipping", "warning", ticker=symbol)
                            continue

                        yield {
                            "mint": mint,
                            "symbol": symbol,
                            "name": name,
                            "dev_sol": sol_amount,
                            "market_cap_sol": market_cap_sol,
                            "curve_progress_pct": curve_progress_pct,
                            "pre_graduation": is_pre_grad,
                            "bonding_curve": bonding_curve,
                            "socials": social_data,
                            "holders": holder_stats,
                            "dex": "raydium" if data.get("raydiumPool") else "pumpfun",
                            "url": f"https://pump.fun/{mint}",
                        }

            except Exception as e:
                self.log(f"⚠️ Pump.fun stream disconnected: {e}. Reconnecting in 3s...", "warning")
                time.sleep(3)
