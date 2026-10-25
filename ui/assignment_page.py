import html

import streamlit as st

from assignment import check_assignment, coverage, improve_essay
from ui.theme import clear_keys, counter, final_output

GROUPS = (("Task", "What the question asks you to do"), ("Length", "Numbers and length"),
          ("Structure", "Structure"), ("Topic", "Topics the question names"))
STATUS = {"ok": ("✓ Covered", "uf-req-ok"), "partial": ("! Partly", "uf-req-partial"),
          "missing": ("✗ Missing", "uf-req-missing"), "check": ("? Check yourself", "uf-req-check")}

EXAMPLE_QUESTION = (
    "Critically evaluate the impact of social media on students' sleep and academic performance. "
    "Use at least three academic sources and two examples. Write 400 words, with an introduction, "
    "a conclusion and a reference list."
)
EXAMPLE_ESSAY = """Social media now shapes how students spend their evenings. This essay evaluates its effect on sleep and on academic performance.

Late-night scrolling cuts sleep. A survey of 2,000 students found that most checked their phones after midnight (Smith, 2021). For example, short videos are designed to keep viewers watching, which delays sleep.

However, social media also has benefits. Students share notes and form study groups online (Lee, 2020). For instance, a class group chat can solve a homework problem in minutes.

Overall, social media harms sleep when it is used late at night, but it can support learning when it is used with limits.

References

Lee, A. (2020). Study groups online. Journal of Learning.
Smith, J. (2021). Phones at midnight. Sleep Studies."""


def use_checker_text() -> None:
    st.session_state["assign_text"] = st.session_state.get("checker_text", "")


def load_example() -> None:
    st.session_state["assign_prompt"] = EXAMPLE_QUESTION
    st.session_state["assign_text"] = EXAMPLE_ESSAY


def requirement_html(label: str, status: str, detail: str) -> str:
    word, cls = STATUS[status]
    return (f'<div class="uf-req {cls}"><span class="uf-req-icon">{word}</span>'
            f'<span><b>{html.escape(label)}</b> <small>{html.escape(detail)}</small></span></div>')


def render() -> None:
    st.markdown("### :material/assignment: Assignment Checker")
    st.write("Paste your assignment question (or its marking rubric) and your essay. WriteLens lists what the "
             "question asks for and shows whether your essay covers each part.")

    st.markdown("#### The assignment question")
    st.text_area("Assignment question", key="assign_prompt", height=130, label_visibility="collapsed",
                 placeholder="e.g. Compare two approaches to... Use at least three sources. 1,500 words.")
    st.markdown("#### Your essay")
    essay = st.text_area("Your essay", key="assign_text", height=280, label_visibility="collapsed",
                         placeholder="Paste your essay, or bring over the text from the Writing page...")
    counter(essay)
    b_check, b_use, b_example, b_clear = st.columns([2, 1, 1, 1])
    go = b_check.button("Check against the assignment", key="assign_check", type="primary",
                        icon=":material/fact_check:", width="stretch")
    b_use.button("Use my Writing text", key="assign_use", icon=":material/content_paste:", width="stretch",
                 on_click=use_checker_text)
    b_example.button("Try an example", key="assign_example", icon=":material/lightbulb:", width="stretch",
                     on_click=load_example)
    b_clear.button("Clear All", key="assign_clear", icon=":material/delete:", width="stretch",
                   on_click=clear_keys, args=("assign_prompt", "assign_text"))

    if not go:
        return
    question = st.session_state.get("assign_prompt", "")
    if not question.strip() or not essay.strip():
        st.warning("Paste both the assignment question and your essay.")
        return

    requirements = check_assignment(question, essay)
    if not requirements:
        st.info("Couldn't find anything to check in that question. Paste the full wording, including any "
                "word count and source requirements.")
        return
    met, total = coverage(requirements)
    st.metric("Requirements covered", f"{met} / {total}",
              help="Partly covered and check-yourself items don't count as covered.")
    for group, title in GROUPS:
        rows = [r for r in requirements if r.group == group]
        if rows:
            st.markdown(f"##### {title}")
            st.markdown("".join(requirement_html(r.label, r.status, r.detail) for r in rows), unsafe_allow_html=True)
    st.caption("These checks look for signs in your wording (like “however” for evaluating, or the question's key "
               "words), so they can miss a point made in other words. Use them as a checklist, not a mark.")
    render_improved(essay, requirements)


def render_improved(essay: str, requirements) -> None:
    improved, changes, notes = improve_essay(essay, requirements)
    parts = []
    if changes:
        parts.append("Easy fixes applied: " + ", ".join(f"“{p}” → {r or 'removed'}" + (f" ×{n}" if n > 1 else "")
                                                         for p, r, n in changes) + ".")
    if notes:
        parts.append(f"{notes} [TO DO] note(s) mark where the essay still needs your own words; search for "
                     "“TO DO” and replace each one.")
    else:
        parts.append("Every requirement that could be checked is covered, so no notes were needed.")
    parts += [f"Length: {r.detail} (aim for {r.label})." for r in requirements
              if r.group == "Length" and r.label.endswith(" words") and r.status != "ok"]
    final_output("assignment", "Improved version", improved, " ".join(parts), "improved-essay.txt")
