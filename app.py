import json
import time
import os
from flask import Flask, render_template, Response, request, jsonify
import config
from bot_manager import bot_manager
from agent_council import agent_council
from ml_engine import ml_engine


app = Flask(__name__, template_folder="templates")


@app.route("/")
def index():
    return render_template("index.html")


import urllib.parse
import requests

_last_rpc_check = 0.0
_cached_rpc_info = {
    "rpc_host": "Helius Dedicated",
    "rpc_latency_ms": 35,
    "rpc_status": "ok"
}

_last_sol_price_check = 0.0
_cached_sol_price = 150.0


def get_sol_usd_price() -> float:
    global _last_sol_price_check, _cached_sol_price
    now = time.time()
    if now - _last_sol_price_check < 60.0:
        return _cached_sol_price

    try:
        r = requests.get(
            "https://api.jup.ag/price/v2?ids=So11111111111111111111111111111111111111112",
            timeout=3.0,
            headers={"User-Agent": "Mozilla/5.0"}
        )
        if r.status_code == 200:
            price_val = float(r.json().get("data", {}).get("So11111111111111111111111111111111111111112", {}).get("price", 0))
            if price_val > 0:
                _cached_sol_price = round(price_val, 2)
    except Exception:
        pass
    _last_sol_price_check = now
    return _cached_sol_price


def get_rpc_telemetry() -> dict:
    global _last_rpc_check, _cached_rpc_info
    now = time.time()
    if now - _last_rpc_check < 15.0:
        return _cached_rpc_info

    rpc_url = config.RPC_URL
    parsed = urllib.parse.urlparse(rpc_url)
    host_raw = parsed.netloc or "api.mainnet-beta.solana.com"
    if "helius" in host_raw.lower():
        host_name = "Helius Dedicated"
    elif "quicknode" in host_raw.lower():
        host_name = "QuickNode Dedicated"
    elif "solana.com" in host_raw.lower():
        host_name = "Solana Public RPC"
    else:
        host_name = host_raw.split(":")[0]

    start = time.perf_counter()
    status = "ok"
    try:
        resp = requests.post(
            rpc_url,
            json={"jsonrpc": "2.0", "id": 1, "method": "getHealth"},
            timeout=3.0,
            headers={"Content-Type": "application/json"}
        )
        latency = max(1, round((time.perf_counter() - start) * 1000))
        if resp.status_code != 200:
            status = "degraded"
    except Exception:
        latency = -1
        status = "offline"

    _cached_rpc_info = {
        "rpc_host": host_name,
        "rpc_latency_ms": latency if latency > 0 else 999,
        "rpc_status": status,
    }
    _last_rpc_check = now
    return _cached_rpc_info


