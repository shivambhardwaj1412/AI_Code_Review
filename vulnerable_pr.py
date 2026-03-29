"""
demo_repo/vulnerable_pr.py
Intentionally buggy file for live demo — open a PR adding this file to trigger the bot.
"""
import sqlite3
import os
import hashlib
import pickle
import subprocess

# BAD: Hardcoded secrets (OWASP A02)
SECRET_KEY = "super_secret_password_123"
DB_PASSWORD = "admin123"
API_KEY = "sk-prod-9876543210abcdef"
AWS_SECRET = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"


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


def login(username, password):
    # BAD: SQL Injection in login query
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username = '" + username + "' AND password = '" + password + "'")
    return cursor.fetchone()


def hash_password(password):
    # BAD: MD5 is cryptographically broken
    return hashlib.md5(password.encode()).hexdigest()


def load_user_data(filepath):
    # BAD: Pickle deserialization of untrusted data (OWASP A08)
    with open(filepath, "rb") as f:
        return pickle.load(f)


def read_user_file(filename):
    # BAD: Path traversal — user controls filename directly
    with open("/var/data/" + filename, "r") as f:
        return f.read()


def run_report(report_name):
    # BAD: Command Injection (OWASP A01)
    os.system("generate_report.sh " + report_name)


def run_script(script_name):
    # BAD: Command Injection via subprocess shell=True
    subprocess.call("python scripts/" + script_name, shell=True)


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


def get_all_users_with_orders():
    # BAD: N+1 query — 2 extra queries per user
    conn = sqlite3.connect("app.db")
    cursor = conn.cursor()
    users = cursor.execute("SELECT * FROM users").fetchall()
    result = []
    for user in users:
        orders = cursor.execute(
            f"SELECT * FROM orders WHERE user_id = {user[0]}"
        ).fetchall()
        payments = cursor.execute(
            f"SELECT * FROM payments WHERE user_id = {user[0]}"
        ).fetchall()
        result.append({"user": user, "orders": orders, "payments": payments})
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


def compute_matrix(matrix):
    # BAD: O(n^3) triple nested loop
    n = len(matrix)
    result = [[0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            for k in range(n):
                result[i][j] += matrix[i][k] * matrix[k][j]
    return result


def X(a, b, c, d, e, f, g):
    # BAD: Poor naming, no type hints, bare except
    try:
        return a + b + c + d + e + f + g
    except:
        pass


def D(x, y, z):
    # BAD: Single letter name, bare except, no return type
    try:
        return x / (y - z)
    except:
        return 0


class userManager:
    # BAD: Not PascalCase, mutable default argument
    def __init__(self, data=[]):
        self.data = data

    def processAll(self):
        # BAD: camelCase method
        for item in self.data:
            print(item)

    def filterItems(self, threshold):
        # BAD: camelCase, O(n^2) nested loop
        result = []
        for i in self.data:
            for j in self.data:
                if i == j and i > threshold:
                    result.append(i)
        return result


class apiHandler:
    # BAD: Not PascalCase, mutable default argument
    def __init__(self, config=[]):
        self.config = config

    def processRequest(self, req):
        # BAD: camelCase, bare except, no return type hint
        try:
            return req["data"]
        except:
            pass
