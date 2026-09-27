import os
import sys
import json
import time
import tempfile
import threading
import unittest
from unittest.mock import patch, MagicMock

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

import config
import safety
import social_checker
from scanner import TokenScanner
from agent_council import AgentCouncil
from bot_manager import BotManager
import app as flask_app


class TestConfigAndWallet(unittest.TestCase):
    def test_default_constants(self):
        self.assertGreater(config.TRADE_AMOUNT_SOL, 0)
        self.assertGreater(config.SLIPPAGE_BPS, 0)
        self.assertGreater(config.TAKE_PROFIT_PCT, 0)
        self.assertGreater(config.STOP_LOSS_PCT, 0)
        self.assertIsNotNone(config.WSOL_MINT)

    def test_load_wallet_missing(self):
        with patch.dict(os.environ, {"SOLANA_PRIVATE_KEY": ""}):
            kp, addr = config.load_wallet()
            self.assertIsNone(kp)
            self.assertIsNone(addr)

    def test_load_wallet_valid(self):
        # Generate a real random solders keypair for verification
        from solders.keypair import Keypair
        import base58
        kp = Keypair()
        b58_key = base58.b58encode(bytes(kp)).decode("utf-8")

        with patch.dict(os.environ, {"SOLANA_PRIVATE_KEY": b58_key}):
            loaded_kp, loaded_addr = config.load_wallet()
            self.assertIsNotNone(loaded_kp)
            self.assertEqual(str(kp.pubkey()), loaded_addr)


class TestSocialChecker(unittest.TestCase):
    def test_twitter_validation(self):
        # Valid handles
        ok, handle = social_checker.is_valid_twitter("https://x.com/solana_coin")
        self.assertTrue(ok)
        self.assertEqual(handle, "@solana_coin")

        ok, handle = social_checker.is_valid_twitter("https://twitter.com/CryptoPepe")
        self.assertTrue(ok)
        self.assertEqual(handle, "@CryptoPepe")

        # Invalid: placeholder roots
        ok, err = social_checker.is_valid_twitter("https://x.com/")
        self.assertFalse(ok)
        self.assertIn("Placeholder", err)

        # Invalid: reserved path
        ok, err = social_checker.is_valid_twitter("https://twitter.com/explore")
        self.assertFalse(ok)
        self.assertIn("Reserved path", err)

    def test_telegram_validation(self):
        # Valid portal
        ok, channel = social_checker.is_valid_telegram("https://t.me/pepe_sol_army")
        self.assertTrue(ok)
        self.assertEqual(channel, "t.me/pepe_sol_army")

        # Valid invite
        ok, channel = social_checker.is_valid_telegram("https://t.me/joinchat/AAAAAF")
        self.assertTrue(ok)

        # Invalid placeholder
        ok, err = social_checker.is_valid_telegram("https://t.me")
        self.assertFalse(ok)

    def test_website_validation(self):
        # Valid project domain
        ok, url = social_checker.is_valid_website("https://pepecoinsol.xyz")
        self.assertTrue(ok)

        # Blacklisted generic platform
        ok, err = social_checker.is_valid_website("https://pump.fun/coin123")
        self.assertFalse(ok)
        self.assertIn("generic platform", err)

    def test_resolve_ipfs_url(self):
        ipfs_uri = "ipfs://QmXoypizjW3WknFiJnKLwHCnL72vedxjQkDDP1mXWo6uco"
        urls = social_checker.resolve_ipfs_url(ipfs_uri)
        self.assertEqual(len(urls), 4)
        self.assertTrue(any("cf-ipfs.com" in u for u in urls))
        self.assertTrue(any("ipfs.io" in u for u in urls))

    def test_concurrent_ipfs_fetch_success(self):
        mock_meta = {"name": "TestCoin", "twitter": "https://x.com/testcoin"}
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_meta

        with patch.object(social_checker.session, "get", return_value=mock_resp):
            data = social_checker.fetch_ipfs_metadata("ipfs://QmValidHashTest", timeout=1.0)
            self.assertIsNotNone(data)
            self.assertEqual(data.get("name"), "TestCoin")


class TestSafetyAndHolderDistribution(unittest.TestCase):
    @patch("safety.rpc_call")
    def test_holder_distribution_healthy(self, mock_rpc):
        # Supply: 1 billion
        mock_rpc.side_effect = [
            {"value": {"uiAmount": 1_000_000_000.0}},  # getTokenSupply
            {
                "value": [
                    {"address": "BondingCurve111", "uiAmount": 700_000_000.0},
                    {"address": "HolderA", "uiAmount": 30_000_000.0},  # 3%
                    {"address": "HolderB", "uiAmount": 20_000_000.0},  # 2%
                ]
            },
        ]
        is_safe, reason, stats = safety.check_token_holders_distribution(
            "TokenMint111", bonding_curve_key="BondingCurve111", max_single_pct=10.0, max_top10_pct=25.0
        )
        self.assertTrue(is_safe)
        self.assertEqual(stats["highest_holder_pct"], 3.0)
        self.assertIn("Healthy Distribution", reason)

    @patch("safety.rpc_call")
    def test_holder_distribution_whale_risk(self, mock_rpc):
        # Whale holds 25% of supply
        mock_rpc.side_effect = [
            {"value": {"uiAmount": 1_000_000_000.0}},
            {
                "value": [
                    {"address": "BondingCurve111", "uiAmount": 600_000_000.0},
                    {"address": "WhaleDevWallet", "uiAmount": 250_000_000.0},  # 25%
                ]
            },
        ]
        is_safe, reason, stats = safety.check_token_holders_distribution(
            "TokenMint111", bonding_curve_key="BondingCurve111", max_single_pct=10.0
        )
        self.assertFalse(is_safe)
        self.assertIn("Concentration Risk", reason)

    @patch("safety.requests.get")
    def test_rugcheck_safety(self, mock_get):
        # Clean rugcheck
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"score": 150, "risks": [], "lpLockedPct": 100}
        mock_get.return_value = mock_resp

        is_safe, reason = safety.check_token_safety("CleanTokenMint111")
        self.assertTrue(is_safe)

        # Dangerous rugcheck
        mock_resp.json.return_value = {
            "score": 900,
            "risks": [{"name": "Mint Authority Enabled", "level": "danger"}],
        }
        is_safe, reason = safety.check_token_safety("DangerTokenMint111")
        self.assertFalse(is_safe)
        self.assertIn("Danger flags", reason)


class TestAgentCouncil(unittest.TestCase):
    def setUp(self):
        self.council = AgentCouncil()

    def test_bypass_when_unconfigured(self):
        with patch.object(self.council, "is_configured", return_value=False):
            candidate = {"symbol": "PEPE", "mint": "Mint111"}
            res = self.council.evaluate_candidate(candidate)
            self.assertFalse(res["configured"])
            self.assertTrue(res["approved"])
            self.assertEqual(res["alpha_score"], 0.0)
            self.assertIn("Bypassed", res["verdict_summary"])

    def test_cache_hit(self):
        candidate = {"symbol": "DOGE", "mint": "MintCached123"}
        self.council.cache["MintCached123"] = ({"cached": True, "mint": "MintCached123"}, time.time())
        res = self.council.evaluate_candidate(candidate)
        self.assertTrue(res.get("cached"))

    @patch("agent_council.requests.Session.post")
    def test_active_gemini_evaluation(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        gemini_payload = {
            "symbol": "ELON",
            "narrative_score": 92.0,
            "narrative_reasoning": "Strong viral Elon tweet meta.",
            "safety_score": 88.0,
            "safety_reasoning": "Distributed liquidity and verified socials.",
            "alpha_score": 90.0,
            "suggested_action": "BUY",
            "target_tp_pct": 35.0,
            "target_sl_pct": 8.0,
            "size_multiplier": 1.25,
            "verdict_summary": "High conviction viral meta.",
        }
        mock_resp.json.return_value = {
            "candidates": [{"content": {"parts": [{"text": json.dumps(gemini_payload)}]}}]
        }
        mock_post.return_value = mock_resp

        with patch.object(config, "GEMINI_API_KEY", "test_key_123"):
            with patch.object(self.council, "is_configured", return_value=True):
                candidate = {
                    "symbol": "ELON",
                    "mint": "ElonMint123",
                    "socials": {"twitter": "@elon"},
                    "holders": {"top10_non_curve_pct": 12.0},
                }
                res = self.council.evaluate_candidate(candidate)
                self.assertTrue(res["configured"])
                self.assertTrue(res["approved"])
                self.assertEqual(res["alpha_score"], 90.0)
                self.assertEqual(res["target_tp_pct"], 35.0)

    def test_multi_key_rotation(self):
        with patch.object(config, "GEMINI_API_KEY", "key1,key2,key3"):
            keys = self.council._get_api_keys()
            self.assertEqual(keys, ["key1", "key2", "key3"])
            self.assertEqual(self.council._select_api_key(), "key1")
            self.assertEqual(self.council._select_api_key(), "key2")
            self.assertEqual(self.council._select_api_key(), "key3")
            self.assertEqual(self.council._select_api_key(), "key1")

    def test_rate_limit_cooldown_heuristic_fallback(self):
        with patch.object(config, "GEMINI_API_KEY", "test_key_123"):
            self.council.cooldown_until = time.time() + 30.0
            candidate = {
                "symbol": "SAFEPEPE",
                "mint": "SafePepe123",
                "socials": {"twitter": "@safepepe", "telegram": "t.me/safepepe"},
                "holders": {"top10_non_curve_pct": 8.0},
                "dev_sol": 1.2,
                "rugcheck_score": 50,
            }
            res = self.council.evaluate_candidate(candidate)
            self.assertEqual(res["model"], "local-heuristic-consensus")
            self.assertTrue(res["approved"])
            self.assertGreaterEqual(res["alpha_score"], 75.0)
            self.assertEqual(res["suggested_action"], "BUY")


class TestBotManagerConcurrency(unittest.TestCase):
    def setUp(self):
        self.bot = BotManager()

    def test_trade_lock_mutual_exclusion(self):
        self.assertFalse(self.bot.is_trading())

        # Acquire lock manually to simulate active trade
        self.assertTrue(self.bot.trade_lock.acquire(blocking=False))
        self.assertTrue(self.bot.is_trading())

        # Secondary call to execute_scalp should be rejected immediately by lock
        rejected = self.bot.execute_scalp("FakeMint", 0.02, dry_run=True, token_info={"symbol": "FAIL"})
        self.assertFalse(rejected)

        # Release lock
        self.bot.trade_lock.release()
        self.assertFalse(self.bot.is_trading())

    def test_sse_subscriber_queue(self):
        q = self.bot.subscribe()
        self.bot.broadcast("test_event", {"msg": "hello_solana"})
        msg = q.get_nowait()
        self.assertEqual(msg["event"], "test_event")
        self.assertEqual(msg["data"]["msg"], "hello_solana")
        self.bot.unsubscribe(q)
        self.assertNotIn(q, self.bot.subscribers)


class TestScannerAnalysis(unittest.TestCase):
    def setUp(self):
        self.scanner = TokenScanner(
            min_liquidity=10000,
            min_5m_volume=5000,
            min_buy_sell_ratio=1.2,
        )

    def test_low_liquidity_filtered(self):
        pair = {
            "baseToken": {"address": "Mint1", "symbol": "TEST"},
            "liquidity": {"usd": 4000},
            "volume": {"m5": 6000},
            "priceChange": {"m5": 5.0},
            "txns": {"m5": {"buys": 50, "sells": 10}},
        }
        res, reason = self.scanner.analyze_token_pair(pair)
        self.assertIsNone(res)
        self.assertIn("Low Liq", reason)

    def test_weak_order_flow_filtered(self):
        pair = {
            "baseToken": {"address": "Mint2", "symbol": "TEST"},
            "liquidity": {"usd": 25000},
            "volume": {"m5": 10000},
            "priceChange": {"m5": 5.0},
            "txns": {"m5": {"buys": 10, "sells": 40}},  # Seller dominated
        }
        res, reason = self.scanner.analyze_token_pair(pair)
        self.assertIsNone(res)
        self.assertIn("Weak buyer ratio", reason)

    @patch("scanner.check_token_safety", return_value=(True, "Safe"))
    @patch("scanner.check_token_holders_distribution", return_value=(True, "Healthy", {"top10_non_curve_pct": 10.0}))
    @patch("scanner.get_quote", return_value={"outAmount": "1000000"})
    def test_successful_dexscreener_social_enrichment(self, mock_quote, mock_holders, mock_safety):
        pair = {
            "baseToken": {"address": "MintPass123", "symbol": "MOON", "name": "Moon Coin"},
            "liquidity": {"usd": 30000},
            "volume": {"m5": 15000},
            "priceChange": {"m5": 8.0},
            "txns": {"m5": {"buys": 80, "sells": 20}},
            "dexId": "raydium",
            "url": "https://dexscreener.com/solana/moon",
            "info": {
                "websites": [{"url": "https://moonsol.com"}],
                "socials": [
                    {"type": "twitter", "url": "https://x.com/moonsol"},
                    {"type": "telegram", "url": "https://t.me/moonsol"},
                ],
                "header": "The next big meme on Solana",
            },
        }
        res, reason = self.scanner.analyze_token_pair(pair)
        self.assertIsNotNone(res)
        self.assertEqual(res["symbol"], "MOON")
        self.assertEqual(res["name"], "Moon Coin")
        self.assertEqual(res["socials"]["twitter"], "https://x.com/moonsol")
        self.assertEqual(res["socials"]["telegram"], "https://t.me/moonsol")
        self.assertEqual(res["socials"]["website"], "https://moonsol.com")
        self.assertEqual(res["holders"]["top10_non_curve_pct"], 10.0)


class TestAppEndpointsAndEnvPersistence(unittest.TestCase):
    def setUp(self):
        flask_app.app.config["TESTING"] = True
        self.client = flask_app.app.test_client()

    def test_status_endpoint(self):
        resp = self.client.get("/api/status")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("bot_mode", data)
        self.assertIn("trade_mode", data)
        self.assertIn("settings", data)

    def test_manual_scalp_lock_rejection(self):
        # Put bot into trading state via lock
        from bot_manager import bot_manager
        with bot_manager.trade_lock:
            resp = self.client.post("/api/scalp", json={"mint": "TestMint123", "amount": 0.02})
            self.assertEqual(resp.status_code, 400)
            data = resp.get_json()
            self.assertFalse(data["success"])
            self.assertIn("Active trade already in progress", data["message"])

    def test_settings_persistence_to_env(self):
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as tf:
            tf.write("# Test Config\nTAKE_PROFIT_PCT=20.0\nSTOP_LOSS_PCT=10.0\n")
            temp_path = tf.name

        try:
            updates = {
                "TAKE_PROFIT_PCT": "35.5",
                "NEW_AGENT_FLAG": "True",
            }
            flask_app.save_env_settings(updates, env_path=temp_path)

            with open(temp_path, "r", encoding="utf-8") as f:
                content = f.read()

            self.assertIn("TAKE_PROFIT_PCT=35.5", content)
            self.assertIn("NEW_AGENT_FLAG=True", content)
            self.assertIn("# Test Config", content)
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)


class TestMoonbagAndRunnerEngine(unittest.TestCase):
    def test_config_moonbag_defaults(self):
        self.assertIsInstance(config.MOONBAG_ENABLED, bool)
        self.assertGreater(config.TIER1_TP_PCT, 0)
        self.assertGreater(config.TIER1_SELL_PCT, 0)
        self.assertGreater(config.TIER2_TP_PCT, 0)
        self.assertGreater(config.TIER2_SELL_PCT, 0)
        self.assertGreater(config.MOONBAG_TRAILING_DROP_PCT, 0)
        self.assertGreater(config.RUNNER_HOLD_SECONDS, 0)
        self.assertIsInstance(config.PUMP_PRE_GRADUATION_TRACKING, bool)
        self.assertGreater(config.PUMP_GRADUATION_MIN_SOL, 0)
        self.assertGreater(config.PUMP_GRADUATION_MAX_SOL, config.PUMP_GRADUATION_MIN_SOL)

    def test_agent_council_runner_classification(self):
        council = AgentCouncil()

        # 1. Pre-graduation token in bypass mode should default to RUNNER
        with patch.object(council, "is_configured", return_value=False):
            candidate = {"symbol": "PREGRAD", "mint": "MintPreGrad1", "pre_graduation": True}
            res = council.evaluate_candidate(candidate)
            self.assertEqual(res["trade_strategy"], "RUNNER")

        # 2. Standard token in bypass mode should default to SCALP
        with patch.object(council, "is_configured", return_value=False):
            candidate = {"symbol": "SCALP1", "mint": "MintScalp1"}
            res = council.evaluate_candidate(candidate)
            self.assertEqual(res["trade_strategy"], "SCALP")

        # 3. LLM returns trade_strategy
        with patch.object(config, "GEMINI_API_KEY", "test_key_123"):
            with patch.object(council, "is_configured", return_value=True):
                with patch("agent_council.requests.Session.post") as mock_post:
                    mock_resp = MagicMock()
                    mock_resp.status_code = 200
                    gemini_payload = {
                        "symbol": "RUNNER1",
                        "narrative_score": 95.0,
                        "narrative_reasoning": "Mega viral",
                        "safety_score": 90.0,
                        "safety_reasoning": "Safe liquidity",
                        "alpha_score": 92.0,
                        "trade_strategy": "RUNNER",
                        "suggested_action": "BUY",
                        "target_tp_pct": 80.0,
                        "target_sl_pct": 10.0,
                        "size_multiplier": 1.5,
                        "verdict_summary": "High conviction runner",
                    }
                    mock_resp.json.return_value = {
                        "candidates": [{"content": {"parts": [{"text": json.dumps(gemini_payload)}]}}]
                    }
                    mock_post.return_value = mock_resp

                    candidate = {"symbol": "RUNNER1", "mint": "MintRunner123"}
                    res = council.evaluate_candidate(candidate)
                    self.assertEqual(res["trade_strategy"], "RUNNER")
                    self.assertEqual(res["alpha_score"], 92.0)

    def test_pre_graduation_curve_progress_math(self):
        # 30 SOL is 0% curve progress
        p0 = round(min(100.0, max(0.0, ((30.0 - 30.0) / (85.0 - 30.0)) * 100)), 1)
        self.assertEqual(p0, 0.0)

        # 65 SOL (pre-graduation minimum) is ~63.6% progress
        p65 = round(min(100.0, max(0.0, ((65.0 - 30.0) / (85.0 - 30.0)) * 100)), 1)
        self.assertEqual(p65, 63.6)

        # 84 SOL (pre-graduation upper bound) is ~98.2% progress
        p84 = round(min(100.0, max(0.0, ((84.0 - 30.0) / (85.0 - 30.0)) * 100)), 1)
        self.assertEqual(p84, 98.2)

        # 85 SOL (graduation to Raydium) is 100% progress
        p85 = round(min(100.0, max(0.0, ((85.0 - 30.0) / (85.0 - 30.0)) * 100)), 1)
        self.assertEqual(p85, 100.0)

    def test_multi_tier_take_profit_accounting_model(self):
        # Entry: 0.02 SOL, 1,000,000 tokens
        entry_sol = 0.02
        initial_tokens = 1_000_000
        remaining_tokens = initial_tokens
        realized_sol_banked = 0.0

        # Tier 1 (+80%): Sell 50%
        sell_tier1 = int(initial_tokens * (config.TIER1_SELL_PCT / 100.0))
        self.assertEqual(sell_tier1, 500_000)
        sold_sol_tier1 = 0.018
        realized_sol_banked += sold_sol_tier1
        remaining_tokens -= sell_tier1
        self.assertEqual(remaining_tokens, 500_000)

        # Tier 2 (+250%): Sell 25% of initial tokens
        sell_tier2 = int(initial_tokens * (config.TIER2_SELL_PCT / 100.0))
        self.assertEqual(sell_tier2, 250_000)
        sold_sol_tier2 = 0.0175
        realized_sol_banked += sold_sol_tier2
        remaining_tokens -= sell_tier2

        # Final remaining tokens is the 25% Moonbag (250,000 tokens)
        self.assertEqual(remaining_tokens, 250_000)
        self.assertGreater(realized_sol_banked, entry_sol)
        self.assertAlmostEqual(realized_sol_banked, 0.0355, places=4)

    def test_flask_settings_api_moonbag_updates(self):
        flask_app.app.config["TESTING"] = True
        client = flask_app.app.test_client()

        payload = {
            "moonbag_enabled": True,
            "tier1_tp_pct": 85.0,
            "tier2_tp_pct": 275.0,
            "moonbag_trailing_drop_pct": 25.0,
            "runner_hold_seconds": 1500,
            "pump_pre_graduation_tracking": True,
        }
        resp = client.post("/api/settings", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["settings"]["tier1_tp_pct"], 85.0)
        self.assertEqual(data["settings"]["tier2_tp_pct"], 275.0)
        self.assertEqual(data["settings"]["moonbag_trailing_drop_pct"], 25.0)
        self.assertEqual(data["settings"]["runner_hold_seconds"], 1500)


class TestQuantitativeMLEngine(unittest.TestCase):
    def setUp(self):
        from ml_engine import ml_engine
        self.engine = ml_engine

    def test_feature_extraction(self):
        candidate = {
            "symbol": "MLPEPE",
            "name": "ML Pepe Coin",
            "description": "Next viral meme coin on Solana",
            "liquidity_usd": 15000.0,
            "volume_5m": 25000.0,
            "dev_buy_sol": 1.5,
            "dev_holding_pct": 5.0,
            "top10_holding_pct": 18.0,
            "buy_sell_ratio": 1.6,
            "socials": {"twitter": "https://x.com/mlpepe", "telegram": "https://t.me/mlpepe"},
        }
        feat = self.engine.extract_features(candidate)
        self.assertEqual(feat["dev_buy_sol"], 1.5)
        self.assertEqual(feat["dev_holding_pct"], 5.0)
        self.assertEqual(feat["liquidity_usd"], 15000.0)
        self.assertEqual(feat["has_twitter"], 1.0)
        self.assertEqual(feat["has_telegram"], 1.0)
        self.assertGreater(feat["name_length"], 0)

    def test_calibrated_baseline_prediction(self):
        feat = {
            "dev_buy_sol": 1.5,
            "dev_holding_pct": 5.0,
            "top10_holding_pct": 15.0,
            "has_twitter": 1.0,
            "has_telegram": 1.0,
            "is_pump": 1.0,
            "buy_sell_ratio": 1.8,
            "liquidity_usd": 20000.0,
            "volume_to_liq_ratio": 1.5,
            "is_pre_grad": 1.0,
        }
        rug_prob, alpha = self.engine._predict_calibrated_baseline(feat)
        self.assertGreaterEqual(rug_prob, 0.0)
        self.assertLessEqual(rug_prob, 1.0)
        self.assertGreaterEqual(alpha, 0.0)
        self.assertLessEqual(alpha, 100.0)
        self.assertLess(rug_prob, 0.45)
        self.assertGreater(alpha, 60.0)

    def test_clone_detection_recycled_template(self):
        clone_candidate = {
            "name": "Pepe Fair Launch",
            "symbol": "PEPE1000X",
            "description": "welcome to next pepe fair launch dev burned tokens renounced 1000x moonshot gem",
        }
        clone_risk, reason = self.engine.compute_clone_similarity(clone_candidate)
        self.assertGreater(clone_risk, 30.0)

    def test_fast_pruning_decision(self):
        bad_candidate = {
            "symbol": "SCAMCOIN",
            "name": "Scam Coin",
            "description": "dev dumped we took over",
            "dev_holding_pct": 35.0,
            "top10_holding_pct": 60.0,
            "buy_sell_ratio": 0.2,
            "liquidity_usd": 1000.0,
            "dev_buy_sol": 0.05,
            "socials": {},
        }
        res = self.engine.evaluate(bad_candidate)
        self.assertFalse(res["approved"])
        self.assertEqual(res["verdict"], "PRUNED_FAST")
        self.assertIn("rug_probability", res)
        self.assertIn("alpha_score", res)


if __name__ == "__main__":
    unittest.main(verbosity=2)
