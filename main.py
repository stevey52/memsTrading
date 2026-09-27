import argparse
import time
import sys
import queue
import threading

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from config import (
    RPC_URL,
    TRADE_AMOUNT_SOL,
    SLIPPAGE_BPS,
    TAKE_PROFIT_PCT,
    STOP_LOSS_PCT,
    TRAILING_STOP_ENABLED,
    TRAILING_TRIGGER_PCT,
    TRAILING_DROP_PCT,
    BREAKEVEN_PROTECTION_ENABLED,
    BREAKEVEN_TRIGGER_PCT,
    MIN_BUY_SELL_RATIO,
    MAX_HOLD_SECONDS,
    SCAN_INTERVAL_SECONDS,
    PUMP_MIN_DEV_BUY_SOL,
    PUMP_MAX_DEV_BUY_SOL,
    load_wallet,
)
from safety import check_token_safety, check_token_holders_distribution
from scanner import TokenScanner
from pump_scanner import PumpFunScanner
from scalper import run_scalp_position
from trader import get_quote, WSOL_MINT, get_wallet_sol_balance


def banner():
    print("""
===============================================================
       ⚡ SOLANA SHITCOIN SNIPER & SCALP TRADING BOT ⚡
===============================================================
    """)


def verify_funds_for_trade(wallet_address: str, required_amount: float) -> bool:
    balance = get_wallet_sol_balance(wallet_address)
    buffer = 0.003
    total_needed = required_amount + buffer
    if balance < total_needed:
        print(f"\n❌ Insufficient SOL Balance for Live Trading!")
        print(f"   Wallet Address: {wallet_address}")
        print(f"   Current Balance: {balance:.4f} SOL")
        print(f"   Required: {total_needed:.4f} SOL ({required_amount} SOL buy + {buffer} SOL network fee buffer)")
        print(f"👉 Please send SOL to your Phantom wallet before running live trades.")
        print(f"💡 You can test immediately in Paper Trading mode (e.g. Option 1) for free!\n")
        return False
    return True


def direct_scalp(mint: str, amount_sol: float, dry_run: bool):
    """Executes a scalp trade on a specific token mint."""
    keypair, wallet_address = load_wallet()

    if not dry_run:
        if not keypair:
            print("❌ Cannot run live trade: SOLANA_PRIVATE_KEY is not configured in .env.")
            print("💡 You can run with --dry-run to test in Paper Trading mode.")
            return
        if not verify_funds_for_trade(wallet_address, amount_sol):
            return

    # 1. Safety & Anti-Rug check
    is_safe, reason = check_token_safety(mint)
    print(f"🛡️ Safety verification: {reason}")
    if not is_safe:
        proceed = input("⚠️ Token failed safety filter. Proceed anyway? (y/N): ").strip().lower()
        if proceed != "y":
            print("❌ Scalp canceled.")
            return

    # 2. On-Chain Holder Distribution check
    h_safe, h_reason, h_stats = check_token_holders_distribution(mint)
    print(f"👥 Holder distribution: {h_reason}")
    if not h_safe:
        proceed = input("⚠️ Token failed holder distribution filter. Proceed anyway? (y/N): ").strip().lower()
        if proceed != "y":
            print("❌ Scalp canceled.")
            return

    # 3. Run Scalp
    run_scalp_position(
        token_mint=mint,
        sol_amount=amount_sol,
        keypair=keypair,
        rpc_url=RPC_URL,
        dry_run=dry_run,
        tp_pct=TAKE_PROFIT_PCT,
        sl_pct=STOP_LOSS_PCT,
        trailing_enabled=TRAILING_STOP_ENABLED,
        trailing_trigger=TRAILING_TRIGGER_PCT,
        trailing_drop=TRAILING_DROP_PCT,
        breakeven_enabled=BREAKEVEN_PROTECTION_ENABLED,
        breakeven_trigger=BREAKEVEN_TRIGGER_PCT,
        max_hold_sec=MAX_HOLD_SECONDS,
        slippage_bps=SLIPPAGE_BPS
    )


def continuous_scanner_and_scalp(amount_sol: float, dry_run: bool):
    """
    Continuously monitors DexScreener for surging, safe tokens
    and immediately launches the scalp manager.
    """
    keypair, wallet_address = load_wallet()

    if not dry_run:
        if not keypair:
            print("❌ Live trading enabled, but SOLANA_PRIVATE_KEY is missing from .env.")
            print("💡 Switching automatically to --dry-run (Paper Trading) mode.")
            dry_run = True
        elif not verify_funds_for_trade(wallet_address, amount_sol):
            return

    scanner = TokenScanner()
    mode = "🧪 PAPER TRADING" if dry_run else "⚡ LIVE TRADING"
    print(f"\n📡 Starting DexScreener Momentum Scanner [{mode}]...")
    print(f"🔍 Min Liq: ${scanner.min_liquidity:,.0f} | Min 5m Vol: ${scanner.min_5m_volume:,.0f} | Min Buy/Sell Ratio: {scanner.min_buy_sell_ratio}x")
    print(f"🎯 Target Size: {amount_sol} SOL | Polling every {SCAN_INTERVAL_SECONDS}s...")
    print("Press Ctrl+C at any time to stop.\n")

    try:
        while True:
            print(f"[{time.strftime('%H:%M:%S')}] 🔎 Scanning DexScreener profiles & boosts...")
            token = scanner.scan_next_candidate()

            if token:
                print("\n" + "🔥" * 30)
                print(f"🚀 OPPORTUNITY DETECTED: {token['symbol']} ({token['mint']})")
                print(f"💧 Liquidity: ${token['liquidity_usd']:,.0f} | 5m Vol: ${token['volume_5m']:,.0f}")
                print(f"📈 5m Change: +{token['change_5m']:.1f}% | Buys: {token['buys_5m']} / Sells: {token['sells_5m']} (Ratio: {token.get('ratio', 1.0):.1f}x)")
                print(f"🔗 DEX: {token['dex']} | Link: {token['url']}")
                print("🔥" * 30)

                # Launch scalp position
                run_scalp_position(
                    token_mint=token["mint"],
                    sol_amount=amount_sol,
                    keypair=keypair,
                    rpc_url=RPC_URL,
                    dry_run=dry_run,
                    tp_pct=TAKE_PROFIT_PCT,
                    sl_pct=STOP_LOSS_PCT,
                    trailing_enabled=TRAILING_STOP_ENABLED,
                    trailing_trigger=TRAILING_TRIGGER_PCT,
                    trailing_drop=TRAILING_DROP_PCT,
                    breakeven_enabled=BREAKEVEN_PROTECTION_ENABLED,
                    breakeven_trigger=BREAKEVEN_TRIGGER_PCT,
                    max_hold_sec=MAX_HOLD_SECONDS,
                    slippage_bps=SLIPPAGE_BPS
                )

                print("\n💤 Resuming scanner in 5 seconds...")
                time.sleep(5)
            else:
                time.sleep(SCAN_INTERVAL_SECONDS)

    except KeyboardInterrupt:
        print("\n🛑 Scanner stopped by user.")


