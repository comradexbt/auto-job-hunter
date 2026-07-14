"""
Database Manager (Phase 1)
Handles SQLite operations for tracking applied jobs and preventing duplicates.
"""
import sqlite3
import datetime
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "jobs.db")


def get_connection():
    """Get a thread-safe database connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def init_db():
    """Initialize the database and create tables if they don't exist."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS applied_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_title TEXT NOT NULL,
            company TEXT NOT NULL,
            url TEXT NOT NULL UNIQUE,
            status TEXT NOT NULL DEFAULT 'applied',
            date_applied TEXT NOT NULL DEFAULT (datetime('now')),
            notes TEXT DEFAULT ''
        )
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_applied_jobs_url 
        ON applied_jobs(url)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_applied_jobs_date 
        ON applied_jobs(date_applied)
    """)
    conn.commit()
    conn.close()


def is_job_applied(url: str) -> bool:
    """Check if a job URL has already been applied to."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM applied_jobs WHERE url = ?", (url,))
    result = cursor.fetchone()
    conn.close()
    return result is not None


def save_job(title: str, company: str, url: str, status: str = "applied") -> bool:
    """Save a job application to the database. Returns True if successful."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO applied_jobs (job_title, company, url, status) VALUES (?, ?, ?, ?)",
            (title, company, url, status),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def get_today_stats() -> int:
    """Get the number of jobs applied to today."""
    conn = get_connection()
    cursor = conn.cursor()
    today = datetime.date.today().isoformat()
    cursor.execute(
        "SELECT COUNT(*) FROM applied_jobs WHERE date(date_applied) = ?",
        (today,),
    )
    count = cursor.fetchone()[0]
    conn.close()
    return count


def get_total_stats() -> int:
    """Get the total number of jobs applied to."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM applied_jobs")
    total = cursor.fetchone()[0]
    conn.close()
    return total


def get_recent_applied(limit: int = 5) -> list:
    """Get the most recent job applications."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT job_title, company, date_applied FROM applied_jobs ORDER BY date_applied DESC LIMIT ?",
        (limit,),
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]
