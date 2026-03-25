import os
import re
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

# ── Tree-sitter setup ─────────────────────────────────────────────────────────
try:
    import tree_sitter_python as tspython
    from tree_sitter import Language, Parser

    PY_LANGUAGE = Language(tspython.language(), "python")
    _parser = Parser()
    _parser.set_language(PY_LANGUAGE)
    TREE_SITTER_OK = True
    log.info("tree-sitter loaded successfully")
except Exception as e:
    log.warning(f"tree-sitter unavailable, falling back to regex chunker: {e}")
    TREE_SITTER_OK = False

# ── Chunking log for 95%+ token reduction tracking (Day 4 KPI) ───────────────
_chunk_log: list[dict] = []


def _chunk_with_tree_sitter(source: str, file_path: str) -> list[dict]:
    """Semantic chunking via AST: extract top-level functions and classes only."""
    tree = _parser.parse(source.encode())
    chunks = []
    original_tokens = len(source.split())

    for node in tree.root_node.children:
        if node.type in ("function_definition", "class_definition"):
            start = node.start_point[0]
            end = node.end_point[0]
            chunk_text = "\n".join(source.splitlines()[start: end + 1])
            chunk_tokens = len(chunk_text.split())
            reduction = round((1 - chunk_tokens / max(original_tokens, 1)) * 100, 1)

            # Get node name safely
            name = "unknown"
            for child in node.children:
                if child.type == "identifier":
                    name = child.text.decode()
                    break

            log.info(f"[CHUNK] '{name}' | file={file_path} | tokens={chunk_tokens} | reduction={reduction}%")
            _chunk_log.append({
                "file": file_path, "chunk": name,
                "original_tokens": original_tokens,
                "chunk_tokens": chunk_tokens,
                "reduction_pct": reduction,
            })
            chunks.append({
                "file_path": file_path, "content": chunk_text,
                "start_line": start + 1, "end_line": end + 1,
            })
    return chunks


def _chunk_with_regex(source: str, file_path: str) -> list[dict]:
    """Fallback regex chunker for non-Python files."""
    pattern = re.compile(r"^(def |class )", re.MULTILINE)
    lines = source.splitlines()
    boundaries = [m.start() for m in pattern.finditer(source)]
    if not boundaries:
        return [{"file_path": file_path, "content": source,
                 "start_line": 1, "end_line": len(lines)}]
    chunks = []
    for i, pos in enumerate(boundaries):
        start_line = source[:pos].count("\n")
        end_line = (source[:boundaries[i + 1]].count("\n") - 1
                    if i + 1 < len(boundaries) else len(lines))
        content = "\n".join(lines[start_line:end_line])
        chunks.append({"file_path": file_path, "content": content,
                        "start_line": start_line + 1, "end_line": end_line})
    return chunks


def parse_diff_to_chunks(diff: str) -> list[dict]:
    """Parse unified diff → semantic code chunks via tree-sitter AST."""
    chunks = []
    current_file = None
    current_lines: list[str] = []

    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            if current_file and current_lines:
                source = "\n".join(current_lines)
                if TREE_SITTER_OK and current_file.endswith(".py"):
                    chunks.extend(_chunk_with_tree_sitter(source, current_file))
                else:
                    chunks.extend(_chunk_with_regex(source, current_file))
            current_file = line[6:]
            current_lines = []
        elif line.startswith("+") and not line.startswith("+++"):
            current_lines.append(line[1:])

    # flush last file
    if current_file and current_lines:
        source = "\n".join(current_lines)
        if TREE_SITTER_OK and current_file.endswith(".py"):
            chunks.extend(_chunk_with_tree_sitter(source, current_file))
        else:
            chunks.extend(_chunk_with_regex(source, current_file))

    log.info(f"[PARSE] Total semantic chunks from diff: {len(chunks)}")
    return chunks


# ── Format findings as rich GitHub Markdown (Day 5 KPI) ──────────────────────
def _format_findings_markdown(findings: list[dict]) -> str:
    severity_emoji = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🔵"}
    lines = [
        "## 🤖 AI Code Review — Automated Analysis\n",
        "> *Powered by LangGraph multi-agent pipeline (Security · Performance · Style)*\n",
        f"**{len(findings)} issue(s) found**, sorted by severity.\n",
        "---\n",
    ]
    for i, f in enumerate(findings, 1):
        sev = f.get("severity", "low")
        emoji = severity_emoji.get(sev, "⚪")
        cat = f.get("category", "").capitalize()
        fp = f.get("file_path", "")
        ln = f.get("line_number", "?")
        desc = f.get("description", "")
        fix = f.get("suggested_fix", "")
        lines.append(
            f"### {i}. {emoji} `[{sev.upper()}]` {cat} — `{fp}` line {ln}\n\n"
            f"**Issue:** {desc}\n\n"
            f"**Suggested Fix:**\n```python\n{fix}\n```\n\n---\n"
        )
    lines.append(
        "\n> 💡 *This review only covers changed sections. "
        "Push a fix and the bot will re-evaluate the updated diff.*"
    )
    return "\n".join(lines)


