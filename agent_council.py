import json
import time
from collections import deque
from threading import Lock
import requests
import config


class AgentCouncil:
    """
    Autonomous Multi-Agent AI Council for Solana Memecoin & Shitcoin Trading.
    Leverages Google Gemini 2.5 Flash for rapid multi-persona evaluations:
      1. 🧠 Narrative & Virality Scout: Meme relevance, cultural meta, humor, ticker catchiness.
      2. 🕵️ Forensic Cabal Auditor: Dev dump risks, bundle farm detection, social authenticity.
      3. 📈 Trade Strategist: Volatility-adjusted dynamic TP/SL targets and position sizing.
      4. 👑 Consensus Orchestrator: Composite Alpha Score (0-100) gating trade dispatch.
    """

    def __init__(self):
        self.lock = Lock()
        self.cache: dict[str, dict] = {}  # mint -> evaluation
        self.cache_ttl = 1800  # 30 minutes
        self.recent_verdicts = deque(maxlen=30)
        self.session = requests.Session()
        self.key_index = -1
        self.cooldown_until = 0.0
        self.last_request_time = 0.0
        self.min_request_interval = 4.0  # Pacing between requests (strictly <= 15 RPM)
        self.request_timestamps = deque(maxlen=30)

    def _get_api_keys(self) -> list[str]:
        raw = config.GEMINI_API_KEY.strip()
        keys = [
            k.strip()
            for k in raw.replace(";", ",").split(",")
            if k.strip() and k.strip() != "your_gemini_api_key_here"
        ]
        return keys

    def _select_api_key(self) -> str:
        keys = self._get_api_keys()
        if not keys:
            return ""
        with self.lock:
            self.key_index = (self.key_index + 1) % len(keys)
            return keys[self.key_index]

    def is_configured(self) -> bool:
        return len(self._get_api_keys()) > 0

    def _evaluate_heuristic_consensus(self, candidate: dict, reason: str = "Rate Limit Cooldown") -> dict:
        """
        Deep on-chain heuristic evaluation applied during rate limits or pacing throttling.
        Uses verified RugCheck scores, holder distribution, developer SOL commitment,
        and social links so trading never freezes when free Gemini quotas are reached.
        """
        symbol = candidate.get("symbol", "TOKEN")
        mint = candidate.get("mint", "")
        socials = candidate.get("socials") or {}
        holders = candidate.get("holders") or {}

        rugcheck_score = candidate.get("rugcheck_score", 0)
        top10_pct = holders.get("top10_non_curve_pct", 15.0)
        dev_sol = candidate.get("dev_sol", 0.0)
        has_twitter = bool(socials.get("twitter"))
        has_telegram = bool(socials.get("telegram"))
        is_pre_grad = bool(candidate.get("pre_graduation"))

        # 1. Narrative Heuristic
        narrative_score = 65.0
        if has_twitter:
            narrative_score += 15.0
        if has_telegram:
            narrative_score += 10.0
        if is_pre_grad:
            narrative_score += 10.0
        narrative_score = min(95.0, narrative_score)

        # 2. Safety Heuristic
        safety_score = 70.0
        if rugcheck_score == 0:
            safety_score += 15.0
        elif rugcheck_score < 250:
            safety_score += 5.0
        else:
            safety_score -= 30.0

        if top10_pct < 12.0:
            safety_score += 15.0
        elif top10_pct > 25.0:
            safety_score -= 20.0
        safety_score = max(10.0, min(95.0, safety_score))

        # 3. Composite Alpha
        alpha = round(0.4 * narrative_score + 0.6 * safety_score, 1)
        approved = (alpha >= config.MIN_AGENT_ALPHA_SCORE) and (safety_score >= 60.0)
        action = "BUY" if approved else "SKIP"
        strategy = "RUNNER" if (is_pre_grad or alpha >= config.RUNNER_MIN_ALPHA_SCORE) else "SCALP"

        verdict = {
            "configured": True,
            "model": "local-heuristic-consensus",
            "symbol": symbol,
            "mint": mint,
            "narrative_score": narrative_score,
            "narrative_reasoning": f"Local Heuristic Audit: Twitter={'Yes' if has_twitter else 'No'}, Telegram={'Yes' if has_telegram else 'No'}, Pre-grad={'Yes' if is_pre_grad else 'No'}. ({reason})",
            "safety_score": safety_score,
            "safety_reasoning": f"On-Chain Audit: RugCheck={rugcheck_score}/500, Top10 Non-Curve={top10_pct}%, Dev Buy={dev_sol} SOL.",
            "alpha_score": alpha,
            "suggested_action": action,
            "trade_strategy": strategy,
            "target_tp_pct": 35.0 if strategy == "RUNNER" else config.TAKE_PROFIT_PCT,
            "target_sl_pct": config.STOP_LOSS_PCT,
            "size_multiplier": 1.0,
            "verdict_summary": f"On-Chain Heuristic Consensus ({reason}): Alpha {alpha}/100 -> {action}.",
            "approved": approved,
            "latency_ms": 5,
            "timestamp": time.strftime("%H:%M:%S"),
        }
        return verdict

    def evaluate_candidate(self, candidate: dict) -> dict:
        """
        Evaluates a token candidate through the AI Council.
        Returns evaluation dict with narrative, safety, and alpha consensus scores.
        """
        mint = candidate.get("mint", "")
        symbol = candidate.get("symbol", "TOKEN")

        # 1. Check in-memory cache
        now = time.time()
        with self.lock:
            if mint in self.cache:
                cached, ts = self.cache[mint]
                if now - ts < self.cache_ttl:
                    return cached

        # 2. Check if AI evaluation is enabled and configured
        if not config.AGENT_EVAL_ENABLED or not self.is_configured():
            bypass = {
                "configured": False,
                "symbol": symbol,
                "mint": mint,
                "narrative_score": 0.0,
                "narrative_reasoning": "AI evaluation bypassed (Gemini API key unconfigured or disabled).",
                "safety_score": 0.0,
                "safety_reasoning": "Evaluated via local on-chain & RugCheck safety rules.",
                "alpha_score": 0.0,
                "suggested_action": "BUY",
                "trade_strategy": "RUNNER" if candidate.get("pre_graduation") else "SCALP",
                "target_tp_pct": config.TAKE_PROFIT_PCT,
                "target_sl_pct": config.STOP_LOSS_PCT,
                "size_multiplier": 1.0,
                "verdict_summary": "Passed local heuristic filters (AI Council Bypassed).",
                "approved": True,
                "timestamp": time.strftime("%H:%M:%S"),
            }
            return bypass

        # 3. Check active cooldown and RPM rate limiting
        with self.lock:
            # Check if within 429 cooldown
            if now < self.cooldown_until:
                rem = int(self.cooldown_until - now)
                verdict = self._evaluate_heuristic_consensus(
                    candidate, f"Gemini 429 Cooldown ({rem}s remaining)"
                )
                self.cache[mint] = (verdict, now)
                self.recent_verdicts.appendleft(verdict)
                return verdict

            # Sliding-window RPM throttle: max 12 requests in 60s, min 4s between requests
            recent_reqs = [t for t in self.request_timestamps if now - t < 60.0]
            if len(recent_reqs) >= config.AGENT_MAX_RPM or (now - self.last_request_time < self.min_request_interval):
                verdict = self._evaluate_heuristic_consensus(
                    candidate, "Pacing Throttle (<12 RPM Gate)"
                )
                self.cache[mint] = (verdict, now)
                self.recent_verdicts.appendleft(verdict)
                return verdict

        # 4. Build structured prompt context
        socials = candidate.get("socials") or {}
        holders = candidate.get("holders") or {}

        token_context = {
            "symbol": symbol,
            "name": candidate.get("name", symbol),
            "mint": mint,
            "source": candidate.get("source", "Unknown"),
            "dev_buy_sol": candidate.get("dev_sol", 0.0),
            "liquidity_usd": candidate.get("liquidity_usd", 0.0),
            "market_cap_sol": candidate.get("market_cap_sol", 0.0),
            "curve_progress_pct": candidate.get("curve_progress_pct", 0.0),
            "pre_graduation": candidate.get("pre_graduation", False),
            "volume_5m": candidate.get("volume_5m", 0.0),
            "twitter": socials.get("twitter") or "None",
            "telegram": socials.get("telegram") or "None",
            "website": socials.get("website") or "None",
            "description": socials.get("description") or "None",
            "top1_holder_pct": holders.get("top1_non_curve_pct", 0.0),
            "top10_holders_pct": holders.get("top10_non_curve_pct", 0.0),
            "rugcheck_score": candidate.get("rugcheck_score", 0),
            "rugcheck_risks": candidate.get("rugcheck_risks", []),
        }

        system_instruction = (
            "You are the Solana High-Frequency Meme & Shitcoin AI Council consisting of 3 elite autonomous sub-agents:\n"
            "1. 🧠 Narrative & Virality Scout: Evaluate memecoin ticker, name, description, and cultural meme potential. "
            "Reward funny, viral, culturally timely concepts (Crypto Twitter meta, viral jokes, political satire, iconic characters). "
            "Heavily penalize low-effort generic AI-generated garbage (e.g. random strings, 'Defi Matrix Global'). "
            "Score narrative from 0 to 100.\n"
            "2. 🕵️ Forensic Cabal Auditor: Review developer buy size, top 10 concentration, social profiles, and RugCheck risks. "
            "Look for signs of serial rug-pullers, bundle farms, or fake botted socials. Score safety from 0 to 100. "
            "If safety is critical (<40), you MUST strongly recommend SKIP.\n"
            "3. 📈 Trade Strategist & Orchestrator: Combine narrative power and forensic safety into a unified Alpha Score (0-100). "
            "Assign suggested_action ('BUY', 'SKIP', or 'WATCH'). "
            "Suggest optimal dynamic Take-Profit % (e.g. 20-50%) and Stop-Loss % (e.g. 8-15%) based on expected volatility.\n"
            "4. 🚀 Conviction Tier Classifier: Assign trade_strategy ('RUNNER' or 'SCALP'). "
            "Assign 'RUNNER' for high-conviction viral cultural plays (narrative >= 80, safe distribution, or pre-graduation) to unlock a multi-tier moonbag hold (200%-1000%+). "
            "Assign 'SCALP' for standard fast momentum flips."
        )

        user_prompt = f"Analyze this Solana token breakout candidate and deliver your Council Verdict:\n{json.dumps(token_context, indent=2)}"

        schema = {
            "type": "OBJECT",
            "properties": {
                "symbol": {"type": "STRING"},
                "narrative_score": {"type": "NUMBER", "description": "Score 0-100 on meme quality, humor, virality"},
                "narrative_reasoning": {"type": "STRING", "description": "Concise 1-sentence meme virality analysis"},
                "safety_score": {"type": "NUMBER", "description": "Score 0-100 on dev dump risk and holder distribution"},
                "safety_reasoning": {"type": "STRING", "description": "Concise 1-sentence forensic audit finding"},
                "alpha_score": {"type": "NUMBER", "description": "Composite score 0-100 weighting narrative and safety"},
                "suggested_action": {"type": "STRING", "enum": ["BUY", "SKIP", "WATCH"]},
                "trade_strategy": {"type": "STRING", "enum": ["SCALP", "RUNNER"], "description": "RUNNER for 200%-1000%+ multi-tier moonshots, SCALP for quick flips"},
                "target_tp_pct": {"type": "NUMBER", "description": "Recommended take profit % (e.g. 25.0)"},
                "target_sl_pct": {"type": "NUMBER", "description": "Recommended stop loss % (e.g. 10.0)"},
                "size_multiplier": {"type": "NUMBER", "description": "Position sizing multiplier between 0.5 and 1.5"},
                "verdict_summary": {"type": "STRING", "description": "Punchy executive verdict summary in 15 words or less"},
            },
            "required": [
                "symbol",
                "narrative_score",
                "narrative_reasoning",
                "safety_score",
                "safety_reasoning",
                "alpha_score",
                "suggested_action",
                "trade_strategy",
                "target_tp_pct",
                "target_sl_pct",
                "size_multiplier",
                "verdict_summary",
            ],
        }

        keys = self._get_api_keys()
        if not keys:
            return self._handle_error(candidate, "No Gemini API key available")

        api_key = self._select_api_key()
        with self.lock:
            self.request_timestamps.append(now)
            self.last_request_time = now

        candidate_models = [config.GEMINI_MODEL]
        for fallback in ("gemini-2.5-flash", "gemini-flash-latest"):
            if fallback not in candidate_models:
                candidate_models.append(fallback)

        payload = {
            "system_instruction": {"parts": [{"text": system_instruction}]},
            "contents": [{"parts": [{"text": user_prompt}]}],
            "generationConfig": {
                "response_mime_type": "application/json",
                "response_schema": schema,
                "thinkingConfig": {"thinkingBudget": 0},
                "temperature": 0.2,
                "max_output_tokens": 800,
            },
        }

        res = None
        active_model = config.GEMINI_MODEL
        latency_ms = 0
        last_error = "Unknown error"
        hit_429 = False

        for model_name in candidate_models:
            active_model = model_name
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
            try:
                start_t = time.time()
                res = self.session.post(url, json=payload, timeout=8.0)
                latency_ms = int((time.time() - start_t) * 1000)

                if res.status_code == 200:
                    config.GEMINI_MODEL = model_name
                    break
                elif res.status_code == 429:
                    hit_429 = True
                    last_error = "Gemini API rate limit exceeded (HTTP 429)"
                    with self.lock:
                        self.cooldown_until = time.time() + config.AGENT_COOLDOWN_SECONDS
                    if len(keys) > 1:
                        api_key = self._select_api_key()
                        continue
                    break
                elif res.status_code == 404:
                    last_error = f"Model {model_name} no longer available (HTTP 404)"
                    continue
                else:
                    last_error = f"Gemini API returned HTTP {res.status_code}: {res.text[:120]}"
                    break
            except Exception as e:
                last_error = f"Agent evaluation failed: {e}"
                continue

        if not res or res.status_code != 200:
            if hit_429:
                verdict = self._evaluate_heuristic_consensus(
                    candidate, "Gemini Quota Exceeded (HTTP 429 Fallback)"
                )
                with self.lock:
                    self.cache[mint] = (verdict, now)
                    self.recent_verdicts.appendleft(verdict)
                return verdict
            return self._handle_error(candidate, last_error)

        try:
            data = res.json()
            raw_text = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "{}")
            parsed = json.loads(raw_text)

            alpha = float(parsed.get("alpha_score", 0.0))
            action = parsed.get("suggested_action", "SKIP").upper()
            approved = (alpha >= config.MIN_AGENT_ALPHA_SCORE) and (action == "BUY")

            strategy = str(parsed.get("trade_strategy", "SCALP")).upper()
            if strategy not in ("SCALP", "RUNNER"):
                strategy = "RUNNER" if alpha >= config.RUNNER_MIN_ALPHA_SCORE else "SCALP"
            if candidate.get("pre_graduation"):
                strategy = "RUNNER"

            verdict = {
                "configured": True,
                "model": active_model,
                "symbol": parsed.get("symbol", symbol),
                "mint": mint,
                "narrative_score": round(float(parsed.get("narrative_score", 0.0)), 1),
                "narrative_reasoning": parsed.get("narrative_reasoning", ""),
                "safety_score": round(float(parsed.get("safety_score", 0.0)), 1),
                "safety_reasoning": parsed.get("safety_reasoning", ""),
                "alpha_score": round(alpha, 1),
                "suggested_action": action,
                "trade_strategy": strategy,
                "target_tp_pct": round(float(parsed.get("target_tp_pct", config.TAKE_PROFIT_PCT)), 1),
                "target_sl_pct": round(float(parsed.get("target_sl_pct", config.STOP_LOSS_PCT)), 1),
                "size_multiplier": round(float(parsed.get("size_multiplier", 1.0)), 2),
                "verdict_summary": parsed.get("verdict_summary", ""),
                "approved": approved,
                "latency_ms": latency_ms,
                "timestamp": time.strftime("%H:%M:%S"),
            }

            with self.lock:
                self.cache[mint] = (verdict, now)
                self.recent_verdicts.appendleft(verdict)

            return verdict

        except Exception as e:
            return self._handle_error(candidate, f"Response parsing failed: {e}")

    def _handle_error(self, candidate: dict, err_msg: str) -> dict:
        """Handles API errors with configured fail-open or fail-closed policy."""
        symbol = candidate.get("symbol", "TOKEN")
        mint = candidate.get("mint", "")
        approved = config.AGENT_FAIL_OPEN

        verdict = {
            "configured": True,
            "model": config.GEMINI_MODEL,
            "symbol": symbol,
            "mint": mint,
            "narrative_score": 50.0,
            "narrative_reasoning": f"Evaluation error: {err_msg}",
            "safety_score": 50.0,
            "safety_reasoning": "Fallback safety applied due to API error.",
            "alpha_score": 50.0 if not approved else config.MIN_AGENT_ALPHA_SCORE,
            "suggested_action": "BUY" if approved else "SKIP",
            "trade_strategy": "RUNNER" if candidate.get("pre_graduation") else "SCALP",
            "target_tp_pct": config.TAKE_PROFIT_PCT,
            "target_sl_pct": config.STOP_LOSS_PCT,
            "size_multiplier": 1.0,
            "verdict_summary": f"Fallback applied ({err_msg[:40]}...)",
            "approved": approved,
            "timestamp": time.strftime("%H:%M:%S"),
        }

        with self.lock:
            self.recent_verdicts.appendleft(verdict)

        return verdict

    def get_recent_verdicts(self) -> list[dict]:
        with self.lock:
            return list(self.recent_verdicts)


# Global singleton instance
agent_council = AgentCouncil()
