from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def root():
    return {"status": "AI Code Reviewer - Day 2 skeleton running!"}

# uvicorn main:app --reload(To see code running)
# Biswajit will complete the /webhook endpoint

import os

os.system("pip install fastapi uvicorn python-dotenv PyGithub psycopg2-binary requests langchain chromadb sentence-transformers tree-sitter tree-sitter-python anthropic")

from fastapi import FastAPI, Request, Header, HTTPException
from dotenv import load_dotenv
import hmac
import hashlib
import os
import json

load_dotenv()

app = FastAPI(title="AI Code Reviewer", version="1.0")

WEBHOOK_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET", "")
GITHUB_TOKEN   = os.getenv("GITHUB_TOKEN", "")


# ─────────────────────────────────────────
# HEALTH CHECK
# ─────────────────────────────────────────
@app.get("/")
def root():
    return {"status": "AI Code Reviewer is running!", "day": 2}


# ─────────────────────────────────────────
# WEBHOOK RECEIVER
# ─────────────────────────────────────────
@app.post("/webhook")
async def github_webhook(
    request: Request,
    x_github_event:      str = Header(None),
    x_hub_signature_256: str = Header(None),
):
    # 1. Read the raw body bytes
    body = await request.body()

    # 2. Verify the webhook signature (proves it really came from GitHub)
    verify_signature(body, x_hub_signature_256)

    # 3. Parse the JSON payload
    try:
        payload = json.loads(body)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    # 4. Only process pull_request events — ignore everything else
    if x_github_event != "pull_request":
        print(f"Ignored event: {x_github_event}")
        return {"message": f"Ignored event: {x_github_event}"}

    # 5. Extract key info from the payload
    action     = payload.get("action", "")
    pr_number  = payload["pull_request"]["number"]
    pr_title   = payload["pull_request"]["title"]
    repo_name  = payload["repository"]["full_name"]
    pr_author  = payload["pull_request"]["user"]["login"]
    pr_url     = payload["pull_request"]["html_url"]

    print("\n" + "="*60)
    print("NEW PULL REQUEST EVENT RECEIVED!")
    print(f"  Repo    : {repo_name}")
    print(f"  PR #    : {pr_number}")
    print(f"  Title   : {pr_title}")
    print(f"  Author  : {pr_author}")
    print(f"  Action  : {action}")
    print(f"  URL     : {pr_url}")
    print("="*60)

    # 6. Only fetch the diff when a PR is opened or updated
    if action in ["opened", "synchronize"]:
        diff = fetch_pr_diff(repo_name, pr_number)

        if diff:
            print("\n--- RAW DIFF (first 2000 characters) ---")
            print(diff[:2000])
            print("--- END OF DIFF PREVIEW ---\n")

            # Save to database
            try:
                from database import save_pr_event
                save_pr_event(repo_name, pr_number, pr_title, diff)
                print(f"PR #{pr_number} saved to database successfully!")
            except Exception as e:
                print(f"Database save skipped (will set up later): {e}")

        else:
            print("WARNING: Could not fetch diff — check your GITHUB_TOKEN")

    return {"message": "Webhook processed successfully", "pr": pr_number}


# ─────────────────────────────────────────
# HELPER: VERIFY GITHUB SIGNATURE
# ─────────────────────────────────────────
def verify_signature(body: bytes, signature_header: str):
    """
    GitHub signs every webhook with our secret key.
    We recompute the signature and compare — if they don't
    match, someone is sending us fake requests.
    """
    if not WEBHOOK_SECRET:
        print("WARNING: No webhook secret set — skipping verification")
        return

    if not signature_header:
        raise HTTPException(
            status_code=401,
            detail="Missing X-Hub-Signature-256 header"
        )

    expected_signature = "sha256=" + hmac.new(
        WEBHOOK_SECRET.encode("utf-8"),
        body,
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(expected_signature, signature_header):
        raise HTTPException(
            status_code=401,
            detail="Invalid webhook signature — request rejected"
        )

    print("Webhook signature verified OK")


# ─────────────────────────────────────────
# HELPER: FETCH THE PR DIFF FROM GITHUB
# ─────────────────────────────────────────
def fetch_pr_diff(repo_full_name: str, pr_number: int) -> str:
    """
    Calls the GitHub API to get the raw diff of a pull request.
    The diff shows exactly what lines were added/removed.
    """
    import requests

    url = f"https://api.github.com/repos/{repo_full_name}/pulls/{pr_number}"

    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3.diff",
    }

    print(f"Fetching diff from: {url}")

    try:
        response = requests.get(url, headers=headers, timeout=10)

        if response.status_code == 200:
            print(f"Diff fetched successfully! Size: {len(response.text)} characters")
            return response.text

        elif response.status_code == 401:
            print("ERROR 401: GitHub token is invalid or expired")
            return ""

        elif response.status_code == 404:
            print(f"ERROR 404: PR #{pr_number} not found in {repo_full_name}")
            return ""

        else:
            print(f"ERROR {response.status_code}: {response.text}")
            return ""

    except requests.exceptions.Timeout:
        print("ERROR: Request to GitHub timed out")
        return ""

    except requests.exceptions.ConnectionError:
        print("ERROR: Could not connect to GitHub API")
        return ""


# ─────────────────────────────────────────
# RUN THE SERVER
# ─────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)