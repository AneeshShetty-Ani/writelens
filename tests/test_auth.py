from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest
import requests
from streamlit.testing.v1 import AppTest

import auth

APP = str(Path(__file__).parent.parent / "app.py")
CFG = {
    "client_id": "cid",
    "client_secret": "csecret",
    "redirect_uri": "http://localhost:8501",
    "allowed_users": ["Alice", " bob "],
}


class FakeResponse:
    def __init__(self, payload, status=200):
        self.payload, self.status_code = payload, status

    def json(self):
        return self.payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code))


# ---- unit tests -------------------------------------------------------------

def test_authorize_url_has_no_scope_and_includes_state():
    q = parse_qs(urlparse(auth.authorize_url(CFG, "abc")).query)
    assert q["client_id"] == ["cid"] and q["state"] == ["abc"]
    assert "scope" not in q
    assert "client_secret" not in q


def test_state_is_single_use():
    s = auth.new_state()
    assert auth.consume_state(s) is True
    assert auth.consume_state(s) is False


def test_unknown_missing_and_expired_states_rejected(monkeypatch):
    assert auth.consume_state("never-issued") is False
    assert auth.consume_state(None) is False
    s = auth.new_state()
    real_time = auth.time.time
    monkeypatch.setattr(auth.time, "time", lambda: real_time() + auth.STATE_TTL_SECONDS + 1)
    assert auth.consume_state(s) is False


def test_allow_list_is_case_insensitive_and_trimmed():
    assert auth.is_allowed("alice", CFG["allowed_users"])
    assert auth.is_allowed("BOB", CFG["allowed_users"])
    assert not auth.is_allowed("mallory", CFG["allowed_users"])
    assert not auth.is_allowed("anyone", [])


def test_exchange_code_success(monkeypatch):
    sent = {}

    def fake_post(url, data, headers, timeout):
        sent.update(data)
        return FakeResponse({"access_token": "tok"})

    monkeypatch.setattr(auth.requests, "post", fake_post)
    assert auth.exchange_code(CFG, "code123") == "tok"
    assert sent["client_secret"] == "csecret" and sent["code"] == "code123"


def test_exchange_code_rejected(monkeypatch):
    monkeypatch.setattr(auth.requests, "post", lambda *a, **k: FakeResponse({"error_description": "bad code"}))
    with pytest.raises(auth.AuthError, match="bad code"):
        auth.exchange_code(CFG, "x")


def test_exchange_code_network_error(monkeypatch):
    def boom(*a, **k):
        raise requests.ConnectionError()

    monkeypatch.setattr(auth.requests, "post", boom)
    with pytest.raises(auth.AuthError, match="reach GitHub"):
        auth.exchange_code(CFG, "x")


def test_fetch_username(monkeypatch):
    monkeypatch.setattr(auth.requests, "get", lambda *a, **k: FakeResponse({"login": "alice"}))
    assert auth.fetch_username("tok") == "alice"
    monkeypatch.setattr(auth.requests, "get", lambda *a, **k: FakeResponse({}, status=401))
    with pytest.raises(auth.AuthError):
        auth.fetch_username("tok")


# ---- app-level tests ----------------------------------------------------------

def make_app(query=None) -> AppTest:
    at = AppTest.from_file(APP, default_timeout=60)
    at.secrets["github"] = CFG
    for k, v in (query or {}).items():
        at.query_params[k] = v
    return at


def test_signed_out_shows_sign_in_and_hides_tools():
    at = make_app().run()
    assert not at.exception
    assert any("Sign in with GitHub" in m.value for m in at.markdown)
    assert len(at.tabs) == 0


def test_missing_config_shows_setup_error():
    # Override the real secrets.toml, which may already be filled in.
    at = AppTest.from_file(APP, default_timeout=60)
    at.secrets["github"] = {**CFG, "client_id": "", "client_secret": ""}
    at.run()
    assert not at.exception
    assert "not configured" in at.error[0].value
    assert len(at.tabs) == 0


def test_setup_error_names_missing_keys_without_values():
    at = AppTest.from_file(APP, default_timeout=60)
    at.secrets["github"] = {**CFG, "client_secret": "", "require_star_follow": True, "owner": "", "repo": "writelens"}
    at.run()
    msg = at.error[0].value
    assert "`client_secret`" in msg and "`owner`" in msg and "`client_id`" not in msg
    assert "cid" not in msg  # never echo a value


def test_setup_error_spots_missing_section_header():
    at = AppTest.from_file(APP, default_timeout=60)
    at.secrets["client_id"] = "cid"
    at.secrets["client_secret"] = "cs"
    at.run()
    assert "[github]" in at.error[0].value


def test_callback_allowed_user_signs_in(monkeypatch):
    monkeypatch.setattr(auth, "exchange_code", lambda cfg, code: "tok")
    monkeypatch.setattr(auth, "fetch_username", lambda token: "Alice")
    at = make_app({"code": "c", "state": auth.new_state()}).run()
    assert not at.exception
    assert at.session_state["user"] == "Alice"
    assert len(at.tabs) == 2


def test_callback_denied_user(monkeypatch):
    monkeypatch.setattr(auth, "exchange_code", lambda cfg, code: "tok")
    monkeypatch.setattr(auth, "fetch_username", lambda token: "mallory")
    at = make_app({"code": "c", "state": auth.new_state()}).run()
    assert "user" not in at.session_state
    assert "Access denied" in at.error[0].value
    assert len(at.tabs) == 0


