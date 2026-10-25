"""The optional AI engine behind the tools: free models from several providers, tried in order until one
answers, plus the status shown under the username.

Every provider here speaks the same OpenAI-style chat API, so one request function serves them all.
Keys come from the `[ai]` secrets; with no key the engine is off and every tool runs offline. OpenRouter's
free models come and go, so its list is read from OpenRouter itself (cached) and the preferred ones are
tried first. The tools ask for JSON and check it (see ai_tasks.py); an answer that fails the check counts
as a failure and the next model is tried.
"""

import json
import re
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable

import requests

# key -> (name shown to users, chat endpoint)
PROVIDERS = {
    "openrouter": ("OpenRouter", "https://openrouter.ai/api/v1/chat/completions"),
    "gemini": ("Google Gemini", "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"),
    "groq": ("Groq", "https://api.groq.com/openai/v1/chat/completions"),
}
# Tried first when they're on offer; any other free OpenRouter model follows. Override with
# `<provider>_models = [...]` in the secrets.
PREFERRED_MODELS = {
    "openrouter": ["google/gemma-4-31b-it:free", "google/gemma-4-26b-a4b-it:free",
                   "nvidia/nemotron-3-super-120b-a12b:free", "dots-studio/dots-3-note-preview:free"],
    "gemini": ["gemini-flash-latest"],
    "groq": ["llama-3.3-70b-versatile"],
}
OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"
OPENROUTER_KEY_URL = "https://openrouter.ai/api/v1/key"
OPENROUTER_HEADERS = {"HTTP-Referer": "https://writelens.streamlit.app", "X-Title": "WriteLens"}
MODEL_LIST_TTL = 6 * 3600
MAX_OPENROUTER_MODELS = 8
# A model that refuses this app (403: only for agent apps, 404: blocked by the account's privacy
# settings) is skipped for a while instead of being asked again every time.
SKIP_SECONDS = 3600
DEFAULT_DAILY_LIMIT = 30  # AI checks per user per day; the free models' limit is shared by everyone
REASONING_TOKENS = 1500
TIMEOUT = (5, 60)
DEADLINE_SECONDS = 90  # give up on further models after this long
KEY_CHECK_SECONDS = 600
BUSY_SECONDS = 600  # how long "Maintenance" shows after the models were busy
STOP_AFTER_FAILURES = 3  # this many failed requests in a row (none busy) shows "Stopped"

SYSTEM_PROMPT = """You are the AI engine inside WriteLens, a writing-feedback app for students.
Follow the task exactly. Reply with one JSON object only: no Markdown fences and no text before or after it.
Never invent facts, statistics, quotes or sources. When asked to quote the text, copy the words exactly."""

# engine status -> (label, what it means)
STATUSES = {
    "online": ("Online", "AI is working; the tools use it automatically."),
    "maintenance": ("Maintenance", "The free AI models are busy or today's AI limit is used up, so the tools "
                                   "run offline for now."),
    "stopped": ("Stopped", "The AI isn't answering (the key was refused or every model failed), so the tools "
                           "run offline."),
    "offline": ("Offline", "No AI is set up, so every tool runs offline."),
}


class AIError(Exception):
    pass


@dataclass
class Answer:
    data: Any  # what the caller's `accept` made of the reply
    provider: str  # name shown to users
    model: str


@dataclass
class Provider:
    key: str
    api_key: str
    models: list[str] = field(default_factory=list)  # empty for OpenRouter = discover free ones


def load_config(secrets) -> tuple[list[Provider], int]:
    """(providers in the order to try, AI checks per user per day) from the `[ai]` secrets section."""
    try:
        ai = secrets["ai"]
    except Exception:
        return [], DEFAULT_DAILY_LIMIT
    providers = []
    for key in PROVIDERS:
        api_key = str(ai.get(f"{key}_key", "")).strip()
        if api_key:
            providers.append(Provider(key, api_key, [str(m) for m in ai.get(f"{key}_models", [])]))
    try:
        limit = max(int(ai.get("daily_limit", DEFAULT_DAILY_LIMIT)), 1)
    except (TypeError, ValueError):
        limit = DEFAULT_DAILY_LIMIT
    return providers, limit


