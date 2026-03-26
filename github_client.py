import os
import hmac
import hashlib
import requests
from dotenv import load_dotenv

load_dotenv()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json",
}


def verify_signature(payload: bytes, signature: str) -> bool:
    secret = os.getenv("GITHUB_WEBHOOK_SECRET", "").encode()
    expected = "sha256=" + hmac.new(secret, payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def get_pr_diff(repo_full_name: str, pr_number: int) -> str:
    url = f"https://api.github.com/repos/{repo_full_name}/pulls/{pr_number}"
    resp = requests.get(url, headers={**HEADERS, "Accept": "application/vnd.github.v3.diff"})
    resp.raise_for_status()
    return resp.text


def get_pr_commits(repo_full_name: str, pr_number: int) -> list[dict]:
    """Return list of commits on a PR (used for iterative re-review on push)."""
    url = f"https://api.github.com/repos/{repo_full_name}/pulls/{pr_number}/commits"
    resp = requests.get(url, headers=HEADERS)
    resp.raise_for_status()
    return resp.json()


def post_inline_comment(repo_full_name: str, pr_number: int, commit_sha: str,
                        path: str, line: int, body: str) -> int:
    """Post a line-level review comment on a specific file+line in the PR diff."""
    url = f"https://api.github.com/repos/{repo_full_name}/pulls/{pr_number}/comments"
    payload = {
        "body": body,
        "commit_id": commit_sha,
        "path": path,
        "line": line,
        "side": "RIGHT",
    }
    resp = requests.post(url, headers=HEADERS, json=payload)
    return resp.status_code


def post_pr_review_comment(repo_full_name: str, pr_number: int, body: str) -> dict:
    """Post a general issue comment (summary) on the PR."""
    url = f"https://api.github.com/repos/{repo_full_name}/issues/{pr_number}/comments"
    resp = requests.post(url, headers=HEADERS, json={"body": body})
    resp.raise_for_status()
    return resp.json()


def get_existing_bot_comments(repo_full_name: str, pr_number: int) -> list[dict]:
    """Fetch existing issue comments to avoid duplicate bot summaries."""
    url = f"https://api.github.com/repos/{repo_full_name}/issues/{pr_number}/comments"
    resp = requests.get(url, headers=HEADERS)
    resp.raise_for_status()
    return [c for c in resp.json() if "🤖 AI Code Review" in c.get("body", "")]


def delete_comment(repo_full_name: str, comment_id: int):
    """Delete a previous bot comment before posting a fresh one."""
    url = f"https://api.github.com/repos/{repo_full_name}/issues/comments/{comment_id}"
    requests.delete(url, headers=HEADERS)