def pump_fun_sniper_and_scalp(amount_sol: float, dry_run: bool):
    """
    Subscribes to real-time Pump.fun WebSocket events, filters for committed
    dev launches, verifies safety and instant routing, and triggers the scalp manager.
    """
    keypair, wallet_address = load_wallet()

    if not dry_run:
        if not keypair:
            print("❌ Live trading enabled, but SOLANA_PRIVATE_KEY is missing from .env.")
            print("💡 Switching automatically to --dry-run (Paper Trading) mode.")
            dry_run = True
        elif not verify_funds_for_trade(wallet_address, amount_sol):
            return

    mode = "🧪 PAPER TRADING" if dry_run else "⚡ LIVE TRADING"
    print(f"\n💊 Starting Pump.fun Real-Time WebSocket Sniper [{mode}]...")
    print(f"🎯 Dev Buy Filter: >= {PUMP_MIN_DEV_BUY_SOL} SOL | Size: {amount_sol} SOL")
    print("Press Ctrl+C at any time to stop.\n")

    scanner = PumpFunScanner(
        min_dev_buy_sol=PUMP_MIN_DEV_BUY_SOL,
        max_dev_buy_sol=PUMP_MAX_DEV_BUY_SOL,
    )

    try:
        for token in scanner.stream_candidates():
            socials = token.get("socials") or {}
            holders = token.get("holders") or {}
            print("\n" + "🚀" * 30)
            print(f"💊 FRESH PUMP.FUN LAUNCH APPROVED: {token['symbol']} - {token['name']}")
            print(f"🪙 Mint: {token['mint']}")
            print(f"💰 Dev Initial Buy: {token['dev_sol']:.2f} SOL | Market Cap: {token['market_cap_sol']:.1f} SOL")
            if socials.get("twitter"):
                print(f"🐦 Twitter/X: {socials['twitter']}")
            if socials.get("telegram"):
                print(f"✈️ Telegram: {socials['telegram']}")
            if socials.get("website"):
                print(f"🌐 Website: {socials['website']}")
            if holders:
                print(f"👥 Distribution: Top1: {holders.get('highest_holder_pct', 0):.1f}% | Top10: {holders.get('top10_non_curve_pct', 0):.1f}%")
            print(f"🔗 Link: {token['url']}")
            print("🚀" * 30)

            # Launch scalp position
            run_scalp_position(
                token_mint=token["mint"],
                sol_amount=amount_sol,
                keypair=keypair,
                rpc_url=RPC_URL,
                dry_run=dry_run,
                tp_pct=TAKE_PROFIT_PCT,
                sl_pct=STOP_LOSS_PCT,
                trailing_enabled=TRAILING_STOP_ENABLED,
                trailing_trigger=TRAILING_TRIGGER_PCT,
                trailing_drop=TRAILING_DROP_PCT,
                breakeven_enabled=BREAKEVEN_PROTECTION_ENABLED,
                breakeven_trigger=BREAKEVEN_TRIGGER_PCT,
                max_hold_sec=MAX_HOLD_SECONDS,
                slippage_bps=SLIPPAGE_BPS
            )

            print("\n💤 Resuming Pump.fun listener in 3 seconds...")
            time.sleep(3)

    except KeyboardInterrupt:
        print("\n🛑 Pump.fun sniper stopped by user.")


