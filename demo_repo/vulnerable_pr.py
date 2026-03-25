"""
demo_repo/vulnerable_pr.py
Intentionally buggy file for live demo — open a PR adding this file to trigger the bot.
"""
import sqlite3
import os

# BAD: Hardcoded secrets (OWASP A02)
SECRET_KEY = "super_secret_password_123"
DB_PASSWORD = "admin123"


def get_user(username):
    # BAD: SQL Injection (OWASP A03)
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    query = "SELECT * FROM users WHERE username = '" + username + "'"
    cursor.execute(query)
    return cursor.fetchall()


def delete_user(user_id):
    # BAD: SQL Injection via f-string
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute(f"DELETE FROM users WHERE id = {user_id}")
    conn.commit()


def run_report(report_name):
    # BAD: Command Injection (OWASP A01)
    os.system("generate_report.sh " + report_name)


def get_all_posts_with_comments():
    # BAD: N+1 query — DB query inside a loop
    conn = sqlite3.connect("blog.db")
    cursor = conn.cursor()
    posts = cursor.execute("SELECT * FROM posts").fetchall()
    result = []
    for post in posts:
        comments = cursor.execute(
            f"SELECT * FROM comments WHERE post_id = {post[0]}"
        ).fetchall()
        tags = cursor.execute(
            f"SELECT * FROM tags WHERE post_id = {post[0]}"
        ).fetchall()
        result.append({"post": post, "comments": comments, "tags": tags})
    return result


def find_duplicates(items):
    # BAD: O(n^2) nested loop
    duplicates = []
    for i in range(len(items)):
        for j in range(len(items)):
            if i != j and items[i] == items[j]:
                if items[i] not in duplicates:
                    duplicates.append(items[i])
    return duplicates


def X(a, b, c, d, e, f, g):
    # BAD: Poor naming, no type hints, bare except
    try:
        return a + b + c + d + e + f + g
    except:
        pass


class userManager:
    # BAD: Not PascalCase, mutable default argument
    def __init__(self, data=[]):
        self.data = data

    def processAll(self):
        # BAD: camelCase method
        for item in self.data:
            print(item)
