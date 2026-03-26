import chromadb
from chromadb.utils import embedding_functions

GUIDELINES = [
    "Always use parameterized queries to prevent SQL injection (OWASP A03).",
    "Never store secrets or credentials in source code.",
    "Avoid executing shell commands with user-supplied input (OWASP A01).",
    "Use HTTPS for all external API calls; never disable SSL verification.",
    "Avoid N+1 database queries; use JOIN or batch fetching instead.",
    "Cache expensive computations; avoid repeated identical DB calls in loops.",
    "Avoid O(n^2) nested loops on large datasets; prefer hash-map lookups.",
    "Follow PEP 8: snake_case for variables/functions, PascalCase for classes.",
    "Functions should do one thing; keep them under 20 lines where possible.",
    "Always handle exceptions explicitly; never use bare `except:` clauses.",
    "Use type hints for all function signatures.",
    "Avoid mutable default arguments in Python functions.",
]

_client = chromadb.Client()
_ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
_collection = _client.get_or_create_collection("guidelines", embedding_function=_ef)

# Seed guidelines once
if _collection.count() == 0:
    _collection.add(
        documents=GUIDELINES,
        ids=[f"g{i}" for i in range(len(GUIDELINES))],
    )


def get_relevant_guidelines(code_chunk: str, n: int = 3) -> list[str]:
    results = _collection.query(query_texts=[code_chunk], n_results=n)
    return results["documents"][0]