# ---- which models to try ----------------------------------------------------------

_model_cache: dict[str, tuple[float, list[str]]] = {}
_refused: dict[str, float] = {}  # model -> when it refused
_last_worked: dict[str, str] = {}  # provider -> the model that answered last, tried first next time


def refused_recently(model: str) -> bool:
    return time.time() - _refused.get(model, 0) < SKIP_SECONDS


def free_openrouter_models(listing: list[dict]) -> list[str]:
    """Ids of the free models in OpenRouter's /models listing, biggest context window first."""
    free = [m for m in listing if str(m.get("id", "")).endswith(":free")
            and str((m.get("pricing") or {}).get("prompt", "0")) in ("0", "0.0")]
    free.sort(key=lambda m: -int(m.get("context_length") or 0))
    return [m["id"] for m in free]


def openrouter_free_models() -> list[str] | None:
    """The free models on offer now (cached), or None if OpenRouter couldn't be asked."""
    cached = _model_cache.get("openrouter")
    if cached and time.time() - cached[0] < MODEL_LIST_TTL:
        return cached[1]
    try:
        resp = requests.get(OPENROUTER_MODELS_URL, timeout=TIMEOUT)
        resp.raise_for_status()
        models = free_openrouter_models(resp.json().get("data", []))
    except (requests.RequestException, ValueError, AttributeError):
        return None
    _model_cache["openrouter"] = (time.time(), models)
    return models


def models_to_try(provider: Provider, available: list[str] | None = None) -> list[str]:
    """The provider's own model list if given; for OpenRouter otherwise the last model that worked, then the
    preferred free models still on offer, then other free ones. `available` is None when the live list
    couldn't be read."""
    if provider.models:
        return provider.models
    preferred = PREFERRED_MODELS[provider.key]
    if provider.key != "openrouter" or available is None:
        return preferred
    last = [_last_worked["openrouter"]] if _last_worked.get("openrouter") in available else []
    ordered = last + [m for m in preferred if m in available] + [m for m in available if m not in preferred]
    return [m for m in dict.fromkeys(ordered) if not refused_recently(m)][:MAX_OPENROUTER_MODELS]


# ---- engine status ------------------------------------------------------------------

_health = {"busy_at": 0.0, "failures": 0, "refused": False, "key_checked_at": 0.0}
_health_lock = threading.Lock()


def note(outcome: str) -> None:
    """Record how a request went: "ok", "busy", "refused" or "failed"."""
    with _health_lock:
        if outcome == "ok":
            _health.update(busy_at=0.0, failures=0, refused=False)
        elif outcome == "busy":
            _health["busy_at"] = time.time()
        elif outcome == "refused":
            _health["refused"] = True
        else:
            _health["failures"] += 1


def check_key(provider: Provider) -> None:
    """Ask OpenRouter whether the key works (free, and not counted as a model request); every 10 minutes."""
    if provider.key != "openrouter" or time.time() - _health["key_checked_at"] < KEY_CHECK_SECONDS:
        return
    _health["key_checked_at"] = time.time()
    try:
        resp = requests.get(OPENROUTER_KEY_URL, headers={"Authorization": f"Bearer {provider.api_key}"},
                            timeout=TIMEOUT)
    except requests.RequestException:
        return  # no network: leave the status as it was
    with _health_lock:
        _health["refused"] = resp.status_code in (401, 403)


def status(providers: list[Provider], left_today: int) -> str:
    """One of STATUSES."""
    if not providers:
        return "offline"
    check_key(providers[0])
    if _health["refused"] or _health["failures"] >= STOP_AFTER_FAILURES:
        return "stopped"
    if left_today <= 0 or time.time() - _health["busy_at"] < BUSY_SECONDS:
        return "maintenance"
    return "online"


