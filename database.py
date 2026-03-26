import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()


def get_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        dbname=os.getenv("DB_NAME", "code_reviewer"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", ""),
        port=os.getenv("DB_PORT", "5432"),
    )


def init_db():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS reviews (
            id SERIAL PRIMARY KEY,
            repo TEXT NOT NULL,
            pr_number INTEGER NOT NULL,
            severity TEXT,
            category TEXT,
            file_path TEXT,
            line_number INTEGER,
            description TEXT,
            suggested_fix TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    conn.commit()
    cur.close()
    conn.close()


def save_findings(repo: str, pr_number: int, findings: list[dict]):
    conn = get_connection()
    cur = conn.cursor()
    for f in findings:
        cur.execute("""
            INSERT INTO reviews (repo, pr_number, severity, category, file_path, line_number, description, suggested_fix)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (repo, pr_number, f.get("severity"), f.get("category"),
              f.get("file_path"), f.get("line_number"),
              f.get("description"), f.get("suggested_fix")))
    conn.commit()
    cur.close()
    conn.close()
