"""Server-side policy for model-backed investigations: who pays, what is reused, how much runs at once.

- Server key: default model only, shared result cache, an estimated-spend cap, a per-client
  hourly limit on fresh runs, and a global concurrency limit.
- BYOK: the user's key is used for that one request only. It is never stored, logged, cached
  or returned. Runs are always fresh, are not written to the shared cache, and do not count
  against the server's budget, but they share the concurrency limit.
"""
from __future__ import annotations

import json
import os
import threading
import time
from collections import defaultdict, deque
from pathlib import Path

from investigation.llm.agents import PROMPT_VERSION, run_agents
from investigation.llm.provider import (PLATFORM, Ledger, Provider, ProviderError, server_api_key, server_key_configured,
                                        server_model,
                                        validate_model)
from phase0.observe import Case

MAX_CONCURRENT = int(os.environ.get("BTR_MAX_CONCURRENT", "2"))
FRESH_RUNS_PER_HOUR = int(os.environ.get("BTR_FRESH_RUNS_PER_HOUR", "2"))
SERVER_BUDGET_USD = float(os.environ.get("BTR_SERVER_BUDGET_USD", "0.20"))


class InferencePolicy:
    def __init__(self, cache_dir: Path, runtime_dir: Path, provider_factory=Provider):
        self.cache_dir = cache_dir
        self.ledger = Ledger.load(runtime_dir / "ledger.json", SERVER_BUDGET_USD)
        self.slots = threading.BoundedSemaphore(MAX_CONCURRENT)
        self.recent: dict[str, deque] = defaultdict(deque)
        self.lock = threading.Lock()
        self.provider_factory = provider_factory

    # --- cache --------------------------------------------------------------------------------

    def _cache_path(self, match_id: str, incident_id: str, model: str) -> Path:
        return self.cache_dir / f"{match_id}_{incident_id}_{model}_{PROMPT_VERSION}.json"

    def cached(self, match_id: str, incident_id: str, model: str | None = None) -> dict | None:
        path = self._cache_path(match_id, incident_id, model or server_model())
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None

    def _store(self, match_id: str, incident_id: str, out: dict) -> None:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._cache_path(match_id, incident_id, out["model"]).write_text(json.dumps(out), encoding="utf-8")

    # --- limits -------------------------------------------------------------------------------

    def _allow_fresh(self, client_id: str) -> None:
        now = time.time()
        with self.lock:
            q = self.recent[client_id]
            while q and now - q[0] > 3600:
                q.popleft()
            if len(q) >= FRESH_RUNS_PER_HOUR:
                raise ProviderError("client_limit", "You've started many fresh runs this hour. Cached results stay "
                                    "available, or add your own key.", 429, True)
            q.append(now)

    # --- entry point --------------------------------------------------------------------------

    def investigate(self, case: Case, *, client_id: str, fresh: bool, byok_key: str | None,
                    byok_model: str | None) -> dict:
        if byok_key:
            provider = self.provider_factory(byok_key, validate_model(byok_model), "byok")
        else:
            if byok_model and validate_model(byok_model) != server_model():
                raise ProviderError("byok_required", "Other models need your own API key.", 400)
            if not fresh:
                hit = self.cached(case.case_id, case.incident_id)
                if hit is not None:
                    return hit | {"cached": True}
            if not server_key_configured():
                raise ProviderError("not_configured", "No model key is configured on this server. Add your own key "
                                    "or run the deterministic investigation.", 503)
            self.ledger.check()
            self._allow_fresh(client_id)
            provider = self.provider_factory(server_api_key(), server_model(), "server")

        if not self.slots.acquire(timeout=2):
            raise ProviderError("busy", "Other investigations are running right now. Try again in a few seconds.", 429, True)
        try:
            out = run_agents(case, provider)
        finally:
            self.slots.release()
            if provider.source == "server":
                self.ledger.record(provider.usage)
        out |= {"cached": False, "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "prompt_version": PROMPT_VERSION}
        if provider.source == "server":
            self._store(case.case_id, case.incident_id, out)
        return out

    def status(self) -> dict:
        return {"server_key_configured": server_key_configured(), "default_model": server_model(), "platform": PLATFORM,
                "budget": self.ledger.to_dict(), "max_concurrent": MAX_CONCURRENT,
                "fresh_runs_per_hour": FRESH_RUNS_PER_HOUR}