def get_runtime_settings():
    keys = [k.strip() for k in config.GEMINI_API_KEY.replace(";", ",").split(",") if k.strip() and k.strip() != "your_gemini_api_key_here"]
    if len(keys) > 1:
        masked_key = f"{len(keys)} keys active (auto-rotating)"
    elif len(keys) == 1:
        k = keys[0]
        masked_key = f"{k[:4]}...{k[-4:]}" if len(k) > 8 else "***"
    else:
        masked_key = ""

    return {
        "trade_amount_sol": config.TRADE_AMOUNT_SOL,
        "slippage_bps": config.SLIPPAGE_BPS,
        "take_profit_pct": config.TAKE_PROFIT_PCT,
        "stop_loss_pct": config.STOP_LOSS_PCT,
        "trailing_stop_enabled": config.TRAILING_STOP_ENABLED,
        "trailing_trigger_pct": config.TRAILING_TRIGGER_PCT,
        "trailing_drop_pct": config.TRAILING_DROP_PCT,
        "breakeven_enabled": config.BREAKEVEN_PROTECTION_ENABLED,
        "breakeven_trigger_pct": config.BREAKEVEN_TRIGGER_PCT,
        "max_hold_seconds": config.MAX_HOLD_SECONDS,
        "min_liquidity_usd": config.MIN_LIQUIDITY_USD,
        "min_5m_volume_usd": config.MIN_5M_VOLUME_USD,
        "require_socials": config.REQUIRE_SOCIALS,
        "require_twitter": config.REQUIRE_TWITTER,
        "require_telegram": config.REQUIRE_TELEGRAM,
        "max_dev_holding_pct": config.MAX_DEV_HOLDING_PCT,
        "max_top10_non_curve_pct": config.MAX_TOP10_NON_CURVE_PCT,
        "pump_min_dev_buy_sol": config.PUMP_MIN_DEV_BUY_SOL,
        "pump_max_dev_buy_sol": config.PUMP_MAX_DEV_BUY_SOL,
        "pump_min_market_cap_sol": config.PUMP_MIN_MARKET_CAP_SOL,
        # AI Agent Council Settings
        "gemini_api_key_configured": bool(keys),
        "gemini_api_key_masked": masked_key,
        "gemini_model": config.GEMINI_MODEL,
        "agent_eval_enabled": config.AGENT_EVAL_ENABLED,
        "min_agent_alpha_score": config.MIN_AGENT_ALPHA_SCORE,
        "agent_dynamic_tp_sl": config.AGENT_DYNAMIC_TP_SL,
        "agent_fail_open": config.AGENT_FAIL_OPEN,
        "agent_max_rpm": config.AGENT_MAX_RPM,
        "agent_cooldown_seconds": config.AGENT_COOLDOWN_SECONDS,
        "runner_min_alpha_score": config.RUNNER_MIN_ALPHA_SCORE,
        # Multi-Tier Moonbag & Moonshot Engine (200%-1000%+)
        "moonbag_enabled": config.MOONBAG_ENABLED,
        "tier1_tp_pct": config.TIER1_TP_PCT,
        "tier1_sell_pct": config.TIER1_SELL_PCT,
        "tier2_tp_pct": config.TIER2_TP_PCT,
        "tier2_sell_pct": config.TIER2_SELL_PCT,
        "moonbag_trailing_drop_pct": config.MOONBAG_TRAILING_DROP_PCT,
        "runner_hold_seconds": config.RUNNER_HOLD_SECONDS,
        # Pre-Graduation Raydium Migration Tracker
        "pump_pre_graduation_tracking": config.PUMP_PRE_GRADUATION_TRACKING,
        "pump_graduation_min_sol": config.PUMP_GRADUATION_MIN_SOL,
        "pump_graduation_max_sol": config.PUMP_GRADUATION_MAX_SOL,
        # Quantitative ML Alpha Engine (XGBoost + Embeddings)
        "ml_filter_enabled": config.ML_FILTER_ENABLED,
        "max_rug_probability": config.MAX_RUG_PROBABILITY,
        "min_ml_alpha_score": config.MIN_ML_ALPHA_SCORE,
        "max_clone_risk": config.MAX_CLONE_RISK,
        "ml_auto_retrain": config.ML_AUTO_RETRAIN,
        "ml_stats": ml_engine.get_stats(),
        # Wallet & RPC Telemetry

        "solana_rpc_url": config.RPC_URL,
        "wallet_configured": bool(bot_manager.wallet_address),
        "wallet_address": bot_manager.wallet_address or "Not Configured",
        "wallet_short": f"{bot_manager.wallet_address[:4]}...{bot_manager.wallet_address[-4:]}" if bot_manager.wallet_address else "Not Configured",
    }


@app.route("/api/status", methods=["GET"])
def get_status():
    if not bot_manager.wallet_address:
        bot_manager.reload_wallet()
    bot_manager.ensure_workers_started()
    balance = bot_manager.get_balance()
    rpc_info = get_rpc_telemetry()
    return jsonify({
        "wallet_configured": bool(bot_manager.wallet_address),
        "wallet_address": bot_manager.wallet_address or "Not Configured",
        "wallet_short": f"{bot_manager.wallet_address[:4]}...{bot_manager.wallet_address[-4:]}" if bot_manager.wallet_address else "Not Configured",
        "sol_balance": balance,
        "sol_usd_price": get_sol_usd_price(),
        "bot_mode": bot_manager.bot_mode,
        "trade_mode": bot_manager.trade_mode,
        "active_trade": bot_manager.active_trade,
        "rpc_host": rpc_info["rpc_host"],
        "rpc_latency_ms": rpc_info["rpc_latency_ms"],
        "rpc_status": rpc_info["rpc_status"],
        "settings": get_runtime_settings(),
        "ml_stats": ml_engine.get_stats(),
    })


@app.route("/api/stream")
def sse_stream():
    """Server-Sent Events endpoint streaming real-time logs and telemetry."""
    def event_generator():
        q = bot_manager.subscribe()
        try:
            rpc_info = get_rpc_telemetry()
            # 1. Send initial snapshot of state and recent logs
            initial_payload = {
                "wallet_address": bot_manager.wallet_address or "Not Configured",
                "wallet_short": f"{bot_manager.wallet_address[:4]}...{bot_manager.wallet_address[-4:]}" if bot_manager.wallet_address else "None",
                "sol_balance": bot_manager.get_balance(),
                "sol_usd_price": get_sol_usd_price(),
                "bot_mode": bot_manager.bot_mode,
                "trade_mode": bot_manager.trade_mode,
                "active_trade": bot_manager.active_trade,
                "rpc_host": rpc_info["rpc_host"],
                "rpc_latency_ms": rpc_info["rpc_latency_ms"],
                "rpc_status": rpc_info["rpc_status"],
                "settings": get_runtime_settings(),
                "ml_stats": ml_engine.get_stats(),
                "dex_logs": list(bot_manager.dex_logs),
                "pump_logs": list(bot_manager.pump_logs),
                "opportunities": list(bot_manager.opportunities),
                "trade_history": list(bot_manager.trade_history),
                "agent_verdicts": agent_council.get_recent_verdicts(),
            }

            yield f"event: init\ndata: {json.dumps(initial_payload)}\n\n"

            # 2. Stream real-time events
            while True:
                try:
                    msg = q.get(timeout=20.0)
                    evt_type = msg.get("event", "message")
                    data = json.dumps(msg.get("data", {}))
                    yield f"event: {evt_type}\ndata: {data}\n\n"
                except Exception:
                    # Keep-alive heartbeat ping
                    yield ": ping\n\n"
        finally:
            bot_manager.unsubscribe(q)

    return Response(
        event_generator(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@app.route("/api/mode", methods=["POST"])
def update_mode():
    data = request.json or {}
    if "bot_mode" in data:
        bot_manager.bot_mode = data["bot_mode"]  # RUNNING | PAUSED
    if "trade_mode" in data:
        bot_manager.trade_mode = data["trade_mode"]  # PAPER | LIVE
    if data.get("bot_mode") == "PAPER":
        bot_manager.bot_mode = "RUNNING"
        bot_manager.trade_mode = "PAPER"

    bot_manager.broadcast("status", {
        "bot_mode": bot_manager.bot_mode,
        "trade_mode": bot_manager.trade_mode,
    })
    return jsonify({"success": True, "bot_mode": bot_manager.bot_mode, "trade_mode": bot_manager.trade_mode})


@app.route("/api/panic_sell", methods=["POST"])
def panic_sell():
    success = bot_manager.panic_sell()
    if success:
        return jsonify({"success": True, "message": "Panic sell order dispatched"})
    return jsonify({"success": False, "message": "No active position to sell"}), 400


@app.route("/api/scalp", methods=["POST"])
def manual_scalp():
    if bot_manager.is_trading():
        sym = bot_manager.active_trade.get("symbol", "TOKEN") if bot_manager.active_trade else "Active Position"
        return jsonify({"success": False, "message": f"Active trade already in progress ({sym})! Close or wait for exit first."}), 400

    data = request.json or {}
    mint = data.get("mint")
    amount = float(data.get("amount", config.TRADE_AMOUNT_SOL))
    if not mint:
        return jsonify({"success": False, "message": "Mint address required"}), 400

    import threading
    t = threading.Thread(
        target=bot_manager.execute_scalp,
        args=(mint, amount, bot_manager.trade_mode == "PAPER", {"symbol": data.get("symbol", "TOKEN"), "name": data.get("name", "Target")}),
        daemon=True,
    )
    t.start()
    return jsonify({"success": True, "message": f"Scalp initiated for {mint[:6]}..."})


@app.route("/api/trades/clear", methods=["POST"])
def clear_trade_history():
    bot_manager.trade_history.clear()
    bot_manager.broadcast("trades_cleared", {})
    return jsonify({"success": True, "message": "Trade history cleared"})


@app.route("/api/logs/clear", methods=["POST"])
def clear_logs():
    data = request.json or {}
    stream = data.get("stream", "all")
    if stream in ("dex", "all"):
        bot_manager.dex_logs.clear()
    if stream in ("pump", "all"):
        bot_manager.pump_logs.clear()
    bot_manager.broadcast("logs_cleared", {"stream": stream})
    return jsonify({"success": True, "message": f"Logs cleared for {stream}"})


def save_env_settings(updates: dict, env_path: str = None):
    """
    Updates or appends key-value pairs in the .env file while preserving existing comments.
    """
    if env_path is None:
        env_path = str(config.BASE_DIR / ".env")

    if not os.path.exists(env_path):
        lines = []
    else:
        with open(env_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

    applied_keys = set()
    new_lines = []

    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            k, _ = stripped.split("=", 1)
            k = k.strip()
            if k in updates:
                new_lines.append(f"{k}={updates[k]}\n")
                applied_keys.add(k)
                continue
        new_lines.append(line)

    missing_keys = [k for k in updates if k not in applied_keys]
    if missing_keys:
        if new_lines and not new_lines[-1].endswith("\n"):
            new_lines[-1] += "\n"
        new_lines.append("\n# Added via Web Terminal Settings\n")
        for k in missing_keys:
            new_lines.append(f"{k}={updates[k]}\n")

    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)


@app.route("/api/settings", methods=["POST"])
def update_settings():
    data = request.json or {}
    env_updates = {}

    # Update runtime config & collect for .env persistence
    if "trade_amount_sol" in data:
        config.TRADE_AMOUNT_SOL = float(data["trade_amount_sol"])
        env_updates["TRADE_AMOUNT_SOL"] = str(config.TRADE_AMOUNT_SOL)
    if "slippage_bps" in data:
        config.SLIPPAGE_BPS = int(data["slippage_bps"])
        env_updates["SLIPPAGE_BPS"] = str(config.SLIPPAGE_BPS)
    if "take_profit_pct" in data:
        config.TAKE_PROFIT_PCT = float(data["take_profit_pct"])
        env_updates["TAKE_PROFIT_PCT"] = str(config.TAKE_PROFIT_PCT)
    if "stop_loss_pct" in data:
        config.STOP_LOSS_PCT = float(data["stop_loss_pct"])
        env_updates["STOP_LOSS_PCT"] = str(config.STOP_LOSS_PCT)
    if "trailing_stop_enabled" in data:
        config.TRAILING_STOP_ENABLED = bool(data["trailing_stop_enabled"])
        env_updates["TRAILING_STOP_ENABLED"] = str(config.TRAILING_STOP_ENABLED)
    if "trailing_trigger_pct" in data:
        config.TRAILING_TRIGGER_PCT = float(data["trailing_trigger_pct"])
        env_updates["TRAILING_TRIGGER_PCT"] = str(config.TRAILING_TRIGGER_PCT)
    if "trailing_drop_pct" in data:
        config.TRAILING_DROP_PCT = float(data["trailing_drop_pct"])
        env_updates["TRAILING_DROP_PCT"] = str(config.TRAILING_DROP_PCT)
    if "breakeven_enabled" in data:
        config.BREAKEVEN_PROTECTION_ENABLED = bool(data["breakeven_enabled"])
        env_updates["BREAKEVEN_PROTECTION_ENABLED"] = str(config.BREAKEVEN_PROTECTION_ENABLED)
    if "breakeven_trigger_pct" in data:
        config.BREAKEVEN_TRIGGER_PCT = float(data["breakeven_trigger_pct"])
        env_updates["BREAKEVEN_TRIGGER_PCT"] = str(config.BREAKEVEN_TRIGGER_PCT)
    if "max_hold_seconds" in data:
        config.MAX_HOLD_SECONDS = int(data["max_hold_seconds"])
        env_updates["MAX_HOLD_SECONDS"] = str(config.MAX_HOLD_SECONDS)
    if "min_liquidity_usd" in data:
        config.MIN_LIQUIDITY_USD = float(data["min_liquidity_usd"])
        env_updates["MIN_LIQUIDITY_USD"] = str(config.MIN_LIQUIDITY_USD)
    if "min_5m_volume_usd" in data:
        config.MIN_5M_VOLUME_USD = float(data["min_5m_volume_usd"])
        env_updates["MIN_5M_VOLUME_USD"] = str(config.MIN_5M_VOLUME_USD)
    if "require_socials" in data:
        config.REQUIRE_SOCIALS = bool(data["require_socials"])
        env_updates["REQUIRE_SOCIALS"] = str(config.REQUIRE_SOCIALS)
    if "require_twitter" in data:
        config.REQUIRE_TWITTER = bool(data["require_twitter"])
        env_updates["REQUIRE_TWITTER"] = str(config.REQUIRE_TWITTER)
    if "require_telegram" in data:
        config.REQUIRE_TELEGRAM = bool(data["require_telegram"])
        env_updates["REQUIRE_TELEGRAM"] = str(config.REQUIRE_TELEGRAM)
    if "pump_min_dev_buy_sol" in data:
        config.PUMP_MIN_DEV_BUY_SOL = float(data["pump_min_dev_buy_sol"])
        env_updates["PUMP_MIN_DEV_BUY_SOL"] = str(config.PUMP_MIN_DEV_BUY_SOL)
    if "pump_max_dev_buy_sol" in data:
        config.PUMP_MAX_DEV_BUY_SOL = float(data["pump_max_dev_buy_sol"])
        env_updates["PUMP_MAX_DEV_BUY_SOL"] = str(config.PUMP_MAX_DEV_BUY_SOL)
    if "pump_min_market_cap_sol" in data:
        config.PUMP_MIN_MARKET_CAP_SOL = float(data["pump_min_market_cap_sol"])
        env_updates["PUMP_MIN_MARKET_CAP_SOL"] = str(config.PUMP_MIN_MARKET_CAP_SOL)
    # Solana Wallet & RPC Configuration
    if "solana_private_key" in data:
        new_pk = str(data["solana_private_key"]).strip().strip("'\"")
        if new_pk and not new_pk.startswith("***") and new_pk != "your_private_key_here":
            try:
                from solders.keypair import Keypair
                import base58
                if new_pk.startswith("["):
                    kb = bytes(json.loads(new_pk))
                else:
                    kb = base58.b58decode(new_pk)
                # Verify valid keypair bytes
                test_kp = Keypair.from_bytes(kb)
                os.environ["SOLANA_PRIVATE_KEY"] = new_pk
                env_updates["SOLANA_PRIVATE_KEY"] = new_pk
                bot_manager.reload_wallet()
            except Exception as e:
                return jsonify({"success": False, "message": f"Invalid Solana Private Key format: {e}"}), 400

    if "solana_rpc_url" in data:
        new_rpc = str(data["solana_rpc_url"]).strip()
        if new_rpc and new_rpc.startswith("http"):
            config.RPC_URL = new_rpc
            os.environ["SOLANA_RPC_URL"] = new_rpc
            env_updates["SOLANA_RPC_URL"] = new_rpc

    # AI Agent Council Settings
    if "gemini_api_key" in data:
        new_key = str(data["gemini_api_key"]).strip()
        if new_key and not new_key.startswith("***"):
            config.GEMINI_API_KEY = new_key
            os.environ["GEMINI_API_KEY"] = new_key
            env_updates["GEMINI_API_KEY"] = new_key
    if "agent_eval_enabled" in data:
        config.AGENT_EVAL_ENABLED = bool(data["agent_eval_enabled"])
        env_updates["AGENT_EVAL_ENABLED"] = str(config.AGENT_EVAL_ENABLED)
    if "min_agent_alpha_score" in data:
        config.MIN_AGENT_ALPHA_SCORE = float(data["min_agent_alpha_score"])
        env_updates["MIN_AGENT_ALPHA_SCORE"] = str(config.MIN_AGENT_ALPHA_SCORE)
    if "agent_dynamic_tp_sl" in data:
        config.AGENT_DYNAMIC_TP_SL = bool(data["agent_dynamic_tp_sl"])
        env_updates["AGENT_DYNAMIC_TP_SL"] = str(config.AGENT_DYNAMIC_TP_SL)
    if "agent_fail_open" in data:
        config.AGENT_FAIL_OPEN = bool(data["agent_fail_open"])
        env_updates["AGENT_FAIL_OPEN"] = str(config.AGENT_FAIL_OPEN)
    if "agent_max_rpm" in data:
        config.AGENT_MAX_RPM = int(data["agent_max_rpm"])
        env_updates["AGENT_MAX_RPM"] = str(config.AGENT_MAX_RPM)
    if "agent_cooldown_seconds" in data:
        config.AGENT_COOLDOWN_SECONDS = int(data["agent_cooldown_seconds"])
        env_updates["AGENT_COOLDOWN_SECONDS"] = str(config.AGENT_COOLDOWN_SECONDS)
    if "runner_min_alpha_score" in data:
        config.RUNNER_MIN_ALPHA_SCORE = float(data["runner_min_alpha_score"])
        env_updates["RUNNER_MIN_ALPHA_SCORE"] = str(config.RUNNER_MIN_ALPHA_SCORE)
    # Multi-Tier Moonbag & Moonshot Engine
    if "moonbag_enabled" in data:
        config.MOONBAG_ENABLED = bool(data["moonbag_enabled"])
        env_updates["MOONBAG_ENABLED"] = str(config.MOONBAG_ENABLED)
    if "tier1_tp_pct" in data:
        config.TIER1_TP_PCT = float(data["tier1_tp_pct"])
        env_updates["TIER1_TP_PCT"] = str(config.TIER1_TP_PCT)
    if "tier1_sell_pct" in data:
        config.TIER1_SELL_PCT = float(data["tier1_sell_pct"])
        env_updates["TIER1_SELL_PCT"] = str(config.TIER1_SELL_PCT)
    if "tier2_tp_pct" in data:
        config.TIER2_TP_PCT = float(data["tier2_tp_pct"])
        env_updates["TIER2_TP_PCT"] = str(config.TIER2_TP_PCT)
    if "tier2_sell_pct" in data:
        config.TIER2_SELL_PCT = float(data["tier2_sell_pct"])
        env_updates["TIER2_SELL_PCT"] = str(config.TIER2_SELL_PCT)
    if "moonbag_trailing_drop_pct" in data:
        config.MOONBAG_TRAILING_DROP_PCT = float(data["moonbag_trailing_drop_pct"])
        env_updates["MOONBAG_TRAILING_DROP_PCT"] = str(config.MOONBAG_TRAILING_DROP_PCT)
    if "runner_hold_seconds" in data:
        config.RUNNER_HOLD_SECONDS = int(data["runner_hold_seconds"])
        env_updates["RUNNER_HOLD_SECONDS"] = str(config.RUNNER_HOLD_SECONDS)
    # Pre-Graduation Tracking
    if "pump_pre_graduation_tracking" in data:
        config.PUMP_PRE_GRADUATION_TRACKING = bool(data["pump_pre_graduation_tracking"])
        env_updates["PUMP_PRE_GRADUATION_TRACKING"] = str(config.PUMP_PRE_GRADUATION_TRACKING)
    if "pump_graduation_min_sol" in data:
        config.PUMP_GRADUATION_MIN_SOL = float(data["pump_graduation_min_sol"])
        env_updates["PUMP_GRADUATION_MIN_SOL"] = str(config.PUMP_GRADUATION_MIN_SOL)
    if "pump_graduation_max_sol" in data:
        config.PUMP_GRADUATION_MAX_SOL = float(data["pump_graduation_max_sol"])
        env_updates["PUMP_GRADUATION_MAX_SOL"] = str(config.PUMP_GRADUATION_MAX_SOL)

    # Quantitative Machine Learning Engine (XGBoost + Embeddings)
    if "ml_filter_enabled" in data:
        config.ML_FILTER_ENABLED = bool(data["ml_filter_enabled"])
        env_updates["ML_FILTER_ENABLED"] = str(config.ML_FILTER_ENABLED)
    if "max_rug_probability" in data:
        config.MAX_RUG_PROBABILITY = float(data["max_rug_probability"])
        env_updates["MAX_RUG_PROBABILITY"] = str(config.MAX_RUG_PROBABILITY)
    if "min_ml_alpha_score" in data:
        config.MIN_ML_ALPHA_SCORE = float(data["min_ml_alpha_score"])
        env_updates["MIN_ML_ALPHA_SCORE"] = str(config.MIN_ML_ALPHA_SCORE)
    if "max_clone_risk" in data:
        config.MAX_CLONE_RISK = float(data["max_clone_risk"])
        env_updates["MAX_CLONE_RISK"] = str(config.MAX_CLONE_RISK)
    if "ml_auto_retrain" in data:
        config.ML_AUTO_RETRAIN = bool(data["ml_auto_retrain"])
        env_updates["ML_AUTO_RETRAIN"] = str(config.ML_AUTO_RETRAIN)

    if env_updates:
        try:
            save_env_settings(env_updates)
        except Exception as e:
            print(f"⚠️ Failed to write settings to .env: {e}")

    bot_manager.broadcast("settings_updated", get_runtime_settings())
    return jsonify({"success": True, "message": "Settings updated & saved to .env", "settings": get_runtime_settings()})


@app.route("/api/ml/stats", methods=["GET"])
def get_ml_stats():
    return jsonify({
        "success": True,
        "stats": ml_engine.get_stats(),
        "enabled": config.ML_FILTER_ENABLED,
        "max_rug_probability": config.MAX_RUG_PROBABILITY,
        "min_ml_alpha_score": config.MIN_ML_ALPHA_SCORE,
        "max_clone_risk": config.MAX_CLONE_RISK,
    })


@app.route("/api/ml/retrain", methods=["POST"])
def retrain_ml_models():
    res = ml_engine.train_models()
    return jsonify(res)



@app.route("/api/agent/recent", methods=["GET"])
def get_recent_agent_verdicts():
    return jsonify({
        "success": True,
        "configured": agent_council.is_configured(),
        "enabled": config.AGENT_EVAL_ENABLED,
        "model": config.GEMINI_MODEL,
        "min_alpha_score": config.MIN_AGENT_ALPHA_SCORE,
        "verdicts": agent_council.get_recent_verdicts(),
    })


if __name__ == "__main__":
    # Start bot discovery and sniper engines in background
    bot_manager.start_workers()
    print("\n" + "=" * 65)
    print("🚀 SOLANA SHITCOIN TRADING TERMINAL SERVER RUNNING")
    print("🌐 Open dashboard in browser: http://127.0.0.1:5000")
    print("=" * 65 + "\n")
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
