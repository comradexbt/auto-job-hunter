# ruff: noqa: E402

import io
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from urllib.error import HTTPError, URLError


JOB_BOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(JOB_BOT_DIR))

import bot_telegram
import db_manager
import web3_api
from browser_engine import BrowserEngine


class FakeResponse:
    def __init__(self, body: str):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self):
        return self.body.encode("utf-8")


class DatabaseErrorHandlingTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "jobs.db"
        self.path_patch = mock.patch.object(db_manager, "DB_PATH", str(self.db_path))
        self.path_patch.start()
        db_manager.init_db()

    def tearDown(self):
        self.path_patch.stop()
        self.temp_dir.cleanup()

    def test_duplicate_url_is_the_only_suppressed_integrity_error(self):
        self.assertTrue(db_manager.save_job("Engineer", "Acme", "https://example.com/1"))
        self.assertFalse(db_manager.save_job("Engineer", "Acme", "https://example.com/1"))

        with self.assertRaises(sqlite3.IntegrityError):
            db_manager.save_job(None, "Acme", "https://example.com/2")


class Web3APIErrorHandlingTests(unittest.TestCase):
    def test_invalid_json_is_raised_with_context(self):
        with (
            mock.patch.object(web3_api, "WEB3_API_TOKEN", "token"),
            mock.patch.object(web3_api, "urlopen", return_value=FakeResponse("not-json")),
        ):
            with self.assertRaises(web3_api.Web3APIError) as raised:
                web3_api.fetch_jobs()

        self.assertIsInstance(raised.exception.__cause__, json.JSONDecodeError)

    def test_unexpected_payload_is_not_reported_as_no_jobs(self):
        with (
            mock.patch.object(web3_api, "WEB3_API_TOKEN", "token"),
            mock.patch.object(
                web3_api,
                "urlopen",
                return_value=FakeResponse('{"unexpected": []}'),
            ),
        ):
            with self.assertRaisesRegex(
                web3_api.Web3APIError,
                "unexpected response format",
            ):
                web3_api.fetch_jobs()

    def test_network_failure_is_raised_after_retries(self):
        with (
            mock.patch.object(web3_api, "WEB3_API_TOKEN", "token"),
            mock.patch.object(web3_api, "MAX_RETRIES", 2),
            mock.patch.object(web3_api, "urlopen", side_effect=URLError("offline")),
            mock.patch.object(web3_api.time, "sleep"),
        ):
            with self.assertRaisesRegex(
                web3_api.Web3APIError,
                "failed after 2 attempts",
            ):
                web3_api.fetch_jobs()

    def test_auth_failure_does_not_include_the_token(self):
        error = HTTPError(
            "https://web3.career/api/v1",
            401,
            "Unauthorized",
            {},
            io.BytesIO(),
        )
        with (
            mock.patch.object(web3_api, "WEB3_API_TOKEN", "secret-token"),
            mock.patch.object(web3_api, "urlopen", side_effect=error),
        ):
            with self.assertRaises(web3_api.Web3APIError) as raised:
                web3_api.fetch_jobs()

        self.assertNotIn("secret-token", str(raised.exception))


class TelegramPersistenceErrorHandlingTests(unittest.TestCase):
    def test_malformed_targets_are_propagated(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "targets.json"
            path.write_text("{invalid", encoding="utf-8")
            with mock.patch.object(bot_telegram, "TARGETS_PATH", str(path)):
                with self.assertRaises(json.JSONDecodeError):
                    bot_telegram._load_targets()

    def test_resume_save_errors_are_propagated(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with mock.patch.object(bot_telegram, "RESUME_PATH", temp_dir):
                with self.assertRaises(OSError):
                    bot_telegram._save_resume({"skills": []})


class BrowserErrorHandlingTests(unittest.TestCase):
    def test_page_loading_error_propagates_and_closes_page(self):
        page = mock.Mock()
        page.goto.side_effect = RuntimeError("navigation failed")
        engine = BrowserEngine()
        engine.context = mock.Mock()
        engine.context.new_page.return_value = page

        with self.assertRaisesRegex(RuntimeError, "navigation failed"):
            engine.get_page_content("https://example.com")

        page.close.assert_called_once_with()

    def test_application_error_propagates_and_closes_page(self):
        page = mock.Mock()
        page.goto.side_effect = RuntimeError("application failed")
        engine = BrowserEngine()
        engine.context = mock.Mock()
        engine.context.new_page.return_value = page

        with self.assertRaisesRegex(RuntimeError, "application failed"):
            engine.apply_to_job("https://example.com", {}, "")

        page.close.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