# ── Background PR processing task ─────────────────────────────────────────────
def process_pr(repo_full_name: str, pr_number: int, commit_sha: str, action: str):
    try:
        from github_client import (get_pr_diff, post_pr_review_comment,
                                   post_inline_comment, get_existing_bot_comments,
                                   delete_comment)
        from agents.orchestrator import run_review
        from database import save_findings

        log.info(f"[PR #{pr_number}] action={action} repo={repo_full_name} sha={commit_sha[:7]}")

        # Day 6: iterative re-review — delete old bot comment on synchronize
        if action == "synchronize":
            old_comments = get_existing_bot_comments(repo_full_name, pr_number)
            for c in old_comments:
                delete_comment(repo_full_name, c["id"])
                log.info(f"[PR #{pr_number}] Deleted stale bot comment {c['id']}")

        diff = get_pr_diff(repo_full_name, pr_number)
        log.info(f"[PR #{pr_number}] Diff fetched: {len(diff)} chars")
        print(f"\n{'='*60}\nRAW DIFF for PR #{pr_number}:\n{diff[:2000]}\n{'='*60}\n")

        chunks = parse_diff_to_chunks(diff)
        if not chunks:
            log.info(f"[PR #{pr_number}] No Python chunks found — skipping review.")
            return

        findings = run_review(chunks)
        log.info(f"[PR #{pr_number}] Review complete: {len(findings)} findings")

        # Save to DB (graceful skip if DB not configured)
        try:
            save_findings(repo_full_name, pr_number, findings)
        except Exception as db_err:
            log.warning(f"[PR #{pr_number}] DB save skipped: {db_err}")

        if not findings:
            post_pr_review_comment(repo_full_name, pr_number,
                                   "## 🤖 AI Code Review\n\n✅ No issues found in this diff. Great work!")
            return

        # Day 5: Post inline line-level comments
        for f in findings:
            ln = f.get("line_number")
            fp = f.get("file_path", "")
            if ln and ln > 0 and fp:
                sev = f.get("severity", "low")
                emoji = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🔵"}.get(sev, "⚪")
                body = (
                    f"{emoji} **[{sev.upper()}] {f.get('category','').capitalize()}**\n\n"
                    f"{f.get('description','')}\n\n"
                    f"**Fix:**\n```python\n{f.get('suggested_fix','')}\n```"
                )
                status = post_inline_comment(repo_full_name, pr_number, commit_sha, fp, ln, body)
                log.info(f"[PR #{pr_number}] Inline comment on {fp}:{ln} → HTTP {status}")

        # Post summary comment
        summary = _format_findings_markdown(findings)
        post_pr_review_comment(repo_full_name, pr_number, summary)
        log.info(f"[PR #{pr_number}] Summary comment posted.")

    except Exception as e:
        log.error(f"[PR #{pr_number}] process_pr FAILED: {e}", exc_info=True)


# ── App lifecycle ─────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        from database import init_db
        init_db()
        log.info("PostgreSQL database initialized")
    except Exception as e:
        log.warning(f"DB init skipped (configure .env to enable): {e}")
    yield


app = FastAPI(title="AI Code Reviewer", version="1.0.0", lifespan=lifespan)


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {
        "status": "AI Code Reviewer running ✅",
        "tree_sitter": TREE_SITTER_OK,
        "endpoints": ["/webhook", "/review/local", "/dashboard", "/chunk-log"],
    }


@app.post("/webhook")
async def webhook(request: Request, background_tasks: BackgroundTasks):
    """GitHub webhook endpoint — listens for PR events."""
    payload_bytes = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "")

    from github_client import verify_signature
    secret = os.getenv("GITHUB_WEBHOOK_SECRET", "")
    if secret and not verify_signature(payload_bytes, signature):
        log.warning("Webhook signature mismatch — rejected")
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    event = request.headers.get("X-GitHub-Event", "")
    log.info(f"[WEBHOOK] event={event}")

    if event != "pull_request":
        return {"status": "ignored", "event": event}

    payload = await request.json()
    action = payload.get("action", "")
    log.info(f"[WEBHOOK] PR action={action}")

    if action not in ("opened", "synchronize", "reopened"):
        return {"status": "ignored", "action": action}

    repo_full_name = payload["repository"]["full_name"]
    pr_number = payload["pull_request"]["number"]
    commit_sha = payload["pull_request"]["head"]["sha"]

    log.info(f"[WEBHOOK] Queuing review: PR #{pr_number} in {repo_full_name}")
    background_tasks.add_task(process_pr, repo_full_name, pr_number, commit_sha, action)
    return {"status": "queued", "pr": pr_number, "repo": repo_full_name, "action": action}


@app.post("/review/local")
async def review_local(request: Request):
    """Dev/demo endpoint: POST a raw unified diff to get a review without GitHub."""
    body = await request.body()
    diff = body.decode()
    if not diff.strip():
        return {"error": "Empty diff body"}
    chunks = parse_diff_to_chunks(diff)
    if not chunks:
        return {"findings": [], "chunks": 0, "message": "No Python chunks found in diff."}
    from agents.orchestrator import run_review
    findings = run_review(chunks)
    return {
        "findings": findings,
        "total": len(findings),
        "chunks_analyzed": len(chunks),
        "markdown_preview": _format_findings_markdown(findings),
    }


@app.get("/chunk-log")
def chunk_log():
    """Day 4 KPI: Returns the token reduction log for all chunks processed."""
    if not _chunk_log:
        return {"message": "No chunks processed yet.", "log": []}
    avg_reduction = round(sum(c["reduction_pct"] for c in _chunk_log) / len(_chunk_log), 1)
    return {
        "total_chunks": len(_chunk_log),
        "average_token_reduction_pct": avg_reduction,
        "target_pct": 95,
        "target_met": avg_reduction >= 95,
        "log": _chunk_log,
    }


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
    """Day 5: HTML dashboard showing review trends."""
    from dashboard import build_dashboard_html
    try:
        from database import get_connection
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT severity, category, COUNT(*) as count
            FROM reviews GROUP BY severity, category ORDER BY severity
        """)
        rows = cur.fetchall()
        cur.close()
        conn.close()
        data = [{"severity": r[0], "category": r[1], "count": r[2]} for r in rows]
    except Exception:
        data = []
    return build_dashboard_html(data)
