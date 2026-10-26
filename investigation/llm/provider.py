"""Model provider: one place where API keys, model choice, errors, usage and spend are handled.

Keys are never logged, returned, or persisted. The server key comes from the environment; a
user's own key (BYOK) arrives per request and lives only for that request's Provider object.
"""
from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

import anthropic

# Explicit allow-list (BYOM). Prices are Anthropic list prices per million tokens, used only to
# *estimate* spend; the provider's own billing is authoritative.
SUPPORTED_MODELS = {
    "claude-haiku-5-5": {"label": "Claude Haiku 5.5", "input": 0.10, "output": 0.50, "effort": True},
    "claude-sonnet-5-5": {"label": "Claude Sonnet 5.5", "input": 2.00, "output": 10.00, "effort": True},
    # Fallback for a Microsoft Foundry catalogue without Haiku 5.5. It rejects the effort setting.
    "claude-haiku-4-5": {"label": "Claude Haiku 4.5", "input": 1.00, "output": 5.00, "effort": False},
}
DEFAULT_MODEL = "claude-haiku-5-5"
# Where the *server* key's requests go: "anthropic" (Claude API) or "foundry" (Claude on Microsoft
# Foundry). Bring-your-own-key always uses the Claude API.
PLATFORM = os.environ.get("BTR_PROVIDER", "anthropic")
# Pinned so a stray ANTHROPIC_BASE_URL in the environment can never redirect keys elsewhere.
API_BASE = os.environ.get("BTR_ANTHROPIC_BASE_URL", "https://api.anthropic.com")
REQUEST_TIMEOUT_S = 60.0
SDK_RETRIES = 2  # SDK retries 408/409/429/5xx and connection errors with backoff, honouring retry-after


class ProviderError(Exception):
    """A provider failure the API and UI can explain. Messages never contain credentials."""

    def __init__(self, code: str, message: str, status: int = 502, retryable: bool = False):
        super().__init__(message)
        self.code, self.message, self.status, self.retryable = code, message, status, retryable

    def to_dict(self) -> dict:
        return {"code": self.code, "message": self.message, "retryable": self.retryable}


@dataclass
class Usage:
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cost_usd_estimate: float = 0.0

    def add(self, usage, model: str) -> float:
        price = SUPPORTED_MODELS[model]
        inp = getattr(usage, "input_tokens", 0) or 0
        out = getattr(usage, "output_tokens", 0) or 0
        cached = getattr(usage, "cache_read_input_tokens", 0) or 0
        cost = (inp * price["input"] + cached * price["input"] * 0.1 + out * price["output"]) / 1e6
        self.calls += 1
        self.input_tokens += inp
        self.output_tokens += out
        self.cache_read_tokens += cached
        self.cost_usd_estimate += cost
        return cost

    def to_dict(self) -> dict:
        return asdict(self) | {"cost_usd_estimate": round(self.cost_usd_estimate, 5),
                               "cost_basis": "estimated from list prices and provider-reported tokens"}


