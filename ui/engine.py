"""The AI engine as the pages use it: run a task if the AI is available (else return None so the page stays
offline), remember answers so re-checking the same text doesn't spend another request, and draw the
status light under the username."""

import datetime
import hashlib
import html
from concurrent.futures import ThreadPoolExecutor
from typing import Callable

import streamlit as st

import ai

CACHE_KEY = "ai_cache"
MAX_CACHED = 20
WORKERS = 4  # parts of a long text asked at once; more trips the free models' per-minute limit


@st.cache_resource
def daily_limit(limit: int) -> ai.DailyLimit:
    """One counter for the whole server, shared by every visitor."""
    return ai.DailyLimit(limit)


def today() -> str:
    return datetime.date.today().isoformat()


def config() -> tuple[list[ai.Provider], int]:
    return ai.load_config(st.secrets)


def available() -> bool:
    return bool(config()[0])


def left_today() -> int:
    providers, limit = config()
    return daily_limit(limit).remaining(st.session_state.get("user", ""), today()) if providers else 0


def run_parts(name: str, jobs: list[tuple[tuple[str, int], Callable]], *inputs: str) -> list[ai.Answer | None] | None:
    """The AI's answers to `jobs` ((request, max tokens), accept), asked side by side, with None for any that
    failed; None instead of a list when the AI is off, used up for today or failed every job. One check
    counts once against the daily limit however many parts it has. `inputs` identify it for the cache."""
    providers, limit = config()
    if not providers or not jobs:
        return None
    digest = hashlib.sha256("\x00".join((name, *inputs)).encode()).hexdigest()
    cache = st.session_state.setdefault(CACHE_KEY, {})
    if digest in cache:
        return cache[digest]
    user = st.session_state.get("user", "")
    limiter = daily_limit(limit)
    if limiter.remaining(user, today()) <= 0:
        st.session_state["ai_skipped"] = "today's AI limit is used up"
        return None

    def ask(job) -> tuple[ai.Answer | None, str]:
        (task, tokens), accept = job
        try:
            return ai.ask(providers, task, accept, tokens), ""
        except ai.AIError as exc:
            return None, str(exc).rstrip(".").lower()

    label = f"AI is checking ({len(jobs)} parts)..." if len(jobs) > 1 else "AI is checking..."
    with st.spinner(label, show_time=True):
        if len(jobs) == 1:
            results = [ask(jobs[0])]
        else:
            with ThreadPoolExecutor(min(WORKERS, len(jobs))) as pool:
                results = list(pool.map(ask, jobs))
    answers = [a for a, _ in results]
    if errors := [e for _, e in results if e]:
        st.session_state["ai_skipped"] = errors[0]
    if not any(answers):
        return None
    limiter.use(user, today())
    if len(cache) >= MAX_CACHED:
        cache.pop(next(iter(cache)))
    cache[digest] = answers
    return answers


def run(name: str, task: tuple[str, int], accept, *inputs: str) -> ai.Answer | None:
    """The AI's answer to one `task` ((request, max tokens)), or None when it's off, busy or used up."""
    answers = run_parts(name, [(task, accept)], *inputs)
    return answers[0] if answers else None


def by_line(answers) -> str:
    """Which model(s) answered: one Answer or a list of them (None entries skipped)."""
    answers = [answers] if isinstance(answers, ai.Answer) else answers
    return ", ".join(dict.fromkeys(f"{ai.model_label(a.model)} via {a.provider}" for a in answers if a))


def offline_note(what: str) -> None:
    """Say why a part ran offline, if the AI was meant to help with it."""
    if available():
        why = st.session_state.pop("ai_skipped", "the AI didn't answer")
        st.caption(f":material/cloud_off: {what} ran offline only: {why}.")


def partial_note(answers: list, what: str) -> None:
    """Say which parts of a long text the AI couldn't check (those parts kept the offline results)."""
    if missed := sum(a is None for a in answers):
        why = st.session_state.pop("ai_skipped", "the AI didn't answer")
        st.caption(f":material/cloud_off: AI checked {len(answers) - missed} of {len(answers)} parts of {what}; "
                   f"the rest ran offline only: {why}.")


def status_html(state: str) -> str:
    label, meaning = ai.STATUSES[state]
    return (f'<div class="uf-engine uf-engine-{state}" title="{html.escape(meaning)}" role="status">'
            f'<span class="uf-engine-dot"></span>AI engine: <b>{label}</b></div>')


def render_status(box) -> None:
    providers, _ = config()
    box.markdown(status_html(ai.status(providers, left_today())), unsafe_allow_html=True)
