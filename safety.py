import sys
import requests
from config import (
    MAX_RUGCHECK_SCORE,
    RUGCHECK_FAIL_OPEN,
    MAX_DEV_HOLDING_PCT,
    MAX_TOP10_NON_CURVE_PCT,
    RPC_URL,
)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

HEADERS = {"User-Agent": "Mozilla/5.0"}

FALLBACK_RPCS = [
    RPC_URL,
    "https://api.mainnet-beta.solana.com",
    "https://solana-rpc.publicnode.com",
]


def rpc_call(method: str, params: list, timeout: float = 6) -> dict | None:
    """Makes a Solana JSON-RPC call with multi-node failover."""
    seen = set()
    for endpoint in FALLBACK_RPCS:
        if endpoint in seen or not endpoint:
            continue
        seen.add(endpoint)
        payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
        try:
            res = requests.post(
                endpoint,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=timeout,
            ).json()
            if "result" in res:
                return res["result"]
        except Exception:
            continue
    return None


def check_token_safety(token_mint: str, max_allowed_score: int = MAX_RUGCHECK_SCORE) -> tuple[bool, str]:
    """
    Evaluates token risk using RugCheck.xyz.
    Returns (is_safe: bool, reason: str).
    """
    url = f"https://api.rugcheck.xyz/v1/tokens/{token_mint}/report/summary"
    try:
        res = requests.get(url, headers=HEADERS, timeout=6)
        if res.status_code != 200:
            if RUGCHECK_FAIL_OPEN:
                return True, f"RugCheck unavailable (HTTP {res.status_code}) - allowed with caution"
            return False, f"RugCheck report unavailable (HTTP {res.status_code}) - rejected for safety"

        data = res.json()
        score = data.get("score", 0)
        risks = data.get("risks", [])

        danger_flags = [r.get("name") for r in risks if r.get("level") == "danger"]

        # Check for critical red flags
        if danger_flags:
            return False, f"Danger flags detected: {', '.join(danger_flags)}"

        if score > max_allowed_score:
            return False, f"Rug score {score} exceeds limit {max_allowed_score}"

        lp_locked = data.get("lpLockedPct", 0)
        return True, f"Passed safety (Score: {score}, LP: {lp_locked}%)"

    except Exception as e:
        if RUGCHECK_FAIL_OPEN:
            return True, f"Safety check skipped due to error: {e}"
        return False, f"RugCheck query failed ({e}) - rejected for safety"


def check_token_holders_distribution(
    token_mint: str,
    bonding_curve_key: str | None = None,
    max_single_pct: float = MAX_DEV_HOLDING_PCT,
    max_top10_pct: float = MAX_TOP10_NON_CURVE_PCT,
    rpc_url: str = RPC_URL,
) -> tuple[bool, str, dict]:
    """
    Queries Solana RPC to inspect on-chain token supply distribution.
    Excludes the bonding curve vault to isolate retail/insider holder concentration.
    Returns (is_safe: bool, reason: str, stats: dict).
    """
    stats = {
        "total_supply": 1_000_000_000.0,
        "curve_pct": 0.0,
        "highest_holder_pct": 0.0,
        "top10_non_curve_pct": 0.0,
        "non_curve_holders_count": 0,
    }

    # 1. Fetch total supply
    supply_res = rpc_call("getTokenSupply", [token_mint])
    if supply_res and "value" in supply_res:
        total_supply = float(supply_res["value"].get("uiAmount") or 1_000_000_000.0)
    else:
        total_supply = 1_000_000_000.0
    stats["total_supply"] = total_supply

    # 2. Fetch largest token accounts
    largest_res = rpc_call("getTokenLargestAccounts", [token_mint])
    if not largest_res or "value" not in largest_res:
        # If RPC fails to return accounts, allow with caution or fail depending on RUGCHECK_FAIL_OPEN
        if RUGCHECK_FAIL_OPEN:
            return True, "Holder distribution check skipped (RPC unavailable)", stats
        return False, "Could not fetch holder distribution via RPC", stats

    accounts = largest_res["value"]
    if not accounts:
        return True, "No accounts found (Brand new launch)", stats

    # 3. Categorize bonding curve vs non-curve accounts
    curve_account = None
    non_curve_accounts = []

    for acc in accounts:
        addr = acc.get("address")
        ui_amt = float(acc.get("uiAmount") or 0.0)
        pct = (ui_amt / total_supply) * 100 if total_supply > 0 else 0.0

        # Bonding curve usually holds >= 40% of supply at launch, or matches bonding_curve_key
        is_curve = False
        if bonding_curve_key and addr == bonding_curve_key:
            is_curve = True
        elif curve_account is None and pct >= 35.0:
            is_curve = True

        if is_curve and curve_account is None:
            curve_account = (addr, pct)
        else:
            non_curve_accounts.append(pct)

    if curve_account:
        stats["curve_pct"] = curve_account[1]

    stats["non_curve_holders_count"] = len(non_curve_accounts)

    if not non_curve_accounts:
        # Only the bonding curve holds tokens
        return True, "100% of tokens in bonding curve (no external holders yet)", stats

    highest_holder_pct = max(non_curve_accounts)
    top10_non_curve_pct = sum(sorted(non_curve_accounts, reverse=True)[:10])

    stats["highest_holder_pct"] = highest_holder_pct
    stats["top10_non_curve_pct"] = top10_non_curve_pct

    # Filter Rule 1: Single holder concentration (Whale / Dev wallet)
    if highest_holder_pct > max_single_pct:
        return (
            False,
            f"Concentration Risk: Largest individual holder owns {highest_holder_pct:.1f}% (Limit: {max_single_pct:.1f}%)",
            stats,
        )

    # Filter Rule 2: Top 10 non-curve holders concentration (Cabal / Bundle Farm)
    if top10_non_curve_pct > max_top10_pct:
        return (
            False,
            f"Cabal Bundle Risk: Top non-curve holders own {top10_non_curve_pct:.1f}% (Limit: {max_top10_pct:.1f}%)",
            stats,
        )

    return (
        True,
        f"Healthy Distribution (Top Holder: {highest_holder_pct:.1f}%, Top 10: {top10_non_curve_pct:.1f}%)",
        stats,
    )