def load_dotenv(path: Path) -> None:
    """Minimal .env loader: sets variables that are not already set. Never prints values."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def server_api_key() -> str | None:
    if PLATFORM == "foundry":
        return os.environ.get("ANTHROPIC_FOUNDRY_API_KEY")
    return os.environ.get("ANTHROPIC_API_KEY")


def server_key_configured() -> bool:
    if PLATFORM == "foundry":
        return bool(server_api_key() and (os.environ.get("ANTHROPIC_FOUNDRY_RESOURCE") or os.environ.get("ANTHROPIC_FOUNDRY_BASE_URL")))
    return bool(server_api_key())


def server_model() -> str:
    """The model the server key uses (BTR_MODEL, default Claude Haiku 5.5)."""
    return validate_model(None)


def validate_model(model: str | None) -> str:
    model = model or os.environ.get("BTR_MODEL") or DEFAULT_MODEL
    if model not in SUPPORTED_MODELS:
        raise ProviderError("unsupported_model", f"Model {model!r} is not supported. Choose one of: "
                            + ", ".join(SUPPORTED_MODELS), status=400)
    return model


def _map_error(exc: Exception) -> ProviderError:
    if isinstance(exc, anthropic.AuthenticationError):
        return ProviderError("auth", "The API key was rejected by Anthropic.", 401)
    if isinstance(exc, anthropic.PermissionDeniedError):
        return ProviderError("permission", "This API key is not allowed to use the selected model.", 403)
    if isinstance(exc, anthropic.NotFoundError):
        return ProviderError("model_unavailable", "The selected model is not available to this key.", 404)
    if isinstance(exc, anthropic.RateLimitError):
        return ProviderError("rate_limited", "Anthropic is rate-limiting this key. Try again in a minute.", 429, True)
    if isinstance(exc, anthropic.BadRequestError):
        if "credit balance" in (exc.message or "").lower():
            return ProviderError("credits", "This key has run out of API credits.", 402)
        return ProviderError("bad_request", "The model request was rejected as invalid.", 502)
    if isinstance(exc, (anthropic.OverloadedError, anthropic.ServiceUnavailableError, anthropic.InternalServerError)):
        return ProviderError("provider_unavailable", "Anthropic is temporarily unavailable.", 503, True)
    if isinstance(exc, anthropic.APITimeoutError):
        return ProviderError("timeout", "The model did not respond in time.", 504, True)
    if isinstance(exc, anthropic.APIConnectionError):
        return ProviderError("connection", "Could not reach Anthropic.", 503, True)
    if isinstance(exc, anthropic.APIStatusError):
        return ProviderError("provider_error", f"Anthropic returned status {exc.status_code}.", 502, exc.status_code >= 500)
    raise exc


class Provider:
    def __init__(self, api_key: str | None, model: str | None = None, source: str = "server", client=None,
                 platform: str | None = None):
        self.model = validate_model(model)          # allow-listed id, used for pricing and caching
        self.source = source                        # "server" | "byok"
        self.platform = platform or (PLATFORM if source == "server" else "anthropic")
        self.api_model = self.model                 # what is sent to the provider
        if client is None:
            if not api_key:
                raise ProviderError("not_configured", "No API key is configured on the server.", 503)
            if self.platform == "foundry":
                # Foundry routes by deployment name; name the deployment after the model id, or set this.
                self.api_model = os.environ.get("BTR_FOUNDRY_DEPLOYMENT") or self.model
                client = anthropic.AnthropicFoundry(api_key=api_key, max_retries=SDK_RETRIES, timeout=REQUEST_TIMEOUT_S)
            else:
                client = anthropic.Anthropic(api_key=api_key, base_url=API_BASE, max_retries=SDK_RETRIES,
                                             timeout=REQUEST_TIMEOUT_S)
        self.client = client
        self.usage = Usage()
        self.last_call_cost = 0.0

    def create(self, **kwargs):
        if not SUPPORTED_MODELS[self.model]["effort"]:
            kwargs.pop("output_config", None)
        try:
            resp = self.client.messages.create(model=self.api_model, **kwargs)
        except anthropic.APIError as exc:
            raise _map_error(exc) from None
        self.last_call_cost = self.usage.add(resp.usage, self.model)
        if resp.stop_reason == "refusal":
            raise ProviderError("refusal", "The model declined this request.", 502)
        return resp

    def test(self) -> dict:
        """Cheapest possible credential check: look up the model (no tokens are generated)."""
        try:
            info = self.client.models.retrieve(self.model)
        except anthropic.APIError as exc:
            raise _map_error(exc) from None
        return {"ok": True, "model": self.model, "display_name": getattr(info, "display_name", self.model)}


@dataclass
class Ledger:
    """Estimated spend of the *server* key, persisted so restarts don't reset the guard."""

    path: Path
    cap_usd: float
    spent_usd: float = 0.0
    calls: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    @classmethod
    def load(cls, path: Path, cap_usd: float) -> "Ledger":
        ledger = cls(path, cap_usd)
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            ledger.spent_usd, ledger.calls = data.get("spent_usd", 0.0), data.get("calls", 0)
        return ledger

    def check(self) -> None:
        if self.spent_usd >= self.cap_usd:
            raise ProviderError("budget_exhausted",
                                "The demo's shared model budget is used up. Cached results and your own key still work.", 402)

    def record(self, usage: Usage) -> None:
        with self._lock:
            self.spent_usd += usage.cost_usd_estimate
            self.calls += usage.calls
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps({"spent_usd": round(self.spent_usd, 6), "calls": self.calls,
                                             "updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}))

    def to_dict(self) -> dict:
        return {"cap_usd": self.cap_usd, "spent_usd_estimate": round(self.spent_usd, 4),
                "remaining_usd_estimate": round(max(self.cap_usd - self.spent_usd, 0), 4)}
