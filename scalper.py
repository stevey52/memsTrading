import time
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from trader import buy_token, sell_token, get_sell_value_sol, get_quote
from config import (
    RPC_URL,
    WSOL_MINT,
    TAKE_PROFIT_PCT,
    STOP_LOSS_PCT,
    TRAILING_STOP_ENABLED,
    TRAILING_TRIGGER_PCT,
    TRAILING_DROP_PCT,
    BREAKEVEN_PROTECTION_ENABLED,
    BREAKEVEN_TRIGGER_PCT,
    MAX_HOLD_SECONDS,
    SLIPPAGE_BPS,
)


def run_scalp_position(
    token_mint: str,
    sol_amount: float,
    keypair=None,
    rpc_url: str = RPC_URL,
    dry_run: bool = False,
    tp_pct: float = TAKE_PROFIT_PCT,
    sl_pct: float = STOP_LOSS_PCT,
    trailing_enabled: bool = TRAILING_STOP_ENABLED,
    trailing_trigger: float = TRAILING_TRIGGER_PCT,
    trailing_drop: float = TRAILING_DROP_PCT,
    breakeven_enabled: bool = BREAKEVEN_PROTECTION_ENABLED,
    breakeven_trigger: float = BREAKEVEN_TRIGGER_PCT,
    max_hold_sec: int = MAX_HOLD_SECONDS,
    slippage_bps: int = SLIPPAGE_BPS,
):
    """
    Manages an active scalp trade from entry to exit.
    Supports dry-run (paper trading) or live on-chain execution.
    """
    mode_str = "🧪 [PAPER / DRY RUN]" if dry_run else "⚡ [LIVE ON-CHAIN]"
    print("\n" + "=" * 65)
    print(f"{mode_str} STARTING SCALP: {token_mint}")
    print(f"💰 Size: {sol_amount} SOL | TP: +{tp_pct}% | SL: -{sl_pct}%")
    print(f"📈 Trailing Stop: {trailing_enabled} (Active at +{trailing_trigger}%, Trail {trailing_drop}%)")
    print(f"⏱️ Max Hold: {max_hold_sec}s | Slippage: {slippage_bps / 100}%")
    print("=" * 65)

    # 1. Entry Buy
    tokens_acquired = 0
    if dry_run:
        lamports = int(sol_amount * 1_000_000_000)
        quote = get_quote(WSOL_MINT, token_mint, lamports, slippage_bps)
        if not quote:
            print("❌ Paper trade failed: No liquidity route found on Jupiter.")
            return False
        tokens_acquired = int(quote.get("outAmount", 0))
        print(f"✅ Paper BUY Simulated! Acquired: {tokens_acquired:,} tokens")
    else:
        if not keypair:
            print("❌ Live trading requested, but wallet is not configured.")
            return False

        print(f"🛒 Broadcasting live BUY order for {sol_amount} SOL...")
        tx_id, tokens_acquired = buy_token(token_mint, sol_amount, keypair, slippage_bps, rpc_url)
        if not tx_id or tokens_acquired <= 0:
            print("❌ Live BUY transaction failed. Aborting scalp.")
            return False
        print(f"✅ Live BUY Confirmed! Tx: https://solscan.io/tx/{tx_id}")
        print(f"📦 Tokens Acquired: {tokens_acquired:,}")

    entry_sol = sol_amount
    start_time = time.time()
    peak_pnl = 0.0
    trailing_active = False
    breakeven_active = False
    exit_reason = "Manual / Unspecified"

    print("\n📊 Active Position Telemetry (Polling Jupiter quote every 2s)...")
    print("-" * 65)

    # 2. Position Monitoring Loop
    try:
        while True:
            time.sleep(2.0)
            elapsed = int(time.time() - start_time)

            current_sol = get_sell_value_sol(token_mint, tokens_acquired, slippage_bps)
            if current_sol <= 0:
                continue

            pnl_pct = ((current_sol - entry_sol) / entry_sol) * 100
            if pnl_pct > peak_pnl:
                peak_pnl = pnl_pct

            # Colorized output: Green if positive, Red if negative
            color = "\033[92m" if pnl_pct >= 0 else "\033[91m"
            reset = "\033[0m"
            print(f"⏱️ {elapsed:03d}s | Value: {current_sol:.4f} SOL | PnL: {color}{pnl_pct:+.2f}%{reset} (Peak: {peak_pnl:+.2f}%)")

            # Check Condition 1: Breakeven Floor Protection
            if breakeven_enabled:
                if not breakeven_active and peak_pnl >= breakeven_trigger:
                    breakeven_active = True
                    print(f"🛡️ Breakeven Protection ACTIVATED (+{peak_pnl:.2f}% peak)! Floor locked at +0.50%.")

                if breakeven_active and pnl_pct <= 0.5:
                    exit_reason = f"Breakeven Floor Hit (+0.50% locked after +{peak_pnl:.2f}% peak)"
                    break

            # Check Condition 2: Trailing Stop
            if trailing_enabled:
                if not trailing_active and peak_pnl >= trailing_trigger:
                    trailing_active = True
                    print(f"🚀 Trailing Stop ACTIVATED at +{peak_pnl:.2f}%! Locking gains...")

                if trailing_active and (peak_pnl - pnl_pct) >= trailing_drop:
                    exit_reason = f"Trailing Stop Triggered (Dropped {trailing_drop}% from peak {peak_pnl:.2f}%)"
                    break

            # Check Condition 3: Hard Take Profit
            if pnl_pct >= tp_pct:
                exit_reason = f"Hard Take Profit (+{tp_pct}%) Reached"
                break

            # Check Condition 4: Hard Stop Loss
            if pnl_pct <= -sl_pct:
                exit_reason = f"Hard Stop Loss (-{sl_pct}%) Triggered"
                break

            # Check Condition 5: Max Hold Stagnation
            if elapsed >= max_hold_sec:
                exit_reason = f"Max Hold Duration Reached ({max_hold_sec}s - Stagnation Exit)"
                break

    except KeyboardInterrupt:
        exit_reason = "User Keyboard Interrupt (Emergency Sell)"

    # 3. Exit Sell
    print("\n" + "-" * 65)
    print(f"🔔 EXIT TRIGGERED: {exit_reason}")
    print(f"📤 Executing SELL order for {tokens_acquired:,} tokens...")

    final_sol = current_sol
    if not dry_run:
        sell_tx, out_lamports = sell_token(token_mint, tokens_acquired, keypair, slippage_bps, rpc_url)
        if sell_tx:
            if out_lamports > 0:
                final_sol = out_lamports / 1_000_000_000
            print(f"✅ Live SELL Confirmed! Tx: https://solscan.io/tx/{sell_tx}")
        else:
            print("🚨 CRITICAL: Live sell transaction failed! Please inspect wallet immediately.")

    net_profit = final_sol - entry_sol
    realized_pct = ((final_sol - entry_sol) / entry_sol) * 100
    color = "\033[92m" if net_profit >= 0 else "\033[91m"
    reset = "\033[0m"

    print("=" * 65)
    print(f"🏁 SCALP COMPLETE: Entry: {entry_sol:.4f} SOL -> Exit: {final_sol:.4f} SOL")
    print(f"💰 Realized Net Profit: {color}{'+' if net_profit >= 0 else ''}{net_profit:.4f} SOL ({realized_pct:+.2f}%){reset}")
    print("=" * 65 + "\n")
    return True