def hybrid_dual_scanner_and_scalp(amount_sol: float, dry_run: bool):
    """
    Runs BOTH DexScreener Momentum Scanner AND Pump.fun Real-Time WebSocket
    concurrently in background threads, feeding verified opportunities into a
    single thread-safe scalp manager.
    """
    keypair, wallet_address = load_wallet()

    if not dry_run:
        if not keypair:
            print("❌ Live trading enabled, but SOLANA_PRIVATE_KEY is missing from .env.")
            print("💡 Switching automatically to --dry-run (Paper Trading) mode.")
            dry_run = True
        elif not verify_funds_for_trade(wallet_address, amount_sol):
            return

    mode = "🧪 PAPER TRADING" if dry_run else "⚡ LIVE TRADING"
    print(f"\n🚀 Starting HYBRID DUAL SCANNER [{mode}]...")
    print(f"📡 Engine 1: DexScreener (Momentum Trends, $12k+ Liq, 1.3x Buy/Sell)")
    print(f"💊 Engine 2: Pump.fun WebSocket (Fresh Launches >= {PUMP_MIN_DEV_BUY_SOL} SOL Dev Buy)")
    print(f"💰 Target Size: {amount_sol} SOL | Both engines listening simultaneously.")
    print("Press Ctrl+C at any time to stop.\n")

    token_queue = queue.Queue()
    stop_event = threading.Event()
    seen_mints = set()
    lock = threading.Lock()

    # 1. Background Worker for DexScreener
    def dexscreener_worker():
        print(f"📡 [DexScreener Engine] Active. Monitoring trending profiles & boosts every {SCAN_INTERVAL_SECONDS}s...")
        scanner = TokenScanner()
        while not stop_event.is_set():
            try:
                candidate = scanner.scan_next_candidate()
                if candidate:
                    with lock:
                        if candidate["mint"] not in seen_mints:
                            seen_mints.add(candidate["mint"])
                            candidate["discovered_at"] = time.time()
                            candidate["source"] = "DexScreener"
                            token_queue.put(candidate)
                            print(f"📥 [DexScreener Queue] Enqueued {candidate['symbol']} for scalp execution!")
            except Exception as e:
                print(f"⚠️ [DexScreener Worker Error]: {e}")
            time.sleep(SCAN_INTERVAL_SECONDS)

    # 2. Background Worker for Pump.fun WebSocket
    def pumpfun_worker():
        pump_scanner = PumpFunScanner(
            min_dev_buy_sol=PUMP_MIN_DEV_BUY_SOL,
            max_dev_buy_sol=PUMP_MAX_DEV_BUY_SOL,
        )
        try:
            for candidate in pump_scanner.stream_candidates():
                if stop_event.is_set():
                    break
                with lock:
                    if candidate["mint"] not in seen_mints:
                        seen_mints.add(candidate["mint"])
                        candidate["discovered_at"] = time.time()
                        candidate["source"] = "Pump.fun"
                        token_queue.put(candidate)
        except Exception:
            pass

    t_dex = threading.Thread(target=dexscreener_worker, daemon=True)
    t_pump = threading.Thread(target=pumpfun_worker, daemon=True)
    t_dex.start()
    t_pump.start()

    # 3. Main Scalp Dispatcher Loop
    try:
        while True:
            try:
                token = token_queue.get(timeout=1.0)
            except queue.Empty:
                continue

            age = time.time() - token.get("discovered_at", time.time())
            # Discard if token sat in queue for too long while previous scalp trade was running
            if age > 45.0:
                print(f"⏳ Candidate {token['symbol']} ({token.get('source')}) expired ({age:.0f}s old). Skipping.")
                continue

            source = token.get("source", "Market")
            socials = token.get("socials") or {}
            holders = token.get("holders") or {}
            print("\n" + "🌟" * 32)
            print(f"🎯 [{source.upper()}] OPPORTUNITY DETECTED: {token['symbol']} ({token['mint']})")
            if source == "DexScreener":
                print(f"💧 Liquidity: ${token['liquidity_usd']:,.0f} | 5m Vol: ${token['volume_5m']:,.0f} | Ratio: {token.get('ratio', 1.0):.1f}x")
            else:
                print(f"💰 Dev Initial Buy: {token['dev_sol']:.2f} SOL | Market Cap: {token['market_cap_sol']:.1f} SOL")
                if socials.get("twitter"):
                    print(f"🐦 Twitter/X: {socials['twitter']}")
                if socials.get("telegram"):
                    print(f"✈️ Telegram: {socials['telegram']}")
                if socials.get("website"):
                    print(f"🌐 Website: {socials['website']}")
                if holders:
                    print(f"👥 Distribution: Top1: {holders.get('highest_holder_pct', 0):.1f}% | Top10: {holders.get('top10_non_curve_pct', 0):.1f}%")
            print(f"🔗 Link: {token['url']}")
            print("🌟" * 32)

            # Launch scalp position
            run_scalp_position(
                token_mint=token["mint"],
                sol_amount=amount_sol,
                keypair=keypair,
                rpc_url=RPC_URL,
                dry_run=dry_run,
                tp_pct=TAKE_PROFIT_PCT,
                sl_pct=STOP_LOSS_PCT,
                trailing_enabled=TRAILING_STOP_ENABLED,
                trailing_trigger=TRAILING_TRIGGER_PCT,
                trailing_drop=TRAILING_DROP_PCT,
                breakeven_enabled=BREAKEVEN_PROTECTION_ENABLED,
                breakeven_trigger=BREAKEVEN_TRIGGER_PCT,
                max_hold_sec=MAX_HOLD_SECONDS,
                slippage_bps=SLIPPAGE_BPS
            )

            print("\n💤 Resuming dual-engine scanning...")

    except KeyboardInterrupt:
        stop_event.set()
        print("\n🛑 Hybrid dual scanner stopped by user.")


