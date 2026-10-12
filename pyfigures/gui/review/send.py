"""Hand an exported review file off to the user's own email client.

Deliberately does NOT send anything itself — no SMTP, no stored credentials.
It only opens a compose window (via the OS's registered mail handler) with
the subject/body pre-filled, and reveals the exported file in the file
manager so it's a one-drag attach. The user still clicks Send themselves.
"""
import os
import platform
import subprocess
import urllib.parse


def build_mailto_url(recipients, subject: str, body: str) -> str:
    """*recipients* is an iterable of email addresses (may include blanks)."""
    to = ",".join(r.strip() for r in recipients if r and r.strip())
    query = urllib.parse.urlencode({"subject": subject, "body": body}, quote_via=urllib.parse.quote)
    return f"mailto:{to}?{query}"


def default_review_request_text(source_name: str, attachment_name: str):
    subject = f"Figure review: {source_name}"
    body = (
        f"Hi,\n\nCould you take a look at the attached figure ({attachment_name})?\n\n"
        "Open it in any browser (no install needed), click anywhere on the figure to "
        "leave a comment, then click \"Save reviewed copy\" and send that downloaded "
        "file back to me.\n\nThanks!"
    )
    return subject, body


def reveal_in_file_manager(path: str):
    """Best-effort: open the OS file manager with *path* pre-selected."""
    system = platform.system()
    try:
        if system == "Windows":
            subprocess.run(["explorer", "/select,", os.path.normpath(path)])
        elif system == "Darwin":
            subprocess.run(["open", "-R", path])
        else:
            subprocess.run(["xdg-open", os.path.dirname(path)])
    except Exception:
        pass
