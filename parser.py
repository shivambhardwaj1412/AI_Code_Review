import re
from dataclasses import dataclass


# ─────────────────────────────────────────
# DATA STRUCTURE
# A CodeChunk holds one extracted function or class
# ─────────────────────────────────────────
@dataclass
class CodeChunk:
    chunk_type:  str   # "function" or "class"
    name:        str   # e.g. "get_user" or "UserService"
    code:        str   # the full source code of that function/class
    start_line:  int   # which line it starts on
    end_line:    int   # which line it ends on
    file_path:   str   # which file it came from


# ─────────────────────────────────────────
# MAIN ENTRY POINT
# Call this with a raw GitHub diff string
# Returns a list of CodeChunk objects
# ─────────────────────────────────────────
def parse_diff_into_chunks(diff_text: str) -> list[CodeChunk]:
    """
    Takes a raw GitHub PR diff and returns a list of
    CodeChunk objects — one per changed function or class.

    Example input:
        diff --git a/app/users.py b/app/users.py
        +def get_user(username):
        +    query = "SELECT * FROM users"
        ...

    Example output:
        [CodeChunk(name='get_user', chunk_type='function', ...)]
    """
    print("\n" + "="*55)
    print("PARSER: Starting diff analysis...")
    print("="*55)

    all_chunks = []

    # Step 1: Split the diff into per-file sections
    file_sections = split_diff_by_file(diff_text)
    print(f"PARSER: Found {len(file_sections)} changed file(s) in diff")

    for file_path, file_diff in file_sections.items():
        print(f"\nPARSER: Processing file -> {file_path}")

        # Step 2: Only process Python files for now (MVP scope)
        if not file_path.endswith(".py"):
            print(f"  Skipping (not a .py file)")
            continue

        # Step 3: Extract the added/changed lines from the diff
        changed_code = extract_changed_lines(file_diff)

        if not changed_code.strip():
            print(f"  No added lines found — skipping")
            continue

        print(f"  Extracted {len(changed_code.splitlines())} changed lines")

        # Step 4: Parse the changed code into chunks
        chunks = extract_chunks_from_code(changed_code, file_path)
        print(f"  Found {len(chunks)} chunk(s): "
              f"{[c.name for c in chunks]}")

        all_chunks.extend(chunks)

    print(f"\nPARSER: Done! Total chunks extracted: {len(all_chunks)}")
    print("="*55 + "\n")
    return all_chunks


# ─────────────────────────────────────────
# STEP 1: SPLIT DIFF INTO FILE SECTIONS
# A diff can touch many files — split them
# ─────────────────────────────────────────
def split_diff_by_file(diff_text: str) -> dict[str, str]:
    """
    A raw diff looks like:

        diff --git a/file1.py b/file1.py
        --- a/file1.py
        +++ b/file1.py
        @@ ... @@
        +def foo(): ...

        diff --git a/file2.py b/file2.py
        ...

    This function splits it into:
        { "file1.py": "<diff for file1>", "file2.py": "<diff for file2>" }
    """
    file_sections = {}
    current_file  = None
    current_lines = []

    for line in diff_text.splitlines():
        # Detect the start of a new file section
        if line.startswith("diff --git"):
            # Save the previous file's content
            if current_file:
                file_sections[current_file] = "\n".join(current_lines)

            # Extract the file path from: "diff --git a/path b/path"
            parts = line.split(" ")
            if len(parts) >= 4:
                # Take the "b/..." path and strip the "b/" prefix
                raw_path    = parts[3]
                current_file = raw_path[2:] if raw_path.startswith("b/") else raw_path
            current_lines = []
        else:
            current_lines.append(line)

    # Don't forget the last file
    if current_file:
        file_sections[current_file] = "\n".join(current_lines)

    return file_sections


# ─────────────────────────────────────────
# STEP 2: EXTRACT ADDED LINES FROM DIFF
# Lines starting with + are new/changed code
# ─────────────────────────────────────────
def extract_changed_lines(file_diff: str) -> str:
    """
    In a diff, lines starting with + are additions.
    Lines starting with - are deletions (we skip those).
    Lines with no prefix are unchanged context lines.

    We keep:
      - All + lines (new code)
      - Context lines (unchanged) — helps tree-sitter understand structure

    We skip:
      - Lines starting with +++ (that's the filename header, not code)
      - Lines starting with - (deleted code)
      - Lines starting with @@ (chunk headers)
    """
    kept_lines = []

    for line in file_diff.splitlines():
        if line.startswith("+++") or line.startswith("---"):
            continue                         # skip file headers
        elif line.startswith("@@"):
            continue                         # skip hunk headers
        elif line.startswith("+"):
            kept_lines.append(line[1:])      # strip the leading +
        elif line.startswith("-"):
            continue                         # skip deleted lines
        else:
            kept_lines.append(line)          # keep context lines

    return "\n".join(kept_lines)


# ─────────────────────────────────────────
# STEP 3: EXTRACT FUNCTIONS & CLASSES
# Uses tree-sitter for smart AST parsing
# Falls back to regex if tree-sitter fails
# ─────────────────────────────────────────
def extract_chunks_from_code(
    source_code: str,
    file_path:   str
) -> list[CodeChunk]:
    """
    Tries tree-sitter first (smart, understands code structure).
    Falls back to regex if tree-sitter isn't available.
    """
    try:
        return _extract_with_treesitter(source_code, file_path)
    except Exception as e:
        print(f"  tree-sitter failed ({e}), using regex fallback")
        return _extract_with_regex(source_code, file_path)


