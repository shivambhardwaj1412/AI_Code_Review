import json
import os
from anthropic import Anthropic
from rag.retriever import get_relevant_guidelines

client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

SYSTEM = """You are a security code reviewer. Analyze the given Python code chunk for OWASP vulnerabilities
(SQL injection, hardcoded secrets, command injection, insecure deserialization, etc.).
Return a JSON array of findings. Each finding must have:
  - file_path (string)
  - line_number (integer, best estimate)
  - severity ("critical"|"high"|"medium"|"low")
  - category ("security")
  - description (string)
  - suggested_fix (string)
Return [] if no issues found. Return ONLY valid JSON, no prose."""


def run_security_agent(chunk: dict) -> list[dict]:
    code = chunk["content"]
    guidelines = get_relevant_guidelines(code)
    guidelines_text = "\n".join(f"- {g}" for g in guidelines)

    prompt = f"""File: {chunk['file_path']}
Relevant guidelines:
{guidelines_text}

Code:
```python
{code}
```"""

    try:
        resp = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=1024,
            system=SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        findings = json.loads(resp.content[0].text)
        for f in findings:
            f["file_path"] = chunk["file_path"]
        return findings
    except Exception as e:
        return [{"category": "security", "severity": "low", "file_path": chunk["file_path"],
                 "line_number": 0, "description": f"Security agent error: {e}", "suggested_fix": ""}]
