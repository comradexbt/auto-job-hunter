import sys
import unittest
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "job_bot"))

from security import (
    is_safe_public_http_url,
    is_safe_public_websocket_url,
    parse_allowed_user_ids,
    url_for_log,
)


class SecurityTests(unittest.TestCase):
    def test_parse_allowed_user_ids(self):
        self.assertEqual(
            parse_allowed_user_ids("123, 456,123"),
            frozenset({123, 456}),
        )

    def test_parse_allowed_user_ids_rejects_invalid_values(self):
        with self.assertRaises(ValueError):
            parse_allowed_user_ids("123,not-a-number")
        with self.assertRaises(ValueError):
            parse_allowed_user_ids("0")

    def test_public_http_urls_are_allowed(self):
        self.assertTrue(is_safe_public_http_url("https://1.1.1.1/jobs"))
        self.assertTrue(is_safe_public_http_url("http://8.8.8.8/"))
        self.assertFalse(is_safe_public_http_url("wss://1.1.1.1/socket"))
        self.assertTrue(is_safe_public_websocket_url("wss://1.1.1.1/socket"))

    def test_private_and_local_urls_are_blocked(self):
        blocked_urls = [
            "http://127.0.0.1/admin",
            "http://10.0.0.1/",
            "http://169.254.169.254/latest/meta-data/",
            "http://[::1]/",
            "http://localhost/",
            "http://service.localhost/",
        ]
        for url in blocked_urls:
            with self.subTest(url=url):
                self.assertFalse(is_safe_public_http_url(url))

    @patch("security.socket.getaddrinfo")
    def test_hostnames_must_resolve_only_to_public_addresses(self, getaddrinfo):
        getaddrinfo.return_value = [
            (2, 1, 6, "", ("93.184.216.34", 443)),
        ]
        self.assertTrue(is_safe_public_http_url("https://example.com/jobs"))

        getaddrinfo.return_value = [
            (2, 1, 6, "", ("93.184.216.34", 443)),
            (2, 1, 6, "", ("127.0.0.1", 443)),
        ]
        self.assertFalse(is_safe_public_http_url("https://example.com/jobs"))

    def test_non_http_and_credential_urls_are_blocked(self):
        blocked_urls = [
            "file:///etc/passwd",
            "javascript:alert(1)",
            "ftp://1.1.1.1/file",
            "https://user:password@1.1.1.1/",
            "https:///",
        ]
        for url in blocked_urls:
            with self.subTest(url=url):
                self.assertFalse(is_safe_public_http_url(url))

    def test_url_for_log_removes_credentials_and_query_strings(self):
        self.assertEqual(
            url_for_log("https://user:secret@1.1.1.1/jobs?token=secret#fragment"),
            "https://1.1.1.1/jobs",
        )


if __name__ == "__main__":
    unittest.main()
