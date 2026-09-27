import time
import queue
import threading
from collections import deque
import config
from safety import check_token_safety, check_token_holders_distribution
from social_checker import check_token_socials
from scanner import TokenScanner
from pump_scanner import PumpFunScanner
from trader import (
    WSOL_MINT,
    get_quote,
    buy_token,
    sell_token,
    get_sell_value_sol,
    get_wallet_sol_balance,
)
from agent_council import agent_council
from ml_engine import ml_engine



class BotManager:
    def __init__(self):
        self.keypair, self.wallet_address = config.load_wallet()
        self.bot_mode = "RUNNING"  # RUNNING | PAUSED
        self.trade_mode = "PAPER"  # PAPER | LIVE
        self.active_trade: dict | None = None
        self.panic_requested = False

        # Thread-safe ring buffers for dashboard
        self.dex_logs = deque(maxlen=250)
        self.pump_logs = deque(maxlen=250)
        self.opportunities = deque(maxlen=50)
        self.trade_history = deque(maxlen=50)

        # Thread coordination
        self.stop_event = threading.Event()
        self.trade_queue = queue.Queue()
        self.seen_mints = set()
        self.lock = threading.RLock()
        self.trade_lock = threading.Lock()  # Mutex ensuring only 1 scalp executes at a time
        self.subscribers: list[queue.Queue] = []

        # Background worker threads
        self.threads: list[threading.Thread] = []

    def is_trading(self) -> bool:
        """Returns True if a trade position is currently active or opening."""
        return self.active_trade is not None or self.trade_lock.locked()

    def reload_wallet(self):
        """Reloads wallet keypair and address from configuration."""
        self.keypair, self.wallet_address = config.load_wallet()
        return self.wallet_address

    def subscribe(self) -> queue.Queue:
        """Subscribes an SSE client queue to receive live broadcast events."""
        q = queue.Queue(maxsize=100)
        with self.lock:
            self.subscribers.append(q)
        return q

    def unsubscribe(self, q: queue.Queue):
        """Unsubscribes an SSE client queue."""
        with self.lock:
            if q in self.subscribers:
                self.subscribers.remove(q)

    def broadcast(self, event_type: str, data: dict):
        """Dispatches an event to all connected SSE clients."""
        with self.lock:
            subscribers_snapshot = list(self.subscribers)

        msg = {"event": event_type, "data": data}
        for q in subscribers_snapshot:
            try:
                q.put_nowait(msg)
            except queue.Full:
                pass

    def log_dex(self, text: str, level: str = "info", ticker: str | None = None):
        """Logs a message to DexScreener stream and broadcasts to UI."""
        ts = time.strftime("%H:%M:%S")
        entry = {"timestamp": ts, "text": text, "level": level}
        if ticker:
            entry["ticker"] = ticker
        self.dex_logs.append(entry)
        self.broadcast("dex_log", entry)
        print(f"[{ts}] 📡 {text}")

    def log_pump(self, text: str, level: str = "info", ticker: str | None = None):
        """Logs a message to Pump.fun stream and broadcasts to UI."""
        ts = time.strftime("%H:%M:%S")
        entry = {"timestamp": ts, "text": text, "level": level}
        if ticker:
            entry["ticker"] = ticker
        self.pump_logs.append(entry)
        self.broadcast("pump_log", entry)
        print(f"[{ts}] 💊 {text}")

    def get_balance(self) -> float:
        if self.wallet_address:
            try:
                return get_wallet_sol_balance(self.wallet_address)
            except Exception:
                pass
        return 0.0

    def start_workers(self):
        """Starts background worker threads for discovery and trade dispatching."""
        if any(t.is_alive() for t in self.threads):
            return
        self.stop_event.clear()

        t_dex = threading.Thread(target=self._dexscreener_worker, daemon=True)
        t_pump = threading.Thread(target=self._pumpfun_worker, daemon=True)
        t_dispatch = threading.Thread(target=self._trade_dispatcher, daemon=True)

        self.threads = [t_dex, t_pump, t_dispatch]
        for t in self.threads:
            t.start()

        self.log_dex("DexScreener background engine initialized.", "success")
        self.log_pump("Pump.fun WebSocket background sniper initialized.", "success")

    def ensure_workers_started(self):
        """Ensures worker threads are running, even under WSGI servers."""
        if not any(t.is_alive() for t in self.threads):
            self.start_workers()

    def _dexscreener_worker(self):
        scanner = TokenScanner(
            min_liquidity=config.MIN_LIQUIDITY_USD,
            min_5m_volume=config.MIN_5M_VOLUME_USD,
            min_buy_sell_ratio=config.MIN_BUY_SELL_RATIO,
            log_callback=self.log_dex,
        )
        while not self.stop_event.is_set():
            if self.bot_mode == "PAUSED":
                time.sleep(2)
                continue

            try:
                candidate = scanner.scan_next_candidate()
                if candidate:
                    is_new = False
                    with self.lock:
                        if candidate["mint"] not in self.seen_mints:
                            self.seen_mints.add(candidate["mint"])
                            candidate["discovered_at"] = time.time()
                            candidate["source"] = "DexScreener"
                            is_new = True
                    if is_new:
                        # 1. Run Quantitative ML Engine (Pandas, XGBoost, Vector Clone Detector)
                        ml_res = ml_engine.evaluate(candidate)
                        candidate["ml_eval"] = ml_res
                        self.broadcast("ml_verdict", ml_res)

                        # Fast Pruning Gate: Reject rugs, clone templates, or low alpha in < 2ms without LLM overhead
                        if config.ML_FILTER_ENABLED and not ml_res.get("approved", True):
                            self.opportunities.appendleft(candidate)
                            self.broadcast("opportunity", candidate)
                            self.log_dex(
                                f"⚡ ML Fast-Pruned: {candidate['symbol']} (P(Rug): {ml_res['rug_pct']}% | Alpha: {ml_res['alpha_score']} | Clone: {ml_res['clone_risk']}%) -> {ml_res['reject_reason']}",
                                "warning",
                                ticker=candidate["symbol"],
                            )
                            continue

                        # 2. Run AI Agent Council evaluation
                        eval_res = agent_council.evaluate_candidate(candidate)
                        candidate["agent_eval"] = eval_res
                        self.broadcast("agent_verdict", eval_res)

                        self.opportunities.appendleft(candidate)
                        self.broadcast("opportunity", candidate)


                        if not eval_res.get("configured", True):
                            self.trade_queue.put(candidate)
                            self.log_dex(
                                f"🛡️ Local Safety Approved: {candidate['symbol']} (AI Evaluation Bypassed)",
                                "success",
                                ticker=candidate["symbol"],
                            )
                        elif eval_res.get("approved", True):
                            self.trade_queue.put(candidate)
                            alpha = eval_res.get("alpha_score", 0.0)
                            summary = eval_res.get("verdict_summary", "")
                            self.log_dex(
                                f"🤖 AI Approved: {candidate['symbol']} (Alpha: {alpha}/100) -> {summary}",
                                "success",
                                ticker=candidate["symbol"],
                            )
                        else:
                            alpha = eval_res.get("alpha_score", 0.0)
                            summary = eval_res.get("verdict_summary", "")
                            self.log_dex(
                                f"🤖 AI Filtered: {candidate['symbol']} (Alpha: {alpha}/100 < {config.MIN_AGENT_ALPHA_SCORE}) -> {summary}",
                                "warning",
                                ticker=candidate["symbol"],
                            )
            except Exception as e:
                self.log_dex(f"Scanner cycle error: {e}", "warning")

            time.sleep(config.SCAN_INTERVAL_SECONDS)

    def _pumpfun_worker(self):
        pump_scanner = PumpFunScanner(
            min_dev_buy_sol=config.PUMP_MIN_DEV_BUY_SOL,
            max_dev_buy_sol=config.PUMP_MAX_DEV_BUY_SOL,
            min_market_cap_sol=config.PUMP_MIN_MARKET_CAP_SOL,
            log_callback=self.log_pump,
        )
        try:
            for candidate in pump_scanner.stream_candidates():
                if self.stop_event.is_set():
                    break
                if self.bot_mode == "PAUSED":
                    continue

                is_new = False
                with self.lock:
                    if candidate["mint"] not in self.seen_mints:
                        self.seen_mints.add(candidate["mint"])
                        candidate["discovered_at"] = time.time()
                        candidate["source"] = "Pump.fun"
                        is_new = True

                if is_new:
                    # 1. Run Quantitative ML Engine (Pandas, XGBoost, Vector Clone Detector)
                    ml_res = ml_engine.evaluate(candidate)
                    candidate["ml_eval"] = ml_res
                    self.broadcast("ml_verdict", ml_res)

                    # Fast Pruning Gate: Reject rugs, clone templates, or low alpha in < 2ms without LLM overhead
                    if config.ML_FILTER_ENABLED and not ml_res.get("approved", True):
                        self.opportunities.appendleft(candidate)
                        self.broadcast("opportunity", candidate)
                        self.log_pump(
                            f"⚡ ML Fast-Pruned: {candidate['symbol']} (P(Rug): {ml_res['rug_pct']}% | Alpha: {ml_res['alpha_score']} | Clone: {ml_res['clone_risk']}%) -> {ml_res['reject_reason']}",
                            "warning",
                            ticker=candidate["symbol"],
                        )
                        continue

                    # 2. Run AI Agent Council evaluation
                    eval_res = agent_council.evaluate_candidate(candidate)
                    candidate["agent_eval"] = eval_res
                    self.broadcast("agent_verdict", eval_res)

                    self.opportunities.appendleft(candidate)
                    self.broadcast("opportunity", candidate)


                    if not eval_res.get("configured", True):
                        self.trade_queue.put(candidate)
                        self.log_pump(
                            f"🛡️ Local Safety Approved: {candidate['symbol']} (AI Evaluation Bypassed)",
                            "success",
                            ticker=candidate["symbol"],
                        )
                    elif eval_res.get("approved", True):
                        self.trade_queue.put(candidate)
                        alpha = eval_res.get("alpha_score", 0.0)
                        summary = eval_res.get("verdict_summary", "")
                        self.log_pump(
                            f"🤖 AI Approved: {candidate['symbol']} (Alpha: {alpha}/100) -> {summary}",
                            "success",
                            ticker=candidate["symbol"],
                        )
                    else:
                        alpha = eval_res.get("alpha_score", 0.0)
                        summary = eval_res.get("verdict_summary", "")
                        self.log_pump(
                            f"🤖 AI Filtered: {candidate['symbol']} (Alpha: {alpha}/100 < {config.MIN_AGENT_ALPHA_SCORE}) -> {summary}",
                            "warning",
                            ticker=candidate["symbol"],
                        )
        except Exception as e:
            self.log_pump(f"Stream worker error: {e}", "warning")

    def _trade_dispatcher(self):
        """Processes opportunities from the queue one at a time."""
        while not self.stop_event.is_set():
            try:
                token = self.trade_queue.get(timeout=1.0)
            except queue.Empty:
                continue

            if self.bot_mode == "PAUSED":
                continue

            age = time.time() - token.get("discovered_at", time.time())
            if age > 45.0:
                msg = f"Candidate {token['symbol']} expired ({age:.0f}s old). Skipping."
                if token.get("source") == "DexScreener":
                    self.log_dex(msg, "warning")
                else:
                    self.log_pump(msg, "warning")
                continue

            is_dry = self.trade_mode == "PAPER"
            self.execute_scalp(token["mint"], config.TRADE_AMOUNT_SOL, dry_run=is_dry, token_info=token)

    def execute_scalp(self, token_mint: str, sol_amount: float, dry_run: bool = True, token_info: dict | None = None) -> bool:
        """
        Thread-safe entry point for executing a scalp position.
        Acquires trade_lock non-blockingly to guarantee zero collisions between
        automated queue dispatch and manual UI requests.
        """
        if not self.trade_lock.acquire(blocking=False):
            sym = token_info.get("symbol", "TOKEN") if token_info else "TOKEN"
            self.log_dex(f"Cannot scalp {sym}: Another trade is currently executing.", "warning")
            return False

        try:
            return self._run_scalp_core(token_mint, sol_amount, dry_run, token_info)
        finally:
            self.active_trade = None
            self.broadcast("active_trade", None)
            if self.trade_lock.locked():
                self.trade_lock.release()

    def _run_scalp_core(self, token_mint: str, sol_amount: float, dry_run: bool = True, token_info: dict | None = None) -> bool:
        """Executes a scalp or multi-tier moonshot position with live telemetry broadcasted to the dashboard."""
        symbol = token_info.get("symbol", "TOKEN") if token_info else "TOKEN"
        name = token_info.get("name", symbol) if token_info else symbol
        source = token_info.get("source", "Manual") if token_info else "Manual"

        # Apply AI dynamic TP/SL targets and position sizing if available
        tp_target = config.TAKE_PROFIT_PCT
        sl_target = config.STOP_LOSS_PCT
        size_mult = 1.0
        agent_eval = token_info.get("agent_eval") if token_info else None

        # Strategy detection: RUNNER for high conviction moonshots (200%-1000%+), SCALP for quick flips
        trade_strategy = "SCALP"
        if agent_eval and agent_eval.get("configured"):
            tp_target = float(agent_eval.get("target_tp_pct", tp_target))
            sl_target = float(agent_eval.get("target_sl_pct", sl_target))
            size_mult = float(agent_eval.get("size_multiplier", 1.0))
            trade_strategy = str(agent_eval.get("trade_strategy", "SCALP")).upper()
        elif token_info and token_info.get("pre_graduation"):
            trade_strategy = "RUNNER"

        sol_amount = round(sol_amount * size_mult, 4)
        self.panic_requested = False
        tokens_acquired = 0

        # 1. Entry Buy
        if dry_run:
            lamports = int(sol_amount * 1_000_000_000)
            quote = get_quote(WSOL_MINT, token_mint, lamports, config.SLIPPAGE_BPS)
            if not quote:
                self.log_dex(f"Paper trade failed for {symbol}: No Jupiter route", "error")
                return False
            tokens_acquired = int(quote.get("outAmount", 0))
        else:
            if not self.keypair:
                self.log_dex("Live trade failed: Wallet not configured", "error")
                return False
            tx_id, tokens_acquired = buy_token(token_mint, sol_amount, self.keypair, config.SLIPPAGE_BPS)
            if not tx_id or tokens_acquired <= 0:
                self.log_dex(f"Live BUY order failed for {symbol}", "error")
                return False

        entry_sol = sol_amount
        start_time = time.time()
        peak_pnl = 0.0
        trailing_active = False
        breakeven_active = False
        exit_reason = "Manual / Unspecified"
        current_sol = entry_sol

        # Multi-Tier Moonbag state
        initial_tokens = tokens_acquired
        remaining_tokens = tokens_acquired
        realized_sol_banked = 0.0
        tier1_executed = False
        tier2_executed = False
        tier_history = []
        is_runner = (trade_strategy == "RUNNER") and config.MOONBAG_ENABLED
        stagnation_limit = config.RUNNER_HOLD_SECONDS if is_runner else config.MAX_HOLD_SECONDS

        self.active_trade = {
            "symbol": symbol,
            "token_name": name,
            "ca": token_mint,
            "entry_sol": entry_sol,
            "tokens_acquired": tokens_acquired,
            "remaining_tokens": remaining_tokens,
            "realized_sol_banked": 0.0,
            "current_sol": current_sol,
            "total_value_sol": current_sol,
            "pnl_pct": 0.0,
            "peak_pnl": 0.0,
            "elapsed_sec": 0,
            "breakeven_active": False,
            "trailing_active": False,
            "trade_strategy": trade_strategy,
            "tier1_executed": False,
            "tier2_executed": False,
            "stagnation_limit": stagnation_limit,
            "target_tp_pct": tp_target,
            "target_sl_pct": sl_target,
            "agent_eval": agent_eval,
            "mode": "PAPER" if dry_run else "LIVE",
            "source": source,
            "url": token_info.get("url", f"https://solscan.io/token/{token_mint}") if token_info else f"https://solscan.io/token/{token_mint}",
        }
        self.broadcast("active_trade", self.active_trade)

        strat_badge = "🚀 MOONSHOT RUNNER (Multi-Tier Moonbag)" if is_runner else "⚡ QUICK SCALP"
        open_msg = f"{'[PAPER] ' if dry_run else '⚡ '}Position Opened: {symbol} | {sol_amount} SOL ({tokens_acquired:,} tokens) [{strat_badge}]"
        if source == "DexScreener":
            self.log_dex(open_msg, "success", ticker=symbol)
        else:
            self.log_pump(open_msg, "success", ticker=symbol)

        # 2. Position Monitoring Loop
        try:
            while not self.panic_requested and not self.stop_event.is_set():
                time.sleep(2.0)
                elapsed = int(time.time() - start_time)

                if remaining_tokens > 0:
                    quote_sol = get_sell_value_sol(token_mint, remaining_tokens, config.SLIPPAGE_BPS)
                    if quote_sol > 0:
                        current_sol = quote_sol
                else:
                    current_sol = 0.0

                total_value = realized_sol_banked + current_sol
                pnl_pct = ((total_value - entry_sol) / entry_sol) * 100
                if pnl_pct > peak_pnl:
                    peak_pnl = pnl_pct

                # Multi-Tier Take-Profit Execution for Moonshot Runners
                if is_runner and remaining_tokens > 0:
                    # Tier 1 (+80%): Sell 50% of initial tokens -> Returns initial capital (Risk-Free!)
                    if pnl_pct >= config.TIER1_TP_PCT and not tier1_executed:
                        sell_qty = int(initial_tokens * (config.TIER1_SELL_PCT / 100.0))
                        sell_qty = min(sell_qty, remaining_tokens)
                        sold_sol = 0.0
                        if dry_run:
                            sold_sol = get_sell_value_sol(token_mint, sell_qty, config.SLIPPAGE_BPS)
                        elif self.keypair:
                            tx_id, out_lamports = sell_token(token_mint, sell_qty, self.keypair, config.SLIPPAGE_BPS)
                            if tx_id and out_lamports > 0:
                                sold_sol = out_lamports / 1_000_000_000

                        if sold_sol > 0:
                            realized_sol_banked += sold_sol
                            remaining_tokens -= sell_qty
                            tier1_executed = True
                            breakeven_active = True
                            tier_evt = {
                                "tier": 1,
                                "pnl_pct": round(pnl_pct, 1),
                                "sold_tokens": sell_qty,
                                "sol_banked": round(sold_sol, 4),
                                "remaining_tokens": remaining_tokens,
                            }
                            tier_history.append(tier_evt)
                            self.broadcast("tier_exit", {"symbol": symbol, **tier_evt})
                            t1_msg = f"🎯 [TIER 1 TAKE PROFIT] {symbol} (+{pnl_pct:.1f}%): Sold 50% for +{sold_sol:.4f} SOL. Initial investment secured! Moonbag running risk-free."
                            if source == "DexScreener":
                                self.log_dex(t1_msg, "success", ticker=symbol)
                            else:
                                self.log_pump(t1_msg, "success", ticker=symbol)

                    # Tier 2 (+250%): Sell 25% of initial tokens -> Locks in large profit!
                    if pnl_pct >= config.TIER2_TP_PCT and not tier2_executed and remaining_tokens > 0:
                        sell_qty = int(initial_tokens * (config.TIER2_SELL_PCT / 100.0))
                        sell_qty = min(sell_qty, remaining_tokens)
                        sold_sol = 0.0
                        if dry_run:
                            sold_sol = get_sell_value_sol(token_mint, sell_qty, config.SLIPPAGE_BPS)
                        elif self.keypair:
                            tx_id, out_lamports = sell_token(token_mint, sell_qty, self.keypair, config.SLIPPAGE_BPS)
                            if tx_id and out_lamports > 0:
                                sold_sol = out_lamports / 1_000_000_000

                        if sold_sol > 0:
                            realized_sol_banked += sold_sol
                            remaining_tokens -= sell_qty
                            tier2_executed = True
                            tier_evt = {
                                "tier": 2,
                                "pnl_pct": round(pnl_pct, 1),
                                "sold_tokens": sell_qty,
                                "sol_banked": round(sold_sol, 4),
                                "remaining_tokens": remaining_tokens,
                            }
                            tier_history.append(tier_evt)
                            self.broadcast("tier_exit", {"symbol": symbol, **tier_evt})
                            t2_msg = f"🚀 [TIER 2 TAKE PROFIT] {symbol} (+{pnl_pct:.1f}%): Sold 25% for +{sold_sol:.4f} SOL. Final 25% Moonbag running to 1000%+!"
                            if source == "DexScreener":
                                self.log_dex(t2_msg, "success", ticker=symbol)
                            else:
                                self.log_pump(t2_msg, "success", ticker=symbol)

                    # Moonbag Dynamic Trailing Stop (Wide trail for remaining 25%)
                    if tier1_executed:
                        trail_drop = config.MOONBAG_TRAILING_DROP_PCT
                        if (peak_pnl - pnl_pct) >= trail_drop:
                            exit_reason = f"Moonbag Trailing Stop Triggered (Dropped {trail_drop:.1f}% from peak +{peak_pnl:.1f}%)"
                            break

                # Standard Quick Scalp Exit Check
                if not is_runner:
                    # Check Standard Take Profit
                    if pnl_pct >= tp_target:
                        exit_reason = f"Take Profit (+{tp_target:.1f}%)"
                        break

                    # Check Standard Trailing Stop
                    if config.TRAILING_STOP_ENABLED:
                        if not trailing_active and peak_pnl >= config.TRAILING_TRIGGER_PCT:
                            trailing_active = True
                        if trailing_active and (peak_pnl - pnl_pct) >= config.TRAILING_DROP_PCT:
                            exit_reason = f"Trailing Stop Triggered (Dropped {config.TRAILING_DROP_PCT}% from peak {peak_pnl:.1f}%)"
                            break

                # Breakeven Protection (Only applicable before Tier 1 de-risk)
                if not tier1_executed and config.BREAKEVEN_PROTECTION_ENABLED:
                    if not breakeven_active and peak_pnl >= config.BREAKEVEN_TRIGGER_PCT:
                        breakeven_active = True
                    if breakeven_active and pnl_pct <= 0.5:
                        exit_reason = f"Breakeven Floor Hit (+0.5% locked after +{peak_pnl:.1f}% peak)"
                        break

                # Stop Loss (Only applicable before Tier 1 de-risk)
                if not tier1_executed and pnl_pct <= -sl_target:
                    exit_reason = f"Stop Loss (-{sl_target:.1f}%)"
                    break

                # Stagnation Exit
                if elapsed >= stagnation_limit:
                    exit_reason = f"Stagnation Exit ({stagnation_limit}s elapsed)"
                    break

                # Update live telemetry state
                self.active_trade.update({
                    "remaining_tokens": remaining_tokens,
                    "realized_sol_banked": round(realized_sol_banked, 4),
                    "current_sol": current_sol,
                    "total_value_sol": round(total_value, 4),
                    "pnl_pct": round(pnl_pct, 2),
                    "peak_pnl": round(peak_pnl, 2),
                    "elapsed_sec": elapsed,
                    "breakeven_active": breakeven_active,
                    "trailing_active": trailing_active,
                    "tier1_executed": tier1_executed,
                    "tier2_executed": tier2_executed,
                })
                self.broadcast("active_trade", self.active_trade)

        except Exception as e:
            exit_reason = f"Error during monitoring: {e}"

        if self.panic_requested:
            exit_reason = "Panic Emergency Market Sell"

        # 3. Final Exit Sell (Remaining Tokens)
        final_sell_sol = 0.0
        if remaining_tokens > 0:
            if dry_run:
                q = get_sell_value_sol(token_mint, remaining_tokens, config.SLIPPAGE_BPS)
                final_sell_sol = q if q > 0 else 0.0
            elif self.keypair:
                sell_tx, out_lamports = sell_token(token_mint, remaining_tokens, self.keypair, config.SLIPPAGE_BPS)
                if sell_tx and out_lamports > 0:
                    final_sell_sol = out_lamports / 1_000_000_000

        total_exit_sol = realized_sol_banked + final_sell_sol
        pnl_sol = total_exit_sol - entry_sol
        realized_pct = ((total_exit_sol - entry_sol) / entry_sol) * 100

        executed_trade = {
            "symbol": symbol,
            "token_name": name,
            "ca": token_mint,
            "entry_sol": entry_sol,
            "exit_sol": round(total_exit_sol, 4),
            "pnl_sol": round(pnl_sol, 4),
            "pnl_pct": round(realized_pct, 2),
            "trade_strategy": trade_strategy,
            "tier_history": tier_history,
            "duration_sec": int(time.time() - start_time),
            "exit_type": exit_reason,
            "timestamp": time.strftime("%H:%M:%S"),
            "agent_eval": agent_eval,
            "mode": "PAPER" if dry_run else "LIVE",
        }

        self.trade_history.appendleft(executed_trade)
        self.active_trade = None
        self.broadcast("trade_completed", executed_trade)
        self.broadcast("active_trade", None)

        # Record trade outcome to ML dataset for continuous training & backtesting
        ml_engine.record_trade_outcome(
            token_mint,
            realized_pct,
            int(time.time() - start_time),
            exit_reason
        )


        msg = f"Trade Closed: {symbol} [{trade_strategy}] -> Total Realized PnL: {realized_pct:+.2f}% ({pnl_sol:+.4f} SOL) [{exit_reason}]"
        lvl = "success" if pnl_sol >= 0 else "error"
        if source == "DexScreener":
            self.log_dex(msg, lvl, ticker=symbol)
        else:
            self.log_pump(msg, lvl, ticker=symbol)

        return True

    def panic_sell(self) -> bool:
        """Triggers emergency exit of the active trade."""
        if self.active_trade:
            self.panic_requested = True
            return True
        return False


# Global singleton instance
bot_manager = BotManager()
