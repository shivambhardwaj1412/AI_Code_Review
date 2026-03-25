import sqlite3

def get_user(username):
    # BAD CODE - SQL Injection vulnerability (for demo)
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    query = "SELECT * FROM users WHERE username = '" + username + "'"
    cursor.execute(query)
    return cursor.fetchall()

def get_all_posts(user_id):
    # BAD CODE - N+1 query problem (for demo)
    conn = sqlite3.connect("blog.db")
    cursor = conn.cursor()
    posts = cursor.execute("SELECT * FROM posts").fetchall()
    for post in posts:
        # This runs a DB query inside a loop - very slow!
        comments = cursor.execute(
            f"SELECT * FROM comments WHERE post_id = {post[0]}"
        ).fetchall()
    return posts