"""Unit tests for db_manager (SQLite-backed applied-jobs tracking)."""
import datetime
import sqlite3

import pytest

import db_manager


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    """Point db_manager at an isolated temporary database and init it."""
    db_file = tmp_path / "test_jobs.db"
    monkeypatch.setattr(db_manager, "DB_PATH", str(db_file))
    db_manager.init_db()
    return str(db_file)


def test_init_db_creates_table_and_indexes(temp_db):
    conn = db_manager.get_connection()
    tables = {
        row["name"]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }
    indexes = {
        row["name"]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index'"
        )
    }
    conn.close()
    assert "applied_jobs" in tables
    assert "idx_applied_jobs_url" in indexes
    assert "idx_applied_jobs_date" in indexes


def test_init_db_is_idempotent(temp_db):
    # Calling init_db again should not raise or drop existing data.
    db_manager.save_job("Engineer", "ACME", "https://x.com/1")
    db_manager.init_db()
    assert db_manager.get_total_stats() == 1


def test_get_connection_uses_row_factory(temp_db):
    conn = db_manager.get_connection()
    assert conn.row_factory is sqlite3.Row
    conn.close()


def test_save_job_returns_true_on_insert(temp_db):
    assert db_manager.save_job("Dev", "Corp", "https://x.com/job") is True
    assert db_manager.get_total_stats() == 1


def test_save_job_default_status_is_applied(temp_db):
    db_manager.save_job("Dev", "Corp", "https://x.com/job")
    conn = db_manager.get_connection()
    row = conn.execute("SELECT status FROM applied_jobs").fetchone()
    conn.close()
    assert row["status"] == "applied"


def test_save_job_custom_status(temp_db):
    db_manager.save_job("Dev", "Corp", "https://x.com/job", status="pending")
    conn = db_manager.get_connection()
    row = conn.execute("SELECT status FROM applied_jobs").fetchone()
    conn.close()
    assert row["status"] == "pending"


def test_save_job_duplicate_url_returns_false(temp_db):
    url = "https://x.com/dup"
    assert db_manager.save_job("Dev", "Corp", url) is True
    assert db_manager.save_job("Dev2", "Corp2", url) is False
    # Duplicate should not create a second row.
    assert db_manager.get_total_stats() == 1


def test_is_job_applied(temp_db):
    url = "https://x.com/applied"
    assert db_manager.is_job_applied(url) is False
    db_manager.save_job("Dev", "Corp", url)
    assert db_manager.is_job_applied(url) is True


def test_get_total_stats_counts_all(temp_db):
    db_manager.save_job("A", "C1", "https://x.com/a")
    db_manager.save_job("B", "C2", "https://x.com/b")
    assert db_manager.get_total_stats() == 2


def test_get_today_stats_counts_only_today(temp_db):
    db_manager.save_job("Today", "C", "https://x.com/today")

    # Insert a row dated yesterday directly, bypassing the default timestamp.
    yesterday = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
    conn = db_manager.get_connection()
    conn.execute(
        "INSERT INTO applied_jobs (job_title, company, url, status, date_applied) "
        "VALUES (?, ?, ?, ?, ?)",
        ("Old", "C", "https://x.com/old", "applied", f"{yesterday} 12:00:00"),
    )
    conn.commit()
    conn.close()

    assert db_manager.get_total_stats() == 2
    assert db_manager.get_today_stats() == 1


def test_get_recent_applied_orders_by_date_desc_and_limits(temp_db):
    conn = db_manager.get_connection()
    for i in range(3):
        conn.execute(
            "INSERT INTO applied_jobs (job_title, company, url, date_applied) "
            "VALUES (?, ?, ?, ?)",
            (f"Job{i}", f"Co{i}", f"https://x.com/{i}", f"2023-01-0{i + 1} 10:00:00"),
        )
    conn.commit()
    conn.close()

    recent = db_manager.get_recent_applied(limit=2)
    assert len(recent) == 2
    # Most recent (Job2) first.
    assert recent[0]["job_title"] == "Job2"
    assert recent[1]["job_title"] == "Job1"
    # Returns dicts with the selected columns only.
    assert set(recent[0].keys()) == {"job_title", "company", "date_applied"}


def test_get_recent_applied_empty(temp_db):
    assert db_manager.get_recent_applied() == []
