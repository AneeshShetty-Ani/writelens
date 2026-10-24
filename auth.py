"""GitHub OAuth sign-in with a server-side allow-list, and optionally a star + follow requirement.

Login state lives in the server-side Streamlit session. So that a page refresh doesn't sign the
user out, the address bar also carries `?session=<username>.<expiry>.<signature>`: an HMAC made
with a key derived from the OAuth client secret, so it can't be forged or edited. The OAuth
`state` values are kept server-side and are single-use.

With `require_star_follow`, anyone may sign in, but only gets in after starring
`owner/repo` and following `owner`. The owner and `allowed_users` skip that check.
"""

import base64
import hashlib
import hmac
import html
import secrets
import threading
import time
import urllib.parse

import requests
import streamlit as st

AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
TOKEN_URL = "https://github.com/login/oauth/access_token"
USER_URL = "https://api.github.com/user"
# 204 = yes, 404 = no. Called with the user's own token: public data, so no OAuth scope is needed,
# and each user gets their own rate limit instead of sharing the server's.
STARRED_URL = "https://api.github.com/user/starred/{owner}/{repo}"
FOLLOWING_URL = "https://api.github.com/user/following/{owner}"
STATE_TTL_SECONDS = 600
SESSION_PARAM = "session"
SESSION_TTL_SECONDS = 7 * 24 * 3600
TIMEOUT = 10

# The user leaves for github.com and returns in a new Streamlit session, so pending
# states must outlive the session: keep them in the server process.
_pending_states: dict[str, float] = {}
_lock = threading.Lock()


class AuthError(Exception):
    pass


def get_config() -> dict | None:
    try:
        gh = st.secrets["github"]
        cfg = {
            "client_id": gh["client_id"],
            "client_secret": gh["client_secret"],
            "redirect_uri": gh["redirect_uri"],
            "allowed_users": list(gh.get("allowed_users", [])),
            "owner": str(gh.get("owner", "")).strip(),
            "repo": str(gh.get("repo", "")).strip(),
            "require_star_follow": bool(gh.get("require_star_follow", False)),
        }
    except Exception:
        return None
    if not cfg["client_id"] or not cfg["client_secret"]:
        return None
    if cfg["require_star_follow"] and not (cfg["owner"] and cfg["repo"]):
        return None  # the gate can't work without knowing what to star and whom to follow
    return cfg


def config_problem() -> str:
    """Why get_config() failed, naming settings but never showing their values."""
    try:
        top = list(st.secrets.keys())
    except Exception:
        return "The secrets couldn't be read. Either none are saved, or there's a typing mistake such as a missing quote."
    if "github" not in top:
        if "client_id" in top or "client_secret" in top:
            return "Add a line `[github]` at the very top of the secrets, above `client_id`."
        return "No `[github]` section found. The secrets box may be empty or not saved."
    gh = st.secrets["github"]
    needed = ["client_id", "client_secret", "redirect_uri"]
    if bool(gh.get("require_star_follow", False)):
        needed += ["owner", "repo"]
    missing = [k for k in needed if not str(gh.get(k, "")).strip()]
    if missing:
        return "Missing or empty under `[github]`: " + ", ".join(f"`{k}`" for k in missing) + "."
    return "Check the `[github]` secrets for typing mistakes."


def new_state() -> str:
    state = secrets.token_urlsafe(32)
    now = time.time()
    with _lock:
        for s, created in list(_pending_states.items()):
            if now - created > STATE_TTL_SECONDS:
                del _pending_states[s]
        _pending_states[state] = now
    return state


def consume_state(state: str | None) -> bool:
    if not state:
        return False
    with _lock:
        created = _pending_states.pop(state, None)
    return created is not None and time.time() - created <= STATE_TTL_SECONDS


