import logging
import time
from typing import TypedDict
from concurrent.futures import ThreadPoolExecutor, as_completed
from langgraph.graph import StateGraph, END
from agents.security_agent import run_security_agent
from agents.performance_agent import run_performance_agent
from agents.style_agent import run_style_agent

log = logging.getLogger(__name__)
SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


class ReviewState(TypedDict):
    chunks: list[dict]
    security_findings: list[dict]
    performance_findings: list[dict]
    style_findings: list[dict]
    final_findings: list[dict]


# ── Agent runner with retry for rate limits ───────────────────────────────────

def _run_agent_safe(agent_fn, chunk: dict, retries: int = 2) -> list[dict]:
    """Run an agent with exponential backoff on rate limit errors."""
    for attempt in range(retries + 1):
        try:
            return agent_fn(chunk)
        except Exception as e:
            err = str(e).lower()
            if "rate_limit" in err or "overloaded" in err or "529" in err:
                wait = 2 ** attempt
                log.warning(f"Rate limit hit on {agent_fn.__name__}, retrying in {wait}s...")
                time.sleep(wait)
            else:
                log.error(f"{agent_fn.__name__} failed on {chunk.get('file_path')}: {e}")
                return []
    return []


# ── LangGraph nodes ───────────────────────────────────────────────────────────

def security_node(state: ReviewState) -> ReviewState:
    findings = []
    for chunk in state["chunks"]:
        findings.extend(_run_agent_safe(run_security_agent, chunk))
    log.info(f"[Security] {len(findings)} findings")
    return {**state, "security_findings": findings}


def performance_node(state: ReviewState) -> ReviewState:
    findings = []
    for chunk in state["chunks"]:
        findings.extend(_run_agent_safe(run_performance_agent, chunk))
    log.info(f"[Performance] {len(findings)} findings")
    return {**state, "performance_findings": findings}


def style_node(state: ReviewState) -> ReviewState:
    findings = []
    for chunk in state["chunks"]:
        findings.extend(_run_agent_safe(run_style_agent, chunk))
    log.info(f"[Style] {len(findings)} findings")
    return {**state, "style_findings": findings}


def orchestrator_node(state: ReviewState) -> ReviewState:
    """
    Orchestrator: merge all agent findings, deduplicate, and prioritize by severity.
    Dedup key: (file_path, line_number, category) — keeps highest severity entry.
    """
    all_findings = (
        state["security_findings"]
        + state["performance_findings"]
        + state["style_findings"]
    )
    log.info(f"[Orchestrator] Raw findings before dedup: {len(all_findings)}")

    seen: dict[tuple, dict] = {}
    for f in all_findings:
        key = (f.get("file_path"), f.get("line_number"), f.get("category"))
        if key not in seen:
            seen[key] = f
        else:
            # Keep the higher severity entry
            if SEVERITY_ORDER.get(f.get("severity", "low"), 3) < \
               SEVERITY_ORDER.get(seen[key].get("severity", "low"), 3):
                seen[key] = f

    prioritized = sorted(
        seen.values(),
        key=lambda x: SEVERITY_ORDER.get(x.get("severity", "low"), 3),
    )
    log.info(f"[Orchestrator] After dedup+sort: {len(prioritized)} findings")
    return {**state, "final_findings": prioritized}


# ── Build LangGraph state machine ─────────────────────────────────────────────

def _build_graph():
    graph = StateGraph(ReviewState)
    graph.add_node("security", security_node)
    graph.add_node("performance", performance_node)
    graph.add_node("style", style_node)
    graph.add_node("orchestrator", orchestrator_node)

    graph.set_entry_point("security")
    graph.add_edge("security", "performance")
    graph.add_edge("performance", "style")
    graph.add_edge("style", "orchestrator")
    graph.add_edge("orchestrator", END)
    return graph.compile()


_graph = _build_graph()


def run_review(chunks: list[dict]) -> list[dict]:
    """
    Main entry point for the LangGraph pipeline.
    Takes semantic code chunks, runs all agents, returns deduplicated+prioritized findings.
    """
    if not chunks:
        return []
    log.info(f"[Pipeline] Starting review of {len(chunks)} chunk(s)")
    initial_state: ReviewState = {
        "chunks": chunks,
        "security_findings": [],
        "performance_findings": [],
        "style_findings": [],
        "final_findings": [],
    }
    result = _graph.invoke(initial_state)
    return result["final_findings"]