# ---- asking -------------------------------------------------------------------------

def ask_model(provider: Provider, model: str, messages: list[dict], max_tokens: int) -> requests.Response:
    headers = {"Authorization": f"Bearer {provider.api_key}"}
    body = {"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": 0.2}
    if provider.key == "openrouter":
        headers.update(OPENROUTER_HEADERS)
        # Many free models "think" before answering, and the thinking counts towards max_tokens: without
        # this they can spend it all thinking and never write the answer. Room is left for models that
        # think anyway.
        body.update(reasoning={"enabled": False}, max_tokens=max_tokens + REASONING_TOKENS)
    return requests.post(PROVIDERS[provider.key][1], headers=headers, timeout=TIMEOUT, json=body)


def answer_text(resp: requests.Response) -> str:
    try:
        content = resp.json()["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError):
        return ""
    return (content or "").strip()


def parse_json(text: str) -> dict | None:
    """The JSON object in a model's reply, allowing for ```json fences or a sentence around it."""
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < start:
        return None
    try:
        data = json.loads(text[start:end + 1])
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def ask(providers: list[Provider], task: str, accept: Callable[[dict], Any], max_tokens: int = 1200) -> Answer:
    """Send `task` to each provider's models in order. `accept` turns the reply's JSON into the result, or
    returns None to reject it (then the next model is tried). A wrong key or a used-up daily limit skips
    the rest of that provider."""
    if not providers:
        raise AIError("No AI is set up.")
    messages = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": task}]
    started, busy = time.monotonic(), False
    all_refused = True
    for provider in providers:
        available = openrouter_free_models() if provider.key == "openrouter" and not provider.models else None
        refused = False
        for model in models_to_try(provider, available):
            if time.monotonic() - started > DEADLINE_SECONDS:
                break
            try:
                resp = ask_model(provider, model, messages, max_tokens)
            except requests.RequestException:
                note("failed")
                continue
            error = resp.text.lower() if resp.status_code != 200 else ""
            if resp.status_code == 200:
                parsed = parse_json(answer_text(resp))
                result = accept(parsed) if parsed is not None else None
                if result is not None:
                    note("ok")
                    _last_worked[provider.key] = model
                    try:
                        model = resp.json().get("model") or model
                    except ValueError:
                        pass
                    return Answer(result, PROVIDERS[provider.key][0], model)
                note("failed")
            elif resp.status_code in (401, 402):
                refused = True
                break
            elif resp.status_code == 429:
                busy = True
                note("busy")
                if "per-day" in error.replace(" ", "-"):
                    break
            else:
                if resp.status_code in (403, 404):
                    _refused[model] = time.time()
                note("failed")
        all_refused = all_refused and refused
    if all_refused:
        note("refused")
        raise AIError("The AI key was refused.")
    raise AIError("The free AI models are busy right now." if busy else "No AI model gave a usable answer.")


def model_label(model: str) -> str:
    """"meta-llama/llama-3.3-70b-instruct:free" -> "llama-3.3-70b-instruct (free)"."""
    name = model.rsplit("/", 1)[-1]
    return name.removesuffix(":free") + " (free)" if name.endswith(":free") else name


# ---- daily limit per user -------------------------------------------------------------

class DailyLimit:
    """AI checks per user per day, kept in server memory (a restart starts the count again)."""

    def __init__(self, limit: int):
        self.limit = limit
        self._used: dict[tuple[str, str], int] = {}
        self._lock = threading.Lock()

    def remaining(self, user: str, day: str) -> int:
        with self._lock:
            return max(self.limit - self._used.get((user.lower(), day), 0), 0)

    def use(self, user: str, day: str) -> None:
        with self._lock:
            # drop earlier days so the dictionary doesn't grow forever
            for key in [k for k in self._used if k[1] != day]:
                del self._used[key]
            self._used[(user.lower(), day)] = self._used.get((user.lower(), day), 0) + 1
