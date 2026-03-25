import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from agents.security_agent import run_security_agent
from agents.performance_agent import run_performance_agent
from agents.style_agent import run_style_agent
from agents.orchestrator import run_review

SQL_INJECTION_CODE = '''
def get_user(username):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    query = "SELECT * FROM users WHERE username = \'" + username + "\'"
    cursor.execute(query)
    return cursor.fetchall()
'''

N_PLUS_ONE_CODE = '''
def get_all_posts():
    posts = cursor.execute("SELECT * FROM posts").fetchall()
    for post in posts:
        comments = cursor.execute(
            f"SELECT * FROM comments WHERE post_id = {post[0]}"
        ).fetchall()
    return posts
'''

STYLE_BAD_CODE = '''
def X(a,b,c):
    try:
        return a+b+c
    except:
        pass
'''


def test_security_catches_sql_injection():
    chunk = {"file_path": "tests/vulnerable_code.py", "content": SQL_INJECTION_CODE}
    findings = run_security_agent(chunk)
    assert isinstance(findings, list), "Should return a list"
    categories = [f.get("category") for f in findings]
    severities = [f.get("severity") for f in findings]
    print(f"[Security] Findings: {len(findings)}")
    for f in findings:
        print(f"  [{f.get('severity')}] {f.get('description')}")
    assert any(c == "security" for c in categories), "Expected security findings"
    assert any(s in ("critical", "high") for s in severities), "SQL injection should be critical/high"
    print("✅ test_security_catches_sql_injection PASSED")


def test_performance_catches_n_plus_one():
    chunk = {"file_path": "tests/vulnerable_code.py", "content": N_PLUS_ONE_CODE}
    findings = run_performance_agent(chunk)
    assert isinstance(findings, list), "Should return a list"
    print(f"[Performance] Findings: {len(findings)}")
    for f in findings:
        print(f"  [{f.get('severity')}] {f.get('description')}")
    assert len(findings) > 0, "Expected N+1 performance finding"
    print("✅ test_performance_catches_n_plus_one PASSED")


def test_style_catches_violations():
    chunk = {"file_path": "tests/vulnerable_code.py", "content": STYLE_BAD_CODE}
    findings = run_style_agent(chunk)
    assert isinstance(findings, list), "Should return a list"
    print(f"[Style] Findings: {len(findings)}")
    for f in findings:
        print(f"  [{f.get('severity')}] {f.get('description')}")
    assert len(findings) > 0, "Expected style findings"
    print("✅ test_style_catches_violations PASSED")


def test_orchestrator_deduplication():
    chunks = [
        {"file_path": "tests/vulnerable_code.py", "content": SQL_INJECTION_CODE},
        {"file_path": "tests/vulnerable_code.py", "content": N_PLUS_ONE_CODE},
    ]
    findings = run_review(chunks)
    assert isinstance(findings, list)
    print(f"[Orchestrator] Total deduplicated findings: {len(findings)}")
    severities = [f.get("severity") for f in findings]
    # Verify sorted by severity (critical/high before low)
    order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    ranks = [order.get(s, 3) for s in severities]
    assert ranks == sorted(ranks), "Findings should be sorted by severity"
    print("✅ test_orchestrator_deduplication PASSED")


if __name__ == "__main__":
    print("=" * 60)
    print("Running AI Code Review Agent Tests")
    print("=" * 60)
    test_security_catches_sql_injection()
    test_performance_catches_n_plus_one()
    test_style_catches_violations()
    test_orchestrator_deduplication()
    print("\n✅ All tests passed!")
