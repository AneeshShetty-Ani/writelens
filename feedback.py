"""Turn a feature request or bug report into a pre-filled GitHub "new issue" link."""

import urllib.parse

ISSUES_REPO = "AneeshShetty-Ani/writelens"
# category -> GitHub's default label for it
CATEGORIES = {
    "Feature request (new capability or enhancement)": "enhancement",
    "Bug report (something isn't working)": "bug",
    "Question or other feedback": "question",
}
MAX_BODY = 4000  # keep the URL well under browsers' length limits


def issue_url(category: str, title: str, description: str, contact: str = "", user: str = "", repo: str = ISSUES_REPO) -> str:
    short = category.split(" (")[0]
    body = f"**Category:** {short}\n\n{description.strip()[:MAX_BODY]}"
    if contact.strip():
        body += f"\n\n**Contact:** {contact.strip()}"
    if user:
        body += f"\n\n_Sent from WriteLens by {user}._"
    query = urllib.parse.urlencode(
        {"title": f"[{short}] {title.strip()}", "body": body, "labels": CATEGORIES.get(category, "")}
    )
    return f"https://github.com/{repo}/issues/new?{query}"