def main():
    banner()

    parser = argparse.ArgumentParser(description="Solana Shitcoin Scalper, DexScreener & Pump.fun Scanner")
    parser.add_argument("--web", "--dashboard", action="store_true", help="Launch the real-time Flask Web Dashboard & Trading Terminal")
    parser.add_argument("--mint", type=str, help="Target token mint address for direct scalp")
    parser.add_argument("--scan", action="store_true", help="Run automated DexScreener scanner only")
    parser.add_argument("--pump", action="store_true", help="Run real-time Pump.fun WebSocket sniper only")
    parser.add_argument("--hybrid", action="store_true", help="Run BOTH DexScreener and Pump.fun simultaneously")
    parser.add_argument("--dry-run", action="store_true", help="Paper trading mode (no real SOL spent)")
    parser.add_argument("--sol", type=float, default=TRADE_AMOUNT_SOL, help="Amount of SOL per scalp trade")

    args = parser.parse_args()

    keypair, wallet_address = load_wallet()
    if wallet_address:
        balance = get_wallet_sol_balance(wallet_address)
        print(f"🔑 Loaded Wallet: {wallet_address[:6]}...{wallet_address[-4:]}")
        print(f"💰 Live SOL Balance: {balance:.4f} SOL")
        if balance < TRADE_AMOUNT_SOL + 0.003:
            print(f"⚠️ Notice: Wallet balance is low ({balance:.4f} SOL). Fund with SOL before selecting LIVE TRADING!")
    else:
        print("⚠️ No valid SOLANA_PRIVATE_KEY loaded. Operating in DRY-RUN / PAPER mode by default.")

    if getattr(args, "web", False) or getattr(args, "dashboard", False):
        import subprocess
        subprocess.run([sys.executable, "app.py"])
        return

    if args.mint:
        direct_scalp(args.mint, args.sol, args.dry_run)
    elif args.hybrid:
        hybrid_dual_scanner_and_scalp(args.sol, args.dry_run)
    elif args.pump:
        pump_fun_sniper_and_scalp(args.sol, args.dry_run)
    elif args.scan:
        continuous_scanner_and_scalp(args.sol, args.dry_run)
    else:
        # Interactive prompt if no CLI flags passed
        print("\nSelect an operation mode:")
        print("  0) 🌐 Launch Web Dashboard & Real-Time Trading Terminal (http://127.0.0.1:5000)")
        print("  1) 🚀 HYBRID DUAL SCANNER (DexScreener + Pump.fun) [Paper Trading]")
        print("  2) 💥 HYBRID DUAL SCANNER (DexScreener + Pump.fun) [LIVE REAL SOL]")
        print("  3) 📡 DexScreener Scanner Only (Established Trends) [Paper Trading]")
        print("  4) ⚡ DexScreener Scanner Only (Established Trends) [LIVE REAL SOL]")
        print("  5) 💊 Pump.fun Sniper Only (Fresh Launches) [Paper Trading]")
        print("  6) 🔥 Pump.fun Sniper Only (Fresh Launches) [LIVE REAL SOL]")
        print("  7) 🎯 Direct Scalp Single Token Mint")
        print("  8) 🛡️ Check Token Safety & Jupiter Route")
        print("  9) ❌ Exit")

        try:
            choice = input("\nEnter choice [0-9]: ").strip()
            if choice == "0":
                import subprocess
                subprocess.run([sys.executable, "app.py"])
            elif choice == "1":
                hybrid_dual_scanner_and_scalp(args.sol, dry_run=True)
            elif choice == "2":
                confirm = input("⚠️ Are you sure you want to run HYBRID with REAL funds? (yes/no): ").strip().lower()
                if confirm == "yes":
                    hybrid_dual_scanner_and_scalp(args.sol, dry_run=False)
                else:
                    print("Canceled.")
            elif choice == "3":
                continuous_scanner_and_scalp(args.sol, dry_run=True)
            elif choice == "4":
                confirm = input("⚠️ Are you sure you want to run DexScreener with REAL funds? (yes/no): ").strip().lower()
                if confirm == "yes":
                    continuous_scanner_and_scalp(args.sol, dry_run=False)
                else:
                    print("Canceled.")
            elif choice == "5":
                pump_fun_sniper_and_scalp(args.sol, dry_run=True)
            elif choice == "6":
                confirm = input("⚠️ Are you sure you want to snipe Pump.fun with REAL funds? (yes/no): ").strip().lower()
                if confirm == "yes":
                    pump_fun_sniper_and_scalp(args.sol, dry_run=False)
                else:
                    print("Canceled.")
            elif choice == "7":
                mint = input("Enter target token mint address: ").strip()
                dry = input("Run in paper trading mode? (Y/n): ").strip().lower() != "n"
                direct_scalp(mint, args.sol, dry_run=dry)
            elif choice == "8":
                mint = input("Enter token mint address to analyze: ").strip()
                print("\n" + "=" * 55)
                print(f"🛡️ ANALYZING TOKEN: {mint}")
                print("=" * 55)
                is_safe, reason = check_token_safety(mint)
                print(f"1. Anti-Rug Safety: {reason}")
                h_ok, h_reason, h_stats = check_token_holders_distribution(mint)
                print(f"2. Holder Distribution: {h_reason}")
                print(f"   • Curve / Pool Share: {h_stats.get('curve_pct', 0):.1f}%")
                print(f"   • Largest Individual Holder: {h_stats.get('highest_holder_pct', 0):.1f}%")
                print(f"   • Top 10 Non-Curve Holders: {h_stats.get('top10_non_curve_pct', 0):.1f}%")
                q = get_quote(WSOL_MINT, mint, 10_000_000)
                print(f"3. Jupiter Routable: {'✅ YES' if q else '❌ NO'}")
                try:
                    from agent_council import agent_council
                    eval_res = agent_council.evaluate_candidate({"mint": mint, "symbol": "TARGET", "holders": h_stats})
                    if eval_res.get("configured"):
                        print(f"4. 🤖 AI Agent Council Consensus:")
                        print(f"   • Alpha Score: {eval_res.get('alpha_score')}/100 [{eval_res.get('suggested_action')}]")
                        print(f"   • Narrative Virality: {eval_res.get('narrative_score')}/100 -> {eval_res.get('narrative_reasoning')}")
                        print(f"   • Cabal Safety: {eval_res.get('safety_score')}/100 -> {eval_res.get('safety_reasoning')}")
                        print(f"   • Dynamic Targets: TP +{eval_res.get('target_tp_pct')}% | SL -{eval_res.get('target_sl_pct')}% (Size: {eval_res.get('size_multiplier')}x)")
                        print(f"   • Summary: {eval_res.get('verdict_summary')}")
                    else:
                        print("4. 🤖 AI Agent Council: Bypassed (Add GEMINI_API_KEY to .env to enable)")
                except Exception as e:
                    print(f"4. 🤖 AI Council Evaluation: Skipped ({e})")
                print("=" * 55 + "\n")
            else:
                print("Exiting.")
        except KeyboardInterrupt:
            print("\nExited.")


if __name__ == "__main__":
    main()