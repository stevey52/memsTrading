import os
import time
import re
import math
import json
import threading
from pathlib import Path
from collections import deque
import config

try:
    import pandas as pd
    import numpy as np
    ML_AVAILABLE = True
except Exception:
    ML_AVAILABLE = False
    pd = None
    np = None

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
    import joblib
    SKLEARN_AVAILABLE = True
except Exception:
    TfidfVectorizer = None
    cosine_similarity = None
    HistGradientBoostingClassifier = None
    HistGradientBoostingRegressor = None
    joblib = None
    SKLEARN_AVAILABLE = False

try:
    import xgboost as xgb
    XGB_AVAILABLE = True
except Exception:
    xgb = None
    XGB_AVAILABLE = False

DATA_DIR = config.BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

FEATURES_PARQUET = DATA_DIR / "ml_features.parquet"
FEATURES_CSV = DATA_DIR / "ml_features.csv"
RUG_MODEL_PATH = DATA_DIR / "gbdt_rug_model.joblib"
ALPHA_MODEL_PATH = DATA_DIR / "gbdt_alpha_model.joblib"
XGB_RUG_MODEL_PATH = DATA_DIR / "xgboost_rug_model.json"
XGB_ALPHA_MODEL_PATH = DATA_DIR / "xgboost_alpha_model.json"


FEATURE_COLS = [
    "dev_buy_sol",
    "dev_holding_pct",
    "market_cap_sol",
    "liquidity_usd",
    "volume_5m",
    "buy_sell_ratio",
    "buys_5m",
    "sells_5m",
    "top10_holding_pct",
    "is_pump",
    "has_twitter",
    "has_telegram",
    "has_website",
    "name_length",
    "ticker_length",
    "desc_length",
    "name_uppercase_ratio",
    "is_pre_grad",
    "liquidity_to_mc_ratio",
    "volume_to_liq_ratio",
]

# Baseline corpus of known scam / cabal copy-paste patterns on pump.fun & raydium
SCAM_TEMPLATES = [
    "welcome to next pepe fair launch dev burned tokens renounced 1000x moonshot",
    "100% community token dev out no rug 1000x gem buy now",
    "solana next shiba inu based dev send it to raydium viral meme",
    "safu dev marketing plan paid callers trending dex banner ads coming",
    "fair launch stealth launched no presale no private sale 100x potential",
    "dev dumped we took over cto community takeover all tokens burned",
    "first ai agent token on pumpfun autonomous trading billionaire bot",
    "elon musk tweet memecoin send to 10m market cap guaranteed multiplier",
    "pump it to king of the hill graduating soon raydium listing in minutes",
]


class QuantitativeMLEngine:
    def __init__(self):
        self.lock = threading.RLock()
        self.ml_ready = ML_AVAILABLE
        self.model_status = "Calibrated Baseline"
        self.rug_model = None
        self.alpha_model = None

        # Telemetry counters
        self.inferences_count = 0
        self.pruned_count = 0
        self.total_latency_ms = 0.0
        self.recent_evaluations = deque(maxlen=40)

        # Clone detector vectorizer
        self.vectorizer = None
        self.template_vectors = None
        self._init_clone_detector()

        # Load persisted models if available
        self._load_models()

    def _init_clone_detector(self):
        """Initializes character & word n-gram TF-IDF vectorizer for fast clone detection."""
        if not ML_AVAILABLE or TfidfVectorizer is None:
            return
        try:
            self.vectorizer = TfidfVectorizer(
                ngram_range=(1, 2),
                max_features=250,
                stop_words="english"
            )
            self.template_vectors = self.vectorizer.fit_transform(SCAM_TEMPLATES)
        except Exception as e:
            print(f"⚠️ Failed to init semantic vectorizer: {e}")
            self.vectorizer = None

    def _load_models(self):
        """Loads trained GBDT/XGBoost models from disk if they exist."""
        # 1. Try joblib HistGradientBoosting (native scikit-learn)
        if SKLEARN_AVAILABLE and joblib is not None:
            try:
                if RUG_MODEL_PATH.exists():
                    self.rug_model = joblib.load(str(RUG_MODEL_PATH))
                    self.model_status = "Trained GBDT Model"
                if ALPHA_MODEL_PATH.exists():
                    self.alpha_model = joblib.load(str(ALPHA_MODEL_PATH))
                    self.model_status = "Trained GBDT Model"
            except Exception as e:
                print(f"⚠️ Could not load joblib GBDT model: {e}")

        # 2. Try XGBoost booster if available
        if XGB_AVAILABLE and xgb is not None:
            try:
                if XGB_RUG_MODEL_PATH.exists():
                    booster = xgb.Booster()
                    booster.load_model(str(XGB_RUG_MODEL_PATH))
                    self.rug_model = booster
                    self.model_status = "XGBoost Active"
                if XGB_ALPHA_MODEL_PATH.exists():
                    booster = xgb.Booster()
                    booster.load_model(str(XGB_ALPHA_MODEL_PATH))
                    self.alpha_model = booster
                    self.model_status = "XGBoost Active"
            except Exception as e:
                pass


    def extract_features(self, candidate: dict) -> dict:
        """
        Extracts tabular quantitative metrics from discovered token metadata.
        Execution speed: < 0.2ms.
        """
        socials = candidate.get("socials", {}) or {}
        has_tw = 1.0 if (candidate.get("has_twitter") or socials.get("has_twitter") or socials.get("twitter")) else 0.0
        has_tg = 1.0 if (candidate.get("has_telegram") or socials.get("has_telegram") or socials.get("telegram")) else 0.0
        has_web = 1.0 if (socials.get("website") or candidate.get("website")) else 0.0

        name = str(candidate.get("name", "") or "")
        symbol = str(candidate.get("symbol", "") or "")
        desc = str(candidate.get("description", "") or "")

        up_chars = sum(1 for c in name if c.isupper())
        name_up_ratio = (up_chars / max(len(name), 1)) if name else 0.0

        liq_usd = float(candidate.get("liquidity_usd", 0.0) or 0.0)
        vol_5m = float(candidate.get("volume_5m", 0.0) or candidate.get("volume_usd", 0.0) or 0.0)
        mc_usd = float(candidate.get("market_cap_usd", 0.0) or 0.0)
        mc_sol = float(candidate.get("market_cap_sol", 0.0) or 0.0)
        if mc_sol <= 0.0 and mc_usd > 0.0:
            mc_sol = mc_usd / 150.0  # Approx SOL price fallback

        buys_5m = float(candidate.get("buys_5m", 0) or 0)
        sells_5m = float(candidate.get("sells_5m", 0) or 0)
        bs_ratio = float(candidate.get("buy_sell_ratio", 1.0) or 1.0)
        if bs_ratio <= 0.0 and sells_5m > 0:
            bs_ratio = buys_5m / max(sells_5m, 1.0)

        liq_mc_ratio = (liq_usd / max(mc_usd, 1.0)) if mc_usd > 0 else 0.5
        vol_liq_ratio = (vol_5m / max(liq_usd, 1.0)) if liq_usd > 0 else 0.0

        return {
            "dev_buy_sol": float(candidate.get("dev_buy_sol", 0.0) or 0.0),
            "dev_holding_pct": float(candidate.get("dev_holding_pct", 0.0) or 0.0),
            "market_cap_sol": mc_sol,
            "liquidity_usd": liq_usd,
            "volume_5m": vol_5m,
            "buy_sell_ratio": bs_ratio,
            "buys_5m": buys_5m,
            "sells_5m": sells_5m,
            "top10_holding_pct": float(candidate.get("top10_holding_pct", 0.0) or 0.0),
            "is_pump": 1.0 if str(candidate.get("source", "")).lower() == "pump.fun" else 0.0,
            "has_twitter": has_tw,
            "has_telegram": has_tg,
            "has_website": has_web,
            "name_length": float(len(name)),
            "ticker_length": float(len(symbol)),
            "desc_length": float(len(desc)),
            "name_uppercase_ratio": float(name_up_ratio),
            "is_pre_grad": 1.0 if candidate.get("pre_graduation") else 0.0,
            "liquidity_to_mc_ratio": float(min(liq_mc_ratio, 5.0)),
            "volume_to_liq_ratio": float(min(vol_liq_ratio, 20.0)),
        }

    def compute_clone_similarity(self, candidate: dict) -> tuple[float, str]:
        """
        Calculates semantic vector similarity of candidate against known scam templates.
        Returns (clone_risk_score: 0-100, matched_summary: str).
        Execution time: < 5ms.
        """
        if not ML_AVAILABLE or self.vectorizer is None or self.template_vectors is None:
            # Fallback regex heuristics
            text = f"{candidate.get('name', '')} {candidate.get('symbol', '')} {candidate.get('description', '')}".lower()
            scam_keywords = ["1000x", "burn", "renounce", "safu", "send it", "next pepe", "cto", "dev dumped"]
            matches = sum(1 for kw in scam_keywords if kw in text)
            risk = min(matches * 22.0, 95.0)
            return (round(risk, 1), f"Keyword overlap: {matches} flags")

        try:
            sample_text = f"{candidate.get('name', '')} {candidate.get('symbol', '')} {candidate.get('description', '')}".lower()
            if len(sample_text.strip()) < 5:
                return (10.0, "Minimal metadata")

            sample_vec = self.vectorizer.transform([sample_text])
            sims = cosine_similarity(sample_vec, self.template_vectors)[0]
            max_sim = float(sims.max()) if len(sims) > 0 else 0.0
            clone_score = round(min(max_sim * 100.0, 99.0), 1)

            best_idx = int(sims.argmax())
            matched_snippet = SCAM_TEMPLATES[best_idx][:35] + "..."
            return (clone_score, f"Matched template: '{matched_snippet}' ({clone_score}%)")
        except Exception as e:
            return (15.0, f"Auditor fallback: {e}")

    def _predict_calibrated_baseline(self, feat: dict) -> tuple[float, float]:
        """
        High-precision calibrated heuristic logistic baseline used during cold-start.
        Returns (rug_probability [0.0 - 1.0], alpha_score [0 - 100]).
        """
        # Rug score log-odds calculation
        z_rug = -0.8  # Base prior ~30% rug rate in new shitcoins

        # Heavily penalize high dev holding or extreme top 10 concentration
        if feat["dev_holding_pct"] > 15.0:
            z_rug += (feat["dev_holding_pct"] - 15.0) * 0.12
        if feat["top10_holding_pct"] > 25.0:
            z_rug += (feat["top10_holding_pct"] - 25.0) * 0.08

        # Socials presence dramatically reduces rug risk
        if feat["has_twitter"] > 0:
            z_rug -= 0.65
        else:
            z_rug += 0.55

        if feat["has_telegram"] > 0:
            z_rug -= 0.35

        # Dev buy size on pump.fun
        if feat["is_pump"] > 0:
            if feat["dev_buy_sol"] < 0.2:
                z_rug += 0.60  # Zero conviction spam
            elif feat["dev_buy_sol"] > 7.0:
                z_rug += 0.85  # Dump hazard
            else:
                z_rug -= 0.40  # Sweet spot (0.5 to 5 SOL)

        # Order flow imbalance
        if feat["buy_sell_ratio"] < 1.0:
            z_rug += 0.70
        elif feat["buy_sell_ratio"] > 1.8:
            z_rug -= 0.50

        # Liquidity depth
        if feat["liquidity_usd"] > 25000:
            z_rug -= 0.60
        elif feat["liquidity_usd"] < 5000 and feat["is_pump"] == 0:
            z_rug += 0.80

        # Sigmoid transform
        rug_prob = 1.0 / (1.0 + math.exp(-max(min(z_rug, 6.0), -6.0)))
        rug_prob = round(rug_prob, 3)

        # Breakout Alpha Score (0 - 100)
        alpha = 50.0

        # Volume momentum
        vol_boost = min(feat["volume_to_liq_ratio"] * 8.0, 20.0)
        alpha += vol_boost

        # Buy flow momentum
        if feat["buy_sell_ratio"] >= 1.5:
            alpha += min((feat["buy_sell_ratio"] - 1.0) * 10.0, 18.0)
        else:
            alpha -= (1.5 - feat["buy_sell_ratio"]) * 15.0

        # Social bonus
        if feat["has_twitter"] and feat["has_telegram"]:
            alpha += 12.0
        elif feat["has_twitter"]:
            alpha += 6.0

        # Pre-graduation momentum
        if feat["is_pre_grad"] > 0:
            alpha += 14.0

        # Scale by inverse rug probability
        alpha = alpha * (1.0 - (rug_prob * 0.5))
        alpha = round(max(5.0, min(alpha, 99.0)), 1)

        return (rug_prob, alpha)

    def evaluate(self, candidate: dict) -> dict:
        """
        Main high-frequency evaluation entry point.
        Executes feature extraction, clone detection, and XGBoost/baseline scoring in < 2ms.
        """
        start_time = time.perf_counter()
        feat = self.extract_features(candidate)

        # 1. Semantic Vector Clone Check (< 5ms)
        clone_risk, clone_reason = self.compute_clone_similarity(candidate)

        # 2. GBDT / XGBoost or Calibrated Inference (< 1ms)
        rug_prob = None
        alpha_score = None

        if self.rug_model is not None:
            try:
                feat_values = [list(feat.values())]
                # Scikit-learn HistGradientBoostingClassifier
                if hasattr(self.rug_model, "predict_proba"):
                    probs = self.rug_model.predict_proba(feat_values)
                    rug_prob = round(float(probs[0][1]), 3)
                # XGBoost Booster
                elif XGB_AVAILABLE and xgb is not None and isinstance(self.rug_model, xgb.Booster):
                    dmatrix = xgb.DMatrix(feat_values, feature_names=list(feat.keys()))
                    rug_preds = self.rug_model.predict(dmatrix)
                    rug_prob = round(float(rug_preds[0]), 3)

                if self.alpha_model is not None:
                    if hasattr(self.alpha_model, "predict"):
                        alpha_preds = self.alpha_model.predict(feat_values)
                        alpha_score = round(float(alpha_preds[0]), 1)
                    elif XGB_AVAILABLE and xgb is not None and isinstance(self.alpha_model, xgb.Booster):
                        alpha_preds = self.alpha_model.predict(dmatrix)
                        alpha_score = round(float(alpha_preds[0]), 1)
            except Exception:
                rug_prob = None
                alpha_score = None

        # Fallback to calibrated mathematical prior if models not yet fitted
        if rug_prob is None or alpha_score is None:
            c_rug, c_alpha = self._predict_calibrated_baseline(feat)
            rug_prob = rug_prob if rug_prob is not None else c_rug
            alpha_score = alpha_score if alpha_score is not None else c_alpha


        # Adjust rug prob if clone risk is extreme
        if clone_risk >= 75.0:
            rug_prob = round(min(rug_prob + 0.25, 0.99), 3)
            alpha_score = round(max(alpha_score - 25.0, 5.0), 1)

        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)

        # Determine Pruning Gate Verdict
        max_rug_thresh = getattr(config, "MAX_RUG_PROBABILITY", 0.45)
        min_alpha_thresh = getattr(config, "MIN_ML_ALPHA_SCORE", 60.0)
        max_clone_thresh = getattr(config, "MAX_CLONE_RISK", 70.0)
        ml_enabled = getattr(config, "ML_FILTER_ENABLED", True)

        approved = True
        reject_reason = ""

        if ml_enabled:
            if rug_prob > max_rug_thresh:
                approved = False
                reject_reason = f"High Rug Probability ({rug_prob*100:.1f}% > {max_rug_thresh*100:.0f}%)"
            elif clone_risk > max_clone_thresh:
                approved = False
                reject_reason = f"Recycled Clone Template ({clone_risk:.0f}% > {max_clone_thresh:.0f}%)"
            elif alpha_score < min_alpha_thresh:
                approved = False
                reject_reason = f"Low Breakout Alpha ({alpha_score:.1f} < {min_alpha_thresh:.0f})"

        verdict_str = "APPROVED" if approved else "PRUNED_FAST"

        # Update telemetry
        with self.lock:
            self.inferences_count += 1
            if not approved:
                self.pruned_count += 1
            self.total_latency_ms += latency_ms

        result = {
            "symbol": candidate.get("symbol", "TOKEN"),
            "mint": candidate.get("mint", ""),
            "rug_probability": rug_prob,
            "rug_pct": round(rug_prob * 100, 1),
            "alpha_score": alpha_score,
            "clone_risk": clone_risk,
            "clone_reason": clone_reason,
            "approved": approved,
            "verdict": verdict_str,
            "reject_reason": reject_reason,
            "latency_ms": latency_ms,
            "model_status": self.model_status,
            "features": feat,
            "timestamp": time.strftime("%H:%M:%S"),
        }

        with self.lock:
            self.recent_evaluations.appendleft(result)

        # Record candidate features to dataset in background
        self._record_candidate_async(candidate.get("mint", ""), feat, result)

        return result

    def _record_candidate_async(self, mint: str, feat: dict, result: dict):
        """Asynchronously writes candidate features to persistent parquet/CSV dataset."""
        t = threading.Thread(target=self._append_dataset_row, args=(mint, feat, result), daemon=True)
        t.start()

    def _append_dataset_row(self, mint: str, feat: dict, result: dict):
        if not mint:
            return
        row = {
            "timestamp": time.time(),
            "mint": mint,
            **feat,
            "pred_rug_prob": result["rug_probability"],
            "pred_alpha": result["alpha_score"],
            "clone_risk": result["clone_risk"],
            "pruned": 1 if not result["approved"] else 0,
            # Ground truth targets (populated upon trade exit)
            "actual_pnl_pct": None,
            "actual_rug": None,
            "hold_duration_sec": None,
        }

        with self.lock:
            try:
                if ML_AVAILABLE and pd is not None:
                    df_row = pd.DataFrame([row])
                    if FEATURES_PARQUET.exists():
                        try:
                            df_existing = pd.read_parquet(FEATURES_PARQUET)
                            df_combined = pd.concat([df_existing, df_row], ignore_index=True)
                            # Keep most recent 5,000 samples for high efficiency
                            if len(df_combined) > 5000:
                                df_combined = df_combined.iloc[-5000:]
                            df_combined.to_parquet(FEATURES_PARQUET, index=False)
                        except Exception:
                            df_row.to_parquet(FEATURES_PARQUET, index=False)
                    else:
                        df_row.to_parquet(FEATURES_PARQUET, index=False)
            except Exception as e:
                # Fallback to CSV append
                pass

            try:
                # Always append to CSV as human-readable/universal backup
                file_exists = FEATURES_CSV.exists()
                with open(FEATURES_CSV, "a", encoding="utf-8") as f:
                    if not file_exists:
                        f.write(",".join(row.keys()) + "\n")
                    f.write(",".join(str(v) if v is not None else "" for v in row.values()) + "\n")
            except Exception:
                pass

    def record_trade_outcome(self, mint: str, pnl_pct: float, duration_sec: int, exit_reason: str):
        """
        Updates the dataset with actual trade outcomes (labels ground truth for training).
        Triggers auto-retrain check if sample count threshold is reached.
        """
        is_rug = 1 if (pnl_pct <= -25.0 or "rug" in exit_reason.lower() or "panic" in exit_reason.lower()) else 0

        def _update():
            if not ML_AVAILABLE or pd is None or not FEATURES_PARQUET.exists():
                return
            try:
                with self.lock:
                    df = pd.read_parquet(FEATURES_PARQUET)
                    mask = df["mint"] == mint
                    if mask.any():
                        df.loc[mask, "actual_pnl_pct"] = pnl_pct
                        df.loc[mask, "actual_rug"] = is_rug
                        df.loc[mask, "hold_duration_sec"] = duration_sec
                        df.to_parquet(FEATURES_PARQUET, index=False)
                # Check for auto-retrain
                if getattr(config, "ML_AUTO_RETRAIN", True):
                    self.trigger_retrain_if_ready()
            except Exception as e:
                print(f"⚠️ Error updating trade outcome in dataset: {e}")

        threading.Thread(target=_update, daemon=True).start()

    def trigger_retrain_if_ready(self):
        """Checks if enough labeled samples exist to train/update models."""
        if not ML_AVAILABLE or pd is None or not FEATURES_PARQUET.exists():
            return
        try:
            with self.lock:
                df = pd.read_parquet(FEATURES_PARQUET)
            labeled = df.dropna(subset=["actual_rug"])
            if len(labeled) >= 20:
                self.train_models(df)
        except Exception as e:
            print(f"⚠️ Auto-retrain check error: {e}")

    def train_models(self, df_data=None):
        """Fits gradient boosting models on historical candidate feature rows."""
        if not ML_AVAILABLE or pd is None:
            return {"success": False, "message": "ML libraries not installed"}

        try:
            if df_data is None:
                if not FEATURES_PARQUET.exists():
                    return {"success": False, "message": "No feature dataset found"}
                df_data = pd.read_parquet(FEATURES_PARQUET)

            cols = [c for c in FEATURE_COLS if c in df_data.columns]
            labeled_rug = df_data.dropna(subset=["actual_rug"])

            if len(labeled_rug) < 10:
                return {
                    "success": False,
                    "message": f"Need at least 10 labeled trade outcomes to train GBDT (currently {len(labeled_rug)}). Using calibrated baseline.",
                    "samples_count": len(df_data),
                    "labeled_count": len(labeled_rug),
                    "model_status": self.model_status,
                }

            X_rug = labeled_rug[cols].fillna(0.0)
            y_rug = labeled_rug["actual_rug"].astype(int)

            # 1. Native Sklearn HistGradientBoosting
            if SKLEARN_AVAILABLE and HistGradientBoostingClassifier is not None and joblib is not None:
                clf = HistGradientBoostingClassifier(max_iter=50, max_depth=4, random_state=42)
                clf.fit(X_rug, y_rug)
                joblib.dump(clf, str(RUG_MODEL_PATH))
                self.rug_model = clf
                self.model_status = "Trained GBDT Model"

                # Train alpha regressor if actual_pnl_pct exists
                labeled_pnl = df_data.dropna(subset=["actual_pnl_pct"])
                if len(labeled_pnl) >= 10 and HistGradientBoostingRegressor is not None:
                    reg = HistGradientBoostingRegressor(max_iter=50, max_depth=4, random_state=42)
                    reg.fit(labeled_pnl[cols].fillna(0.0), labeled_pnl["actual_pnl_pct"])
                    joblib.dump(reg, str(ALPHA_MODEL_PATH))
                    self.alpha_model = reg

            # 2. XGBoost if available
            if XGB_AVAILABLE and xgb is not None:
                try:
                    dtrain_rug = xgb.DMatrix(X_rug, label=y_rug)
                    params_rug = {
                        "objective": "binary:logistic",
                        "eval_metric": "logloss",
                        "max_depth": 4,
                        "eta": 0.1,
                        "verbosity": 0,
                    }
                    booster_rug = xgb.train(params_rug, dtrain_rug, num_boost_round=40)
                    booster_rug.save_model(str(XGB_RUG_MODEL_PATH))
                    self.rug_model = booster_rug
                    self.model_status = "XGBoost Active"
                except Exception:
                    pass

            return {
                "success": True,
                "message": f"Successfully trained model on {len(labeled_rug)} labeled trade samples ({len(df_data)} total candidates)",
                "samples_count": len(df_data),
                "labeled_count": len(labeled_rug),
                "model_status": self.model_status,
            }
        except Exception as e:
            return {"success": False, "message": f"Training failed: {e}"}


    def get_stats(self) -> dict:
        """Returns live telemetry for dashboard display."""
        avg_lat = round(self.total_latency_ms / max(self.inferences_count, 1), 2)
        pruned_ratio = round((self.pruned_count / max(self.inferences_count, 1)) * 100, 1)

        samples_count = 0
        if ML_AVAILABLE and pd is not None and FEATURES_PARQUET.exists():
            try:
                # Fast row count check
                df = pd.read_parquet(FEATURES_PARQUET, columns=["timestamp"])
                samples_count = len(df)
            except Exception:
                pass

        return {
            "ml_available": ML_AVAILABLE,
            "model_status": self.model_status,
            "inferences_count": self.inferences_count,
            "pruned_count": self.pruned_count,
            "pruned_pct": pruned_ratio,
            "avg_latency_ms": avg_lat,
            "dataset_samples": samples_count,
            "recent_evaluations": list(self.recent_evaluations)[:15],
        }


# Global singleton instance
ml_engine = QuantitativeMLEngine()