def _session_signature(payload: str, cfg: dict) -> str:
    # a separate key for this purpose, so the client secret itself is never used directly
    key = hmac.new(cfg["client_secret"].encode(), b"writelens-session-v1", hashlib.sha256).digest()
    digest = hmac.new(key, payload.encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip("=")


def make_session_token(username: str, cfg: dict) -> str:
    # GitHub usernames are letters, digits and hyphens, so "." can't appear inside one
    payload = f"{username}.{int(time.time()) + SESSION_TTL_SECONDS}"
    return f"{payload}.{_session_signature(payload, cfg)}"


def read_session_token(token: str | None, cfg: dict) -> str | None:
    """The username in a valid, unexpired token; None for anything else."""
    try:
        username, expires, signature = (token or "").split(".")
        expired = int(expires) < time.time()
    except ValueError:
        return None
    expected = _session_signature(f"{username}.{expires}", cfg).encode()
    if expired or not username or not hmac.compare_digest(signature.encode(), expected):
        return None
    return username


def restore_session(cfg: dict) -> str | None:
    """Sign the user back in from the token in the address bar, e.g. after a page refresh."""
    username = read_session_token(st.query_params.get(SESSION_PARAM), cfg)
    # without the star/follow gate only the allow-list gets in, and it may have changed since
    if username and (cfg["require_star_follow"] or skips_gate(username, cfg)):
        return username
    if SESSION_PARAM in st.query_params:
        del st.query_params[SESSION_PARAM]
    return None


def authorize_url(cfg: dict, state: str) -> str:
    # No `scope`: only public profile information is requested.
    query = urllib.parse.urlencode(
        {"client_id": cfg["client_id"], "redirect_uri": cfg["redirect_uri"], "state": state, "allow_signup": "false"}
    )
    return f"{AUTHORIZE_URL}?{query}"


def exchange_code(cfg: dict, code: str) -> str:
    try:
        resp = requests.post(
            TOKEN_URL,
            data={
                "client_id": cfg["client_id"],
                "client_secret": cfg["client_secret"],
                "code": code,
                "redirect_uri": cfg["redirect_uri"],
            },
            headers={"Accept": "application/json"},
            timeout=TIMEOUT,
        )
        payload = resp.json()
    except (requests.RequestException, ValueError) as exc:
        raise AuthError("Could not reach GitHub. Please try again.") from exc
    token = payload.get("access_token")
    if not token:
        raise AuthError(payload.get("error_description") or "GitHub rejected the sign-in. Please try again.")
    return token


def fetch_username(token: str) -> str:
    try:
        resp = requests.get(
            USER_URL,
            headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        login = resp.json().get("login")
    except (requests.RequestException, ValueError) as exc:
        raise AuthError("Could not read your GitHub profile. Please try again.") from exc
    if not login:
        raise AuthError("Could not read your GitHub profile. Please try again.")
    return login


def is_allowed(username: str, allowed: list[str]) -> bool:
    return username.lower() in {u.strip().lower() for u in allowed if u.strip()}


def skips_gate(username: str, cfg: dict) -> bool:
    return is_allowed(username, [*cfg["allowed_users"], cfg["owner"]])


def _yes_no(url: str, token: str) -> bool:
    try:
        resp = requests.get(
            url, headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}, timeout=TIMEOUT
        )
    except requests.RequestException as exc:
        raise AuthError("Couldn't reach GitHub to check. Please try again.") from exc
    if resp.status_code == 204:
        return True
    if resp.status_code == 404:
        return False
    if resp.status_code == 401:
        raise AuthError("Your GitHub sign-in expired. Please sign in again.")
    raise AuthError(f"GitHub didn't answer the check (error {resp.status_code}). Please try again in a minute.")


def check_star_follow(token: str, cfg: dict) -> tuple[bool, bool]:
    """(has starred owner/repo, follows owner)."""
    starred = _yes_no(STARRED_URL.format(owner=cfg["owner"], repo=cfg["repo"]), token)
    following = _yes_no(FOLLOWING_URL.format(owner=cfg["owner"]), token)
    return starred, following


def sign_out() -> None:
    for key in ("user", "pending_user", "pending_token", "gate_status", "auth_error"):
        st.session_state.pop(key, None)
    if SESSION_PARAM in st.query_params:
        del st.query_params[SESSION_PARAM]


def refresh_gate(cfg: dict) -> None:
    """Re-run the star/follow check for the pending user; let them in if both are done."""
    try:
        st.session_state["gate_status"] = check_star_follow(st.session_state["pending_token"], cfg)
        st.session_state.pop("auth_error", None)
    except AuthError as exc:
        st.session_state["auth_error"] = str(exc)
        return
    if all(st.session_state["gate_status"]):
        st.session_state["user"] = st.session_state.pop("pending_user")
        for key in ("pending_token", "gate_status"):
            st.session_state.pop(key, None)


def render_gate(cfg: dict) -> None:
    starred, following = st.session_state.get("gate_status", (False, False))
    owner, repo = html.escape(cfg["owner"]), html.escape(cfg["repo"])
    repo_url = f"https://github.com/{urllib.parse.quote(cfg['owner'])}/{urllib.parse.quote(cfg['repo'])}"
    owner_url = f"https://github.com/{urllib.parse.quote(cfg['owner'])}"
    mark = lambda ok: '<span class="uf-ok">✓ Done</span>' if ok else '<span class="uf-todo">✗ Not yet</span>'  # noqa: E731
    st.markdown(
        '<div class="uf-signin"><div class="uf-logo">write<span>lens</span></div>'
        f"<p>Hi <b>{html.escape(st.session_state['pending_user'])}</b>! One more step to unlock WriteLens:</p>"
        f'<div class="uf-step"><span>⭐ Star <b>{owner}/{repo}</b></span>{mark(starred)}</div>'
        f'<div class="uf-step"><span>👤 Follow <b>@{owner}</b></span>{mark(following)}</div>'
        "</div>",
        unsafe_allow_html=True,
    )
    if error := st.session_state.get("auth_error"):
        st.error(error)
    _, mid, _ = st.columns([1, 2, 1])
    # link buttons, not HTML links: they work inside Streamlit Cloud's iframe
    left, right = mid.columns(2)
    left.link_button("⭐ Star the repo", repo_url, width="stretch")
    right.link_button("👤 Follow", owner_url, width="stretch")
    mid.button("I've done it, check again", key="gate_check", type="primary", icon=":material/refresh:",
               width="stretch", on_click=refresh_gate, args=(cfg,))
    mid.button("Use a different GitHub account", key="gate_signout", width="stretch", on_click=sign_out)
    st.stop()


def require_login() -> str:
    """Return the signed-in username, or render the sign-in screen and stop the script."""
    cfg = get_config()
    if "user" in st.session_state:
        if cfg is not None and SESSION_PARAM not in st.query_params:
            st.query_params[SESSION_PARAM] = make_session_token(st.session_state["user"], cfg)
        return st.session_state["user"]

    if cfg is not None and (username := restore_session(cfg)):
        st.session_state["user"] = username
        return username

    if cfg is None:
        st.title("🔍 WriteLens")
        st.error(
            f"GitHub sign-in is not configured. {config_problem()}\n\n"
            "On Streamlit Cloud: **Manage app → ⋮ → Settings → Secrets**. Running locally: copy "
            "`.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and fill it in."
        )
        st.stop()

    params = st.query_params
    if "code" in params:
        code, state = params.get("code"), params.get("state")
        st.query_params.clear()
        if not consume_state(state):
            st.session_state["auth_error"] = "Sign-in link expired or was invalid. Please try again."
        else:
            try:
                token = exchange_code(cfg, code)
                username = fetch_username(token)
            except AuthError as exc:
                st.session_state["auth_error"] = str(exc)
            else:
                st.session_state.pop("auth_error", None)
                if skips_gate(username, cfg):
                    st.session_state["user"] = username
                elif cfg["require_star_follow"]:
                    # kept server-side only, until the check passes
                    st.session_state["pending_user"], st.session_state["pending_token"] = username, token
                    refresh_gate(cfg)
                else:
                    st.session_state["auth_error"] = f"Access denied: **{username}** is not on the allowed list."
        st.rerun()

    if "pending_user" in st.session_state:
        render_gate(cfg)

    st.markdown(
        '<div class="uf-signin"><div class="uf-logo">write<span>lens</span></div>'
        "<p>Check your writing, cite your sources and compare documents.</p></div>",
        unsafe_allow_html=True,
    )
    # Streamlit Cloud runs the app in an iframe that blocks a plain link from leaving it, so use
    # Streamlit's own link button: GitHub opens in a new tab and returns to the app there.
    _, mid, _ = st.columns([1, 2, 1])
    mid.link_button("Sign in with GitHub", authorize_url(cfg, new_state()), type="primary",
                    icon=":material/login:", width="stretch")
    mid.caption("Opens GitHub in a new tab. You'll come back to WriteLens there, signed in.")
    if error := st.session_state.get("auth_error"):
        st.error(error)
    st.stop()
