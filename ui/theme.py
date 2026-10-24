"""Shared look ("Frosted Obsidian"): CSS, the header, issue cards, and small helpers used by every page."""

import html

import streamlit as st

from analysis import READ_WPM, SPEAK_WPM, duration

VERSION = "1.4.0"

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
:root {
  --uf-accent: #06B6D4; --uf-bg: #12131C; --uf-glass: rgba(30, 41, 59, .7); --uf-edge: rgba(255, 255, 255, .1);
  --uf-text: #F9FAFB; --uf-muted: #94A3B8;
}
/* one centred column; no sidebar */
[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"], [data-testid="stAppDeployButton"] { display: none; }
[data-testid="stMainBlockContainer"], .block-container {
  max-width: min(1480px, 100%); padding: 4.5rem clamp(16px, 4vw, 64px) 3rem;
}
a, a:visited { color: var(--uf-accent); }

/* type: Inter everywhere (icon spans set their own font, so they're unaffected) */
html, body, .stApp, .stMarkdown, button, textarea, input, label, h1, h2, h3, h4, h5 {
  font-family: 'Inter', system-ui, sans-serif;
}
.stApp h3 { font-size: 1.75rem; font-weight: 700; letter-spacing: -.02em; margin: .4rem 0 .3rem; }
.stApp h4 { font-size: 1.12rem; font-weight: 600; margin: 1.4rem 0 .5rem; }
.stApp h5 { font-size: 1rem; font-weight: 600; margin: 1.1rem 0 .4rem; }
.stApp p { line-height: 1.65; }

/* a faint cyan light at the top of the page */
.stApp {
  background: radial-gradient(900px 380px at 50% -120px, rgba(6, 182, 212, .14), transparent 70%), var(--uf-bg);
}

/* header: wordmark left, account menu right */
.uf-logo {
  font-weight: 800; font-size: 1.9rem; letter-spacing: -.03em; line-height: 1.1; display: inline-block;
  background: linear-gradient(90deg, #F9FAFB 0%, #F9FAFB 30%, #22D3EE 45%, #818CF8 60%, #F9FAFB 75%, #F9FAFB 100%);
  background-size: 300% 100%; -webkit-background-clip: text; background-clip: text; color: transparent;
  animation: uf-shine 8s ease-in-out infinite; filter: drop-shadow(0 0 18px rgba(6, 182, 212, .25));
}
.uf-logo span { color: var(--uf-accent); -webkit-text-fill-color: var(--uf-accent); }
@keyframes uf-shine { 0%, 100% { background-position: 100% 0; } 50% { background-position: 0 0; } }
.uf-tagline { color: var(--uf-muted); font-size: .88rem; margin-top: 4px; }

/* gentle lift on hover for buttons and cards */
.stButton button, .stDownloadButton button, .stFormSubmitButton button, .stLinkButton a {
  border-radius: 10px; font-weight: 600; transition: transform .15s ease, box-shadow .2s ease, border-color .2s ease;
}
.stButton button:hover, .stDownloadButton button:hover, .stFormSubmitButton button:hover { transform: translateY(-1px); }
[data-testid="stBaseButton-primary"]:hover { box-shadow: 0 6px 22px rgba(6, 182, 212, .35); }
@media (prefers-reduced-motion: reduce) {
  .uf-logo { animation: none; }
  .stButton button, .uf-card { transition: none; }
  .stButton button:hover, .uf-card:hover { transform: none; }
}

/* top navigation: a row of pill tabs with a hairline underneath */
.st-key-topnav { border-bottom: 1px solid var(--uf-edge); padding-bottom: .7rem; margin-bottom: 1.2rem; }
.st-key-topnav button { border-radius: 999px; }
.st-key-topnav [data-testid="stBaseButton-secondary"] { background: transparent; border-color: transparent; color: var(--uf-muted); }
.st-key-topnav [data-testid="stBaseButton-secondary"]:hover { color: var(--uf-text); border-color: var(--uf-edge); }
.st-key-topnav [data-testid="stBaseButton-primary"] { box-shadow: 0 0 16px rgba(6, 182, 212, .35); }

/* frosted glass inputs with a cyan glow on focus */
[data-baseweb="textarea"], [data-baseweb="input"], [data-baseweb="select"] > div {
  background: var(--uf-glass) !important; border: 1px solid var(--uf-edge) !important;
  backdrop-filter: blur(10px); border-radius: 12px !important;
}
[data-baseweb="textarea"] textarea, [data-baseweb="input"] input { background: transparent !important; }
[data-baseweb="textarea"]:focus-within, [data-baseweb="input"]:focus-within {
  border-color: rgba(6, 182, 212, .6) !important; box-shadow: 0 0 0 3px rgba(6, 182, 212, .15);
}

/* writing score ring */
.uf-score { display: flex; align-items: center; gap: 18px; }
.uf-ring { width: 104px; height: 104px; border-radius: 50%; display: grid; place-items: center; flex: none;
  box-shadow: 0 0 24px rgba(6, 182, 212, .15); }
.uf-ring-inner { width: 82px; height: 82px; border-radius: 50%; background: var(--uf-bg);
  display: flex; flex-direction: column; align-items: center; justify-content: center; line-height: 1; }
.uf-ring-inner b { font-size: 1.9rem; font-weight: 800; }
.uf-ring-inner small { color: var(--uf-muted); font-size: .72rem; margin-top: 3px; }
.uf-score-title { color: var(--uf-muted); font-size: .85rem; }
.uf-score-label { font-size: 1.25rem; font-weight: 700; }
.uf-score-change { font-size: .82rem; font-weight: 600; margin-top: 2px; }
.uf-up { color: #4ade80; }
.uf-down { color: #F87171; }
.uf-drafts { border-radius: 10px; padding: 10px 14px; margin: .2rem 0 1rem; font-size: .9rem;
  background: var(--uf-glass); border: 1px solid var(--uf-edge); }

/* sign-in screen */
.uf-signin { max-width: 440px; margin: 8vh auto 1.2rem; text-align: center; padding: 40px 32px;
  background: var(--uf-glass); border: 1px solid var(--uf-edge); border-radius: 18px; backdrop-filter: blur(12px);
  box-shadow: 0 0 40px rgba(6, 182, 212, .12); }
.uf-signin p { color: var(--uf-muted); margin: .8rem 0 0; }
.uf-step { display: flex; justify-content: space-between; align-items: center; gap: 12px; text-align: left;
  padding: 12px 14px; margin-top: 14px; border-radius: 10px; background: rgba(255, 255, 255, .04);
  border: 1px solid var(--uf-edge); }
.uf-ok { color: #4ade80; font-weight: 700; white-space: nowrap; }
.uf-todo { color: #F87171; font-weight: 700; white-space: nowrap; }

/* final output boxes: readable text instead of code styling, with a cyan edge */
[class*="st-key-final_"] [data-testid="stCode"] pre {
  background: var(--uf-glass) !important; border: 1px solid rgba(6, 182, 212, .45); border-radius: 12px;
  box-shadow: 0 0 18px rgba(6, 182, 212, .12); padding: 16px 18px;
}
[class*="st-key-final_"] [data-testid="stCode"] code {
  font-family: 'Inter', system-ui, sans-serif !important; font-size: .95rem; line-height: 1.7; color: var(--uf-text);
}

.uf-counter { color: var(--uf-muted); font-size: .8rem; margin-top: -.4rem; letter-spacing: .02em; }
.uf-placeholder {
  border-radius: 12px; background: var(--uf-glass); color: #64748B; padding: 18px; min-height: 120px;
  border: 1px dashed var(--uf-edge); text-align: center;
}
.uf-highlight {
  border-radius: 12px; background: var(--uf-glass); padding: 14px 18px; line-height: 1.8;
  border: 1px solid var(--uf-edge); backdrop-filter: blur(10px);
  max-height: 520px; overflow-y: auto; white-space: normal; margin-bottom: 1rem;
}
/* in-text highlights: red = plagiarism, gold = grammar, cyan = style */
.uf-match, .uf-uncited { background: rgba(240, 82, 82, .3); color: #FFAAAA; border-radius: 3px; }
.uf-cited { background: rgba(74, 222, 128, .2); color: #BBF7D0; border-radius: 3px; }
.uf-cited.uf-uncited { background: rgba(240, 82, 82, .3); color: #FFAAAA; }
.uf-passive { background: rgba(245, 158, 11, .2); color: #FDE68A; }
.uf-wordy { background: rgba(6, 182, 212, .22); color: #A5F3FC; border-radius: 3px; }
.uf-adverb { text-decoration: underline wavy #67E8F9; text-underline-offset: 4px; }
.uf-cliche { background: rgba(167, 139, 250, .22); color: #DDD6FE; border-radius: 3px; }
.uf-contraction { text-decoration: underline dashed #67E8F9; text-underline-offset: 4px; }
.uf-spelling { text-decoration: underline wavy #F59E0B; text-underline-offset: 4px; }
.uf-long { border-bottom: 2px dotted #67E8F9; }
.uf-legend { display: flex; gap: 14px; flex-wrap: wrap; font-size: .82rem; margin: .2rem 0 .8rem; }
.uf-legend span { padding: 1px 6px; }

/* issue feed: frosted cards in a fluid grid, coloured by kind */
.uf-feed { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: .8rem; margin-bottom: 1rem; }
.uf-feed .uf-card { margin: 0; }
.uf-card {
  border-radius: 12px; padding: 12px 16px; margin: 0 0 .8rem 0; font-size: .9rem; line-height: 1.5;
  background: var(--uf-glass); border: 1px solid var(--uf-edge); border-top-width: 3px; backdrop-filter: blur(10px);
  transition: transform .18s ease, box-shadow .2s ease;
}
.uf-card:hover { transform: translateY(-2px); }
.uf-card-plagiarism:hover { box-shadow: 0 8px 26px rgba(240, 82, 82, .25); }
.uf-card-grammar:hover { box-shadow: 0 8px 26px rgba(245, 158, 11, .22); }
.uf-card-style:hover { box-shadow: 0 8px 26px rgba(6, 182, 212, .25); }
.uf-card b { font-weight: 700; }
.uf-card-plagiarism { color: #FFAAAA; border-top-color: #F05252; box-shadow: 0 0 14px rgba(240, 82, 82, .15); }
.uf-card-grammar { color: #FDE68A; border-top-color: #F59E0B; box-shadow: 0 0 14px rgba(245, 158, 11, .12); }
.uf-card-style { color: #A5F3FC; border-top-color: #06B6D4; box-shadow: 0 0 14px rgba(6, 182, 212, .15); }
.uf-card-quote { margin-top: 6px; padding-left: 10px; border-left: 2px solid currentColor; opacity: .85; }
</style>
"""

CARD_KINDS = ("plagiarism", "grammar", "style")


def apply_css() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def banner() -> None:
    st.markdown(
        '<div class="uf-logo">write<span>lens</span></div>'
        '<div class="uf-tagline">Check your writing, cite your sources, compare documents</div>',
        unsafe_allow_html=True,
    )


def card_html(kind: str, title: str, advice: str, quote: str = "") -> str:
    """An issue badge. `title` and `advice` are trusted app text and may contain <b>/<i>;
    `quote` is user text and is escaped."""
    assert kind in CARD_KINDS
    body = f"<b>{title}</b> → {advice}"
    if quote:
        body += f'<div class="uf-card-quote">{html.escape(quote)}</div>'
    return f'<div class="uf-card uf-card-{kind}">{body}</div>'


def card(kind: str, title: str, advice: str, quote: str = "") -> None:
    st.markdown(card_html(kind, title, advice, quote), unsafe_allow_html=True)


def feed(cards: list[str]) -> None:
    """Show several cards from card_html() as a grid."""
    if cards:
        st.markdown(f'<div class="uf-feed">{"".join(cards)}</div>', unsafe_allow_html=True)


def final_output(key: str, title: str, text: str, note: str = "", file_name: str = "") -> None:
    """The finished text of a tool, with a copy button (top right of the box) and a .txt download."""
    with st.container(key=f"final_{key}"):
        st.markdown(f"#### :material/task_alt: {title}")
        if note:
            st.caption(note)
        st.code(text, language=None, wrap_lines=True)
        if file_name:
            st.download_button("Download (.txt)", text, file_name, "text/plain", key=f"dl_{key}",
                               icon=":material/download:", on_click="ignore")


def counter(text: str) -> None:
    words = len(text.split())
    times = f" | Reading: {duration(words, READ_WPM)} | Speaking: {duration(words, SPEAK_WPM)}" if words else ""
    st.markdown(
        f'<div class="uf-counter">Words: {words:,} | Characters: {len(text):,}{times}</div>',
        unsafe_allow_html=True,
    )


def clear_keys(*keys: str) -> None:
    """Button callback: empty the given text widgets."""
    for key in keys:
        st.session_state[key] = ""
