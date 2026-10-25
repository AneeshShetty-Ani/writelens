import streamlit as st

from ai_tasks import accept_feedback, feedback_task
from feedback import CATEGORIES, ISSUES_REPO, issue_url
from ui import engine


def render(user: str) -> None:
    st.markdown("### :material/feedback: Feature Request & Bug Report Hub")
    st.write(f"Suggest a feature or report a problem. This opens a pre-filled issue in the `{ISSUES_REPO}` GitHub repository.")

    with st.container(border=True):
        st.markdown("##### :material/edit_square: Submit Request or Report")
        with st.form("feedback", border=False):
            category = st.selectbox("Request / Issue Category", list(CATEGORIES))
            title = st.text_input("Title / Summary", placeholder="e.g. Add Chicago citation style")
            description = st.text_area(
                "Detailed Description & Context", height=180,
                placeholder="Describe the feature you want, or the steps that cause the bug and what you expected.",
            )
            contact = st.text_input("Your Email / GitHub Handle (Optional)", placeholder="e.g. @github_user")
            submitted = st.form_submit_button("Submit Report & Generate Issue Link", type="primary", icon=":material/send:", width="stretch")

    if not submitted:
        return
    if not title.strip():
        st.error("Please add a title.")
        return
    url = issue_url(category, title, description, contact, user)
    # only the title and description go to the AI, never the contact details
    answer = engine.run("feedback", feedback_task(category, title, description),
                        accept_feedback(title, description), category, title, description)
    st.success("Your issue is ready. Open it on GitHub and press **Create** to file it.")
    if not answer:
        st.link_button("Open issue on GitHub", url, type="primary", icon=":material/open_in_new:")
        engine.offline_note("Tidying up the report")
        return
    tidy = answer.data
    with st.container(border=True):
        st.markdown(f"##### :material/auto_awesome: {tidy['title']}")
        st.markdown(tidy["description"])
    st.caption(f"Tidied up by AI ({engine.by_line(answer)}): clearer title, spelling fixed and the details "
               "organised, with nothing added. Check it says what you meant.")
    b1, b2 = st.columns(2)
    b1.link_button("Open issue on GitHub", issue_url(category, tidy["title"], tidy["description"], contact, user),
                   type="primary", icon=":material/open_in_new:", width="stretch")
    b2.link_button("Use my own wording instead", url, icon=":material/edit:", width="stretch")