# ─────────────────────────────────────────
# TREE-SITTER PARSER
# Builds a syntax tree and walks it
# ─────────────────────────────────────────
def _extract_with_treesitter(
    source_code: str,
    file_path:   str
) -> list[CodeChunk]:
    """
    tree-sitter builds an Abstract Syntax Tree (AST) of the code.
    An AST is like a map of the code — it knows exactly where
    every function and class starts and ends.

    We walk the tree looking for:
      - function_definition nodes  → functions
      - class_definition nodes     → classes
    """
    from tree_sitter import Language, Parser
    import tree_sitter_python as tspython

    # Build the Python language parser
    PY_LANGUAGE = Language(tspython.language())
    parser      = Parser(PY_LANGUAGE)

    # Parse the source code into a syntax tree
    tree        = parser.parse(bytes(source_code, "utf-8"))
    root_node   = tree.root_node

    chunks      = []
    lines       = source_code.splitlines()

    # Walk every node in the syntax tree
    def walk(node):
        if node.type in ("function_definition", "class_definition"):
            # Get the name of this function/class
            name_node = node.child_by_field_name("name")
            name      = name_node.text.decode("utf-8") if name_node else "unknown"

            # Get the start and end line numbers
            start_line = node.start_point[0]
            end_line   = node.end_point[0]

            # Extract the actual source code lines
            chunk_lines = lines[start_line : end_line + 1]
            chunk_code  = "\n".join(chunk_lines)

            chunk_type  = (
                "function" if node.type == "function_definition"
                else "class"
            )

            chunks.append(CodeChunk(
                chunk_type = chunk_type,
                name       = name,
                code       = chunk_code,
                start_line = start_line + 1,   # convert to 1-based
                end_line   = end_line   + 1,
                file_path  = file_path,
            ))

        # Recurse into child nodes
        for child in node.children:
            walk(child)

    walk(root_node)
    return chunks


# ─────────────────────────────────────────
# REGEX FALLBACK PARSER
# Used if tree-sitter is not installed
# Less accurate but always works
# ─────────────────────────────────────────
def _extract_with_regex(
    source_code: str,
    file_path:   str
) -> list[CodeChunk]:
    """
    Simple regex-based fallback.
    Looks for lines that start with 'def ' or 'class '.
    Not as accurate as tree-sitter but good enough for demo.
    """
    chunks = []
    lines  = source_code.splitlines()

    # Patterns to detect function and class definitions
    func_pattern  = re.compile(r"^(def\s+(\w+)\s*\()")
    class_pattern = re.compile(r"^(class\s+(\w+)[\s:(])")

    i = 0
    while i < len(lines):
        line = lines[i]

        func_match  = func_pattern.match(line)
        class_match = class_pattern.match(line)

        if func_match or class_match:
            is_func    = bool(func_match)
            match      = func_match if is_func else class_match
            name       = match.group(2)
            start_line = i

            # Collect lines until the next def/class at the same indent
            # or until end of file
            block_lines = [line]
            j = i + 1
            while j < len(lines):
                next_line = lines[j]
                # Stop if we hit another top-level def or class
                if (func_pattern.match(next_line) or
                        class_pattern.match(next_line)):
                    if not next_line.startswith((" ", "\t")):
                        break
                block_lines.append(next_line)
                j += 1

            end_line = start_line + len(block_lines) - 1

            chunks.append(CodeChunk(
                chunk_type = "function" if is_func else "class",
                name       = name,
                code       = "\n".join(block_lines),
                start_line = start_line + 1,
                end_line   = end_line   + 1,
                file_path  = file_path,
            ))
            i = j
        else:
            i += 1

    return chunks


# ─────────────────────────────────────────
# UTILITY: PRETTY PRINT CHUNKS
# Useful for debugging during the demo
# ─────────────────────────────────────────
def print_chunks(chunks: list[CodeChunk]):
    if not chunks:
        print("No chunks found.")
        return

    for i, chunk in enumerate(chunks, 1):
        print(f"\n{'─'*55}")
        print(f"  Chunk #{i}")
        print(f"  Type  : {chunk.chunk_type}")
        print(f"  Name  : {chunk.name}")
        print(f"  File  : {chunk.file_path}")
        print(f"  Lines : {chunk.start_line} → {chunk.end_line}")
        print(f"{'─'*55}")
        print(chunk.code)


# ─────────────────────────────────────────
# QUICK TEST — run: python parser.py
# ─────────────────────────────────────────
if __name__ == "__main__":

    # Simulate a real GitHub PR diff
    sample_diff = """\
diff --git a/app/users.py b/app/users.py
index 0000000..1111111 100644
--- a/app/users.py
+++ b/app/users.py
@@ -0,0 +1,30 @@
+import sqlite3
+
+def get_user(username):
+    # Vulnerable to SQL injection!
+    conn = sqlite3.connect("users.db")
+    cursor = conn.cursor()
+    query = "SELECT * FROM users WHERE username = '" + username + "'"
+    cursor.execute(query)
+    return cursor.fetchall()
+
+def hash_password(password):
+    # Weak hashing — not secure
+    return password[::-1]
+
+class UserService:
+    def __init__(self):
+        self.db = sqlite3.connect("users.db")
+
+    def create_user(self, username, password):
+        hashed = hash_password(password)
+        self.db.execute(
+            f"INSERT INTO users VALUES ('{username}', '{hashed}')"
+        )
+        self.db.commit()
"""

    print("Running parser on sample diff...\n")
    chunks = parse_diff_into_chunks(sample_diff)
    print_chunks(chunks)
    print(f"\nTotal token reduction: sent {len(chunks)} chunks "
          f"instead of entire file")