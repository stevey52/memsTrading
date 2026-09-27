import time
import sys
import requests

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from safety import check_token_safety, check_token_holders_distribution
from trader import get_quote
from config import (
    WSOL_MINT,
    MIN_LIQUIDITY_USD,
    MIN_5M_VOLUME_USD,
    MIN_BUY_SELL_RATIO,
    SCAN_INTERVAL_SECONDS,
    REQUIRE_SOCIALS,
    REQUIRE_TWITTER,
    REQUIRE_TELEGRAM,
)

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
DEXSCREENER_PROFILES_API = "https://api.dexscreener.com/token-profiles/latest/v1"
DEXSCREENER_BOOSTS_API = "https://api.dexscreener.com/token-boosts/latest/v1"
DEXSCREENER_TOKEN_API = "https://api.dexscreener.com/latest/dex/tokens/"

session = requests.Session()
session.headers.update(HEADERS)


class TokenScanner:
    def __init__(
        self,
        min_liquidity: float = MIN_LIQUIDITY_USD,
        min_5m_volume: float = MIN_5M_VOLUME_USD,
        min_buy_sell_ratio: float = MIN_BUY_SELL_RATIO,
        min_5m_change_pct: float = 3.0,
        max_5m_change_pct: float = 25.0,
        cooldown_sec: float = 90.0,
        log_callback=None,
    ):
        self.min_liquidity = min_liquidity
        self.min_5m_volume = min_5m_volume
        self.min_buy_sell_ratio = min_buy_sell_ratio
        self.min_5m_change_pct = min_5m_change_pct
        self.max_5m_change_pct = max_5m_change_pct
        self.cooldown_sec = cooldown_sec
        self.log_callback = log_callback
        # mint -> timestamp of last analysis
        self.seen_tokens: dict[str, float] = {}

    def log(self, text: str, level: str = "info", ticker: str | None = None):
        if self.log_callback:
            try:
                self.log_callback(text, level, ticker)
            except TypeError:
                self.log_callback(text, level)
        else:
            ts = time.strftime("%H:%M:%S")
            print(f"[{ts}] 📡 {text}")

    def fetch_candidate_mints(self) -> list[str]:
        """
        Gathers newly profiled and boosted Solana tokens from DexScreener,
        filtering out tokens analyzed within cooldown window.
        """
        candidates = []
        now = time.time()

        # 1. Fetch latest token profiles
        try:
            res = session.get(DEXSCREENER_PROFILES_API, timeout=10)
            if res.status_code == 200:
                data = res.json()
                for item in data:
                    if item.get("chainId") == "solana":
                        addr = item.get("tokenAddress")
                        if addr and (now - self.seen_tokens.get(addr, 0) > self.cooldown_sec):
                            candidates.append(addr)
        except Exception as e:
            self.log(f"⚠️ Error fetching profiles: {e}", "warning")

        # 2. Fetch latest boosted tokens
        try:
            res = session.get(DEXSCREENER_BOOSTS_API, timeout=10)
            if res.status_code == 200:
                data = res.json()
                for item in data:
                    if item.get("chainId") == "solana":
                        addr = item.get("tokenAddress")
                        if addr and addr not in candidates and (now - self.seen_tokens.get(addr, 0) > self.cooldown_sec):
                            candidates.append(addr)
        except Exception as e:
            self.log(f"⚠️ Error fetching boosts: {e}", "warning")

        return candidates

    def analyze_token_pair(self, primary_pair: dict) -> tuple[dict | None, str]:
        """
        Inspects liquidity, volume, order flow, safety, and Jupiter routability for a pair.
        Returns (token_info_or_None, reason_if_skipped).
        """
        token_mint = primary_pair.get("baseToken", {}).get("address")
        symbol = primary_pair.get("baseToken", {}).get("symbol", "UNKNOWN")
        liquidity_usd = float((primary_pair.get("liquidity") or {}).get("usd") or 0)
        volume_5m = float((primary_pair.get("volume") or {}).get("m5") or 0)
        change_5m = float((primary_pair.get("priceChange") or {}).get("m5") or 0)

        txns_5m = (primary_pair.get("txns") or {}).get("m5") or {}
        buys_5m = int(txns_5m.get("buys") or 0)
        sells_5m = int(txns_5m.get("sells") or 0)

        # Check 1: Liquidity Filter
        if liquidity_usd < self.min_liquidity:
            return None, f"Low Liq (${liquidity_usd:,.0f} < ${self.min_liquidity:,.0f})"

        # Check 2: 5m Volume Filter
        if volume_5m < self.min_5m_volume:
            return None, f"Low 5m Vol (${volume_5m:,.0f} < ${self.min_5m_volume:,.0f})"

        # Check 3: Momentum Range (e.g. +3% to +25%)
        if not (self.min_5m_change_pct <= change_5m <= self.max_5m_change_pct):
            return None, f"Momentum out of range ({change_5m:+.1f}%)"

        # Check 4: Positive Net Order Flow & Strong Buyer Dominance
        if sells_5m == 0:
            ratio = float(buys_5m) if buys_5m > 0 else 1.0
        else:
            ratio = buys_5m / sells_5m

        if ratio < self.min_buy_sell_ratio:
            return None, f"Weak buyer ratio ({ratio:.1f}x < {self.min_buy_sell_ratio:.1f}x)"

        # Check 5: RugCheck Safety Filter
        is_safe, reason = check_token_safety(token_mint)
        if not is_safe:
            return None, f"RugCheck unsafe: {reason}"

        # Check 6: Extract Socials & Metadata from DexScreener Info
        info = primary_pair.get("info") or {}
        websites = info.get("websites") or []
        socials_list = info.get("socials") or []
        twitter_url = None
        telegram_url = None
        website_url = None

        for s in socials_list:
            stype = (s.get("type") or "").lower()
            surl = s.get("url")
            if stype in ("twitter", "x"):
                twitter_url = surl
            elif stype in ("telegram", "tg"):
                telegram_url = surl

        for w in websites:
            if w.get("url"):
                website_url = w.get("url")
                break

        social_data = {
            "twitter": twitter_url,
            "telegram": telegram_url,
            "website": website_url,
            "description": info.get("header") or "",
        }

        if REQUIRE_SOCIALS and not (twitter_url or telegram_url):
            return None, "No socials found in DexScreener profile"
        if REQUIRE_TWITTER and not twitter_url:
            return None, "No Twitter found in DexScreener profile"
        if REQUIRE_TELEGRAM and not telegram_url:
            return None, "No Telegram found in DexScreener profile"

        # Check 7: On-Chain Holder Distribution & Anti-Cabal Check
        holders_ok, holder_reason, holder_stats = check_token_holders_distribution(token_mint)
        if not holders_ok:
            return None, f"Holders unsafe: {holder_reason}"

        # Check 8: Verify Jupiter Routability (Must be tradable)
        test_quote = get_quote(WSOL_MINT, token_mint, 10_000_000, slippage_bps=800)
        if not test_quote:
            return None, "Jupiter route unavailable"

        name = primary_pair.get("baseToken", {}).get("name") or symbol

        return {
            "mint": token_mint,
            "symbol": symbol,
            "name": name,
            "liquidity_usd": liquidity_usd,
            "volume_5m": volume_5m,
            "change_5m": change_5m,
            "buys_5m": buys_5m,
            "sells_5m": sells_5m,
            "ratio": ratio,
            "dex": primary_pair.get("dexId"),
            "url": primary_pair.get("url"),
            "socials": social_data,
            "holders": holder_stats,
        }, "Approved"

    def scan_next_candidate(self) -> dict | None:
        """
        Polls DexScreener for candidate tokens using high-performance batch queries
        and returns the first qualified match while logging progress.
        """
        candidates = self.fetch_candidate_mints()
        now = time.time()
        for mint in candidates:
            self.seen_tokens[mint] = now

        if not candidates:
            # All previously seen candidates are currently cooling down
            active_cooling = len([m for m, t in self.seen_tokens.items() if now - t <= self.cooldown_sec])
            self.log(f"Polling DexScreener... ({active_cooling} candidates in cooldown)", "info")
            return None

        self.log(f"Evaluating {len(candidates)} candidate token(s)...", "info")

        # Process in batches of up to 30 mints per DexScreener API call
        batch_size = 30
        skipped_reasons = {}

        for i in range(0, len(candidates), batch_size):
            batch = candidates[i : i + batch_size]
            url = DEXSCREENER_TOKEN_API + ",".join(batch)
            try:
                res = session.get(url, timeout=10)
                if res.status_code != 200:
                    continue
                data = res.json()
                pairs = data.get("pairs") or []
                if not pairs:
                    continue

                # Group pairs by token mint
                solana_pairs = [p for p in pairs if p.get("chainId") == "solana"]
                by_mint: dict[str, list] = {}
                for p in solana_pairs:
                    m = p.get("baseToken", {}).get("address")
                    if m:
                        by_mint.setdefault(m, []).append(p)

                for mint in batch:
                    token_pairs = by_mint.get(mint, [])
                    if not token_pairs:
                        skipped_reasons["No Solana pair"] = skipped_reasons.get("No Solana pair", 0) + 1
                        continue

                    # Select primary pool with highest USD liquidity
                    primary = max(
                        token_pairs,
                        key=lambda p: float((p.get("liquidity") or {}).get("usd") or 0),
                    )

                    token_info, reason = self.analyze_token_pair(primary)
                    if token_info:
                        self.log(
                            f"🔥 Approved: {token_info['symbol']} (${token_info['liquidity_usd']:,.0f} Liq | ${token_info['volume_5m']:,.0f} 5m Vol)",
                            "success",
                            ticker=token_info["symbol"],
                        )
                        return token_info

                    cat = reason.split("(")[0].strip()
                    skipped_reasons[cat] = skipped_reasons.get(cat, 0) + 1

            except Exception as e:
                self.log(f"⚠️ Batch analysis error: {e}", "warning")
                continue

        # Print concise telemetry breakdown of scanned batch
        summary_str = ", ".join([f"{count} {reason}" for reason, count in skipped_reasons.items()][:4])
        if summary_str:
            self.log(f"Filter Summary: {summary_str}", "info")

        return None