def test_callback_forged_state_never_contacts_github(monkeypatch):
    def fail(*a, **k):
        raise AssertionError("GitHub must not be called with an invalid state")

    monkeypatch.setattr(auth, "exchange_code", fail)
    at = make_app({"code": "c", "state": "forged"}).run()
    assert not at.exception
    assert "user" not in at.session_state
    assert "invalid" in at.error[0].value


def test_github_down_shows_error(monkeypatch):
    def down(cfg, code):
        raise auth.AuthError("Could not reach GitHub. Please try again.")

    monkeypatch.setattr(auth, "exchange_code", down)
    at = make_app({"code": "c", "state": auth.new_state()}).run()
    assert "user" not in at.session_state
    assert "reach GitHub" in at.error[0].value


# ---- star + follow requirement ------------------------------------------------

GATE = {**CFG, "owner": "AneeshShetty-Ani", "repo": "writelens", "require_star_follow": True}


def gated_app(query=None) -> AppTest:
    at = AppTest.from_file(APP, default_timeout=60)
    at.secrets["github"] = GATE
    for k, v in (query or {}).items():
        at.query_params[k] = v
    return at


def answers(starred: bool, following: bool):
    """A fake requests.get for the two GitHub checks."""
    def fake_get(url, headers, timeout):
        assert headers["Authorization"] == "Bearer tok"
        ok = starred if "/user/starred/AneeshShetty-Ani/writelens" in url else following
        return FakeResponse(None, status=204 if ok else 404)
    return fake_get


def sign_in_as(monkeypatch, username):
    monkeypatch.setattr(auth, "exchange_code", lambda cfg, code: "tok")
    monkeypatch.setattr(auth, "fetch_username", lambda token: username)
    return gated_app({"code": "c", "state": auth.new_state()}).run()


def test_check_star_follow_reads_204_and_404(monkeypatch):
    monkeypatch.setattr(auth.requests, "get", answers(True, False))
    assert auth.check_star_follow("tok", GATE) == (True, False)


def test_check_reports_github_errors(monkeypatch):
    monkeypatch.setattr(auth.requests, "get", lambda *a, **k: FakeResponse(None, status=403))
    with pytest.raises(auth.AuthError, match="403"):
        auth.check_star_follow("tok", GATE)


def test_gate_needs_owner_and_repo():
    at = AppTest.from_file(APP, default_timeout=60)
    at.secrets["github"] = {**GATE, "repo": ""}
    at.run()
    assert "not configured" in at.error[0].value


def test_starred_and_following_user_gets_in(monkeypatch):
    monkeypatch.setattr(auth.requests, "get", answers(True, True))
    at = sign_in_as(monkeypatch, "stranger")
    assert at.session_state["user"] == "stranger"
    assert "pending_token" not in at.session_state  # the token isn't kept once the check passes
    assert len(at.tabs) == 2


def test_missing_star_shows_unlock_card(monkeypatch):
    monkeypatch.setattr(auth.requests, "get", answers(False, True))
    at = sign_in_as(monkeypatch, "stranger")
    assert "user" not in at.session_state and len(at.tabs) == 0
    page = "\n".join(m.value for m in at.markdown)
    assert "Star <b>AneeshShetty-Ani/writelens</b></span><span class=\"uf-todo\">" in page
    assert "Follow <b>@AneeshShetty-Ani</b></span><span class=\"uf-ok\">" in page
    assert 'href="https://github.com/AneeshShetty-Ani/writelens"' in page


def test_check_again_lets_user_in_after_starring(monkeypatch):
    monkeypatch.setattr(auth.requests, "get", answers(False, False))
    at = sign_in_as(monkeypatch, "stranger")
    assert "user" not in at.session_state
    monkeypatch.setattr(auth.requests, "get", answers(True, True))
    at.button(key="gate_check").click().run()
    assert at.session_state["user"] == "stranger"
    assert len(at.tabs) == 2


def test_owner_and_allowed_users_skip_the_check(monkeypatch):
    def fail(*a, **k):
        raise AssertionError("no star/follow check for the owner")

    monkeypatch.setattr(auth.requests, "get", fail)
    for name in ("aneeshshetty-ani", "Alice"):
        at = sign_in_as(monkeypatch, name)
        assert at.session_state["user"] == name


def test_gate_escapes_username(monkeypatch):
    monkeypatch.setattr(auth.requests, "get", answers(False, False))
    at = sign_in_as(monkeypatch, "<img src=x>")
    page = "\n".join(m.value for m in at.markdown)
    assert "&lt;img src=x&gt;" in page and "<img src=x>" not in page


def test_github_down_during_check_keeps_user_waiting(monkeypatch):
    def down(*a, **k):
        raise requests.ConnectionError()

    monkeypatch.setattr(auth.requests, "get", down)
    at = sign_in_as(monkeypatch, "stranger")
    assert "user" not in at.session_state
    assert "reach GitHub" in at.error[0].value


def test_different_account_button_signs_out(monkeypatch):
    monkeypatch.setattr(auth.requests, "get", answers(False, False))
    at = sign_in_as(monkeypatch, "stranger")
    at.button(key="gate_signout").click().run()
    assert "pending_user" not in at.session_state and "pending_token" not in at.session_state
    assert any("Sign in with GitHub" in m.value for m in at.markdown)


def test_sign_out():
    at = make_app()
    at.session_state["user"] = "Alice"
    at.run()
    assert len(at.tabs) == 2
    at.button(key="logout").click().run()
    assert "user" not in at.session_state
    assert len(at.tabs) == 0
