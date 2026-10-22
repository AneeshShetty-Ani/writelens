import streamlit as st

from feedback import CATEGORIES, ISSUES_REPO, issue_url


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
    st.success("Your issue is ready. Open it on GitHub and press **Create** to file it.")
    st.link_button("Open issue on GitHub", url, type="primary", icon=":material/open_in_new:")
