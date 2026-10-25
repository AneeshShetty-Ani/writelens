import json

import pytest
import requests

import ai
from ai import AIError, DailyLimit, Provider, ask, load_config, model_label, models_to_try, parse_json


class FakeResponse:
    def __init__(self, status: int, payload: dict | None = None, text: str = ""):
        self.status_code, self._payload, self.text = status, payload, text

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


def reply(content, model: str = "") -> FakeResponse:
    content = content if isinstance(content, str) else json.dumps(content)
    return FakeResponse(200, {"model": model, "choices": [{"message": {"content": content}}]})


def accept_any(data: dict):
    return data.get("answer")


@pytest.fixture
def calls(monkeypatch):
    """Record (provider, model) per request; answer from a queue of responses. Engine state starts fresh."""
    log, queue = [], []

    def fake(provider, model, messages, max_tokens):
        log.append((provider.key, model))
        result = queue.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(ai, "ask_model", fake)
    monkeypatch.setattr(ai, "openrouter_free_models", lambda: ["a:free", "b:free", "c:free"])
    monkeypatch.setattr(ai, "_refused", {})
    monkeypatch.setattr(ai, "_last_worked", {})
    monkeypatch.setattr(ai, "_health", {"busy_at": 0.0, "failures": 0, "refused": False, "key_checked_at": 1e18})
    return log, queue


def test_config_needs_a_key():
    assert load_config({}) == ([], ai.DEFAULT_DAILY_LIMIT)
    providers, limit = load_config({"ai": {"openrouter_key": " ", "groq_key": "g", "daily_limit": "5"}})
    assert [p.key for p in providers] == ["groq"] and limit == 5


def test_config_keeps_provider_order_and_models():
    providers, _ = load_config({"ai": {"groq_key": "g", "openrouter_key": "o", "openrouter_models": ["x:free"]}})
    assert [(p.key, p.models) for p in providers] == [("openrouter", ["x:free"]), ("groq", [])]


def test_parse_json_allows_fences_and_chatter():
    assert parse_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert parse_json('Sure! Here it is: {"a": [1, 2]} Hope that helps.') == {"a": [1, 2]}
    assert parse_json("no json here") is None and parse_json("[1, 2]") is None


def test_free_models_from_listing():
    listing = [{"id": "big:free", "context_length": 128000, "pricing": {"prompt": "0"}},
               {"id": "paid", "context_length": 999999, "pricing": {"prompt": "0.001"}},
               {"id": "small:free", "context_length": 8000, "pricing": {"prompt": "0"}}]
    assert ai.free_openrouter_models(listing) == ["big:free", "small:free"]


def test_preferred_models_first_and_gone_ones_skipped():
    preferred = ai.PREFERRED_MODELS["openrouter"]
    available = ["new:free", preferred[1], "other:free"]
    assert models_to_try(Provider("openrouter", "k"), available) == [preferred[1], "new:free", "other:free"]
    assert models_to_try(Provider("openrouter", "k"), None) == preferred  # live list unavailable
    assert models_to_try(Provider("groq", "k", ["mine"]), available) == ["mine"]


def test_falls_back_to_the_next_model(calls):
    log, queue = calls
    queue += [FakeResponse(429, text="busy"), requests.Timeout(), reply({"answer": "Yes."}, "b:free")]
    answer = ask([Provider("openrouter", "k", ["a:free", "x:free", "b:free"])], "task", accept_any)
    assert answer.data == "Yes." and answer.provider == "OpenRouter" and answer.model == "b:free"
    assert [m for _, m in log] == ["a:free", "x:free", "b:free"]


def test_a_reply_that_fails_the_check_tries_the_next_model(calls):
    _, queue = calls
    queue += [reply("not json"), reply({"other": 1}), reply({"answer": "Good."})]
    assert ask([Provider("openrouter", "k")], "task", accept_any).data == "Good."


def test_bad_key_or_daily_limit_moves_to_the_next_provider(calls):
    log, queue = calls
    queue += [FakeResponse(401), reply({"answer": "From Groq."})]
    assert ask([Provider("openrouter", "k"), Provider("groq", "g")], "t", accept_any).provider == "Groq"
    assert log == [("openrouter", "a:free"), ("groq", "llama-3.3-70b-versatile")]
    log.clear()
    queue += [FakeResponse(429, text="Rate limit exceeded: free-models-per-day"), reply({"answer": "Gemini."})]
    assert ask([Provider("openrouter", "k"), Provider("gemini", "m")], "t", accept_any).data == "Gemini."
    assert [p for p, _ in log] == ["openrouter", "gemini"]


def test_models_that_refuse_the_app_are_skipped_next_time(calls):
    log, queue = calls
    queue += [FakeResponse(403, text="only available on agentic harnesses"),
              FakeResponse(404, text="No endpoints matching your data policy"), reply({"answer": "Hi."})]
    assert ask([Provider("openrouter", "k")], "t", accept_any).model == "c:free"  # a 403 is the model, not the key
    log.clear()
    queue.append(reply({"answer": "Again."}))
    ask([Provider("openrouter", "k")], "t", accept_any)
    assert log == [("openrouter", "c:free")]


def test_the_model_that_answered_last_goes_first(calls):
    log, queue = calls
    queue += [FakeResponse(429, text="busy"), reply({"answer": "From b."})]
    ask([Provider("openrouter", "k")], "t", accept_any)
    log.clear()
    queue.append(reply({"answer": "b again."}))
    ask([Provider("openrouter", "k")], "t", accept_any)
    assert log == [("openrouter", "b:free")]


def test_status_follows_what_happened(calls):
    _, queue = calls
    providers = [Provider("openrouter", "k")]
    assert ai.status([], 5) == "offline"
    assert ai.status(providers, 5) == "online"
    assert ai.status(providers, 0) == "maintenance"  # this user's daily AI checks are used up
    queue += [FakeResponse(429, text="busy")] * 3
    with pytest.raises(AIError, match="busy"):
        ask(providers, "t", accept_any)
    assert ai.status(providers, 5) == "maintenance"
    queue.append(reply({"answer": "ok"}))
    ask(providers, "t", accept_any)
    assert ai.status(providers, 5) == "online"
    queue += [FakeResponse(500)] * 3
    with pytest.raises(AIError, match="usable answer"):
        ask(providers, "t", accept_any)
    assert ai.status(providers, 5) == "stopped"
    queue.append(FakeResponse(401))
    with pytest.raises(AIError, match="refused"):
        ask(providers, "t", accept_any)
    assert ai.status(providers, 5) == "stopped"


def test_key_check_marks_a_refused_key(calls, monkeypatch):
    monkeypatch.setitem(ai._health, "key_checked_at", 0.0)
    monkeypatch.setattr(ai.requests, "get", lambda *a, **k: FakeResponse(401))
    assert ai.status([Provider("openrouter", "bad")], 5) == "stopped"


def test_no_providers_is_an_error():
    with pytest.raises(AIError):
        ask([], "t", accept_any)


def test_model_label():
    assert model_label("meta-llama/llama-3.3-70b-instruct:free") == "llama-3.3-70b-instruct (free)"
    assert model_label("gemini-flash-latest") == "gemini-flash-latest"


def test_daily_limit_per_user_and_day():
    limit = DailyLimit(2)
    limit.use("Ana", "2026-10-25")
    limit.use("ana", "2026-10-25")
    assert limit.remaining("ANA", "2026-10-25") == 0 and limit.remaining("bo", "2026-10-25") == 2
    limit.use("bo", "2026-10-26")
    assert limit.remaining("ana", "2026-10-26") == 2  # a new day starts again
