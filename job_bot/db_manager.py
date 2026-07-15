"""
Database Manager (Phase 1)
Handles SQLite operations for tracking applied jobs and preventing duplicates.
"""
import sqlite3
import datetime
import os
from contextlib import closing

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
    with closing(get_connection()) as conn, conn:
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


def is_job_applied(url: str) -> bool:
    """Check if a job URL has already been applied to."""
    with closing(get_connection()) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM applied_jobs WHERE url = ?", (url,))
        return cursor.fetchone() is not None


def save_job(title: str, company: str, url: str, status: str = "applied") -> bool:
    """Save an application, returning False only when the URL already exists."""
    with closing(get_connection()) as conn, conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO applied_jobs (job_title, company, url, status) VALUES (?, ?, ?, ?)",
                (title, company, url, status),
            )
        except sqlite3.IntegrityError as error:
            if "applied_jobs.url" in str(error):
                return False
            raise
    return True


def get_today_stats() -> int:
    """Get the number of jobs applied to today."""
    with closing(get_connection()) as conn:
        cursor = conn.cursor()
        today = datetime.date.today().isoformat()
        cursor.execute(
            "SELECT COUNT(*) FROM applied_jobs WHERE date(date_applied) = ?",
            (today,),
        )
        return cursor.fetchone()[0]


def get_total_stats() -> int:
    """Get the total number of jobs applied to."""
    with closing(get_connection()) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM applied_jobs")
        return cursor.fetchone()[0]


def get_recent_applied(limit: int = 5) -> list:
    """Get the most recent job applications."""
    with closing(get_connection()) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT job_title, company, date_applied FROM applied_jobs ORDER BY date_applied DESC LIMIT ?",
            (limit,),
        )
        return [dict(row) for row in cursor.fetchall()]
