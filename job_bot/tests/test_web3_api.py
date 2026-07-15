"""Unit tests for web3_api (Web3 Jobs API fetching + normalization)."""
import io
import json
from urllib.error import HTTPError, URLError

import pytest

import web3_api


# ─── _normalize_job ──────────────────────────────────────────────────────────


def test_normalize_job_returns_none_without_title():
    assert web3_api._normalize_job({}) is None
    assert web3_api._normalize_job({"company": "ACME"}) is None
    assert web3_api._normalize_job(None) is None


def test_normalize_job_basic_fields():
    raw = {
        "id": 42,
        "title": "Solidity Engineer",
        "company": "Web3 Co",
        "is_remote": 1,
        "apply_url": "https://web3.career/apply/42",
        "tags": ["solidity", "rust"],
        "location": "Remote",
        "date": "2024-01-01",
    }
    job = web3_api._normalize_job(raw)
    assert job["job_title"] == "Solidity Engineer"
    assert job["company"] == "Web3 Co"
    assert job["is_remote"] is True
    assert job["application_url"] == "https://web3.career/apply/42"
    assert job["required_skills"] == ["solidity", "rust"]
    assert job["source"] == "web3"
    assert job["source_id"] == "42"
    assert job["location"] == "Remote"


def test_normalize_job_defaults_for_missing_optional_fields():
    job = web3_api._normalize_job({"title": "Dev"})
    assert job["company"] == "Unknown Company"
    assert job["is_remote"] is False
    assert job["application_url"] == ""
    assert job["required_skills"] == []
    assert job["salary_range"] == ""
    assert job["source_id"] == ""


def test_normalize_job_strips_html_and_collapses_whitespace():
    raw = {
        "title": "Dev",
        "description": "<p>Hello   <b>World</b></p>\n\n<script>x</script> done",
    }
    job = web3_api._normalize_job(raw)
    assert "<" not in job["job_description"]
    assert "  " not in job["job_description"]
    assert "Hello World" in job["job_description"]


def test_normalize_job_truncates_long_description():
    raw = {"title": "Dev", "description": "a" * 5000}
    job = web3_api._normalize_job(raw)
    assert len(job["job_description"]) == 2000


def test_normalize_job_salary_min_and_max():
    job = web3_api._normalize_job(
        {
            "title": "Dev",
            "salary_min_value": 100000,
            "salary_max_value": 150000,
            "salary_currency": "$",
        }
    )
    assert job["salary_range"] == "$100,000 - $150,000"


def test_normalize_job_salary_min_only():
    job = web3_api._normalize_job(
        {"title": "Dev", "salary_min_value": 90000, "salary_currency": "$"}
    )
    assert job["salary_range"] == "From $90,000"


def test_normalize_job_salary_max_only():
    job = web3_api._normalize_job(
        {"title": "Dev", "salary_max_value": 120000, "salary_currency": "€"}
    )
    assert job["salary_range"] == "Up to €120,000"


def test_normalize_job_no_salary():
    job = web3_api._normalize_job({"title": "Dev"})
    assert job["salary_range"] == ""


# ─── fetch_jobs ───────────────────────────────────────────────────────────────


def test_fetch_jobs_returns_empty_without_token(monkeypatch):
    monkeypatch.setattr(web3_api, "WEB3_API_TOKEN", "")
    assert web3_api.fetch_jobs() == []


class _FakeResponse:
    """Minimal context-manager stand-in for urlopen's return value."""

    def __init__(self, payload: str):
        self._payload = payload.encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self._payload


def _make_urlopen(payload):
    def _urlopen(req, timeout=None):
        return _FakeResponse(payload)

    return _urlopen


def test_fetch_jobs_parses_three_element_array(monkeypatch):
    monkeypatch.setattr(web3_api, "WEB3_API_TOKEN", "tok")
    data = [
        "info",
        "terms",
        [
            {"title": "Dev A", "company": "C1"},
            {"title": "Dev B", "company": "C2"},
        ],
    ]
    monkeypatch.setattr(web3_api, "urlopen", _make_urlopen(json.dumps(data)))
    jobs = web3_api.fetch_jobs(limit=10)
    assert [j["job_title"] for j in jobs] == ["Dev A", "Dev B"]


def test_fetch_jobs_skips_non_dict_and_invalid_entries(monkeypatch):
    monkeypatch.setattr(web3_api, "WEB3_API_TOKEN", "tok")
    data = ["info", "terms", ["not-a-dict", {"company": "no title"}, {"title": "Ok"}]]
    monkeypatch.setattr(web3_api, "urlopen", _make_urlopen(json.dumps(data)))
    jobs = web3_api.fetch_jobs()
    assert [j["job_title"] for j in jobs] == ["Ok"]


def test_fetch_jobs_two_element_array_with_list(monkeypatch):
    monkeypatch.setattr(web3_api, "WEB3_API_TOKEN", "tok")
    data = ["info", [{"title": "Dev"}]]
    monkeypatch.setattr(web3_api, "urlopen", _make_urlopen(json.dumps(data)))
    jobs = web3_api.fetch_jobs()
    assert len(jobs) == 1


def test_fetch_jobs_bare_list_of_jobs(monkeypatch):
    monkeypatch.setattr(web3_api, "WEB3_API_TOKEN", "tok")
    data = [{"title": "Dev"}]
    monkeypatch.setattr(web3_api, "urlopen", _make_urlopen(json.dumps(data)))
    jobs = web3_api.fetch_jobs()
    assert len(jobs) == 1


def test_fetch_jobs_other_http_error_returns_empty(monkeypatch):
    monkeypatch.setattr(web3_api, "WEB3_API_TOKEN", "tok")

    def _urlopen(req, timeout=None):
        raise HTTPError(req.full_url, 500, "Server Error", {}, None)

    monkeypatch.setattr(web3_api, "urlopen", _urlopen)
    assert web3_api.fetch_jobs() == []


def test_fetch_jobs_handles_dict_with_jobs_key(monkeypatch):
    monkeypatch.setattr(web3_api, "WEB3_API_TOKEN", "tok")
    data = {"jobs": [{"title": "Dev"}]}
    monkeypatch.setattr(web3_api, "urlopen", _make_urlopen(json.dumps(data)))
    jobs = web3_api.fetch_jobs()
    assert len(jobs) == 1


def test_fetch_jobs_limit_clamped_into_query(monkeypatch):
    monkeypatch.setattr(web3_api, "WEB3_API_TOKEN", "tok")
    captured = {}

    def _urlopen(req, timeout=None):
        captured["url"] = req.full_url
        return _FakeResponse(json.dumps(["i", "t", []]))

    monkeypatch.setattr(web3_api, "urlopen", _urlopen)
    web3_api.fetch_jobs(limit=999)
    assert "limit=100" in captured["url"]

    web3_api.fetch_jobs(limit=0)
    assert "limit=1" in captured["url"]


def test_fetch_jobs_query_includes_filters(monkeypatch):
    monkeypatch.setattr(web3_api, "WEB3_API_TOKEN", "tok")
    captured = {}

    def _urlopen(req, timeout=None):
        captured["url"] = req.full_url
        return _FakeResponse(json.dumps(["i", "t", []]))

    monkeypatch.setattr(web3_api, "urlopen", _urlopen)
    web3_api.fetch_jobs(remote_only=True, tags=["solidity", "rust"], country="us")
    url = captured["url"]
    assert "remote=1" in url
    assert "tags=solidity,rust" in url
    assert "country=us" in url


def test_fetch_jobs_omits_remote_flag_when_false(monkeypatch):
    monkeypatch.setattr(web3_api, "WEB3_API_TOKEN", "tok")
    captured = {}

    def _urlopen(req, timeout=None):
        captured["url"] = req.full_url
        return _FakeResponse(json.dumps(["i", "t", []]))

    monkeypatch.setattr(web3_api, "urlopen", _urlopen)
    web3_api.fetch_jobs(remote_only=False)
    assert "remote=1" not in captured["url"]


def test_fetch_jobs_invalid_json_returns_empty(monkeypatch):
    monkeypatch.setattr(web3_api, "WEB3_API_TOKEN", "tok")
    monkeypatch.setattr(web3_api, "urlopen", _make_urlopen("not json"))
    assert web3_api.fetch_jobs() == []


def test_fetch_jobs_403_returns_empty(monkeypatch):
    monkeypatch.setattr(web3_api, "WEB3_API_TOKEN", "tok")

    def _urlopen(req, timeout=None):
        raise HTTPError(req.full_url, 403, "Forbidden", {}, None)

    monkeypatch.setattr(web3_api, "urlopen", _urlopen)
    assert web3_api.fetch_jobs() == []


def test_fetch_jobs_401_returns_empty(monkeypatch):
    monkeypatch.setattr(web3_api, "WEB3_API_TOKEN", "tok")

    def _urlopen(req, timeout=None):
        raise HTTPError(req.full_url, 401, "Unauthorized", {}, None)

    monkeypatch.setattr(web3_api, "urlopen", _urlopen)
    assert web3_api.fetch_jobs() == []


def test_fetch_jobs_429_retries_then_gives_up(monkeypatch):
    monkeypatch.setattr(web3_api, "WEB3_API_TOKEN", "tok")
    monkeypatch.setattr(web3_api, "MAX_RETRIES", 2)
    calls = {"n": 0}

    def _urlopen(req, timeout=None):
        calls["n"] += 1
        raise HTTPError(req.full_url, 429, "Too Many Requests", {}, None)

    monkeypatch.setattr(web3_api, "urlopen", _urlopen)
    monkeypatch.setattr(web3_api.time, "sleep", lambda *_: None)
    assert web3_api.fetch_jobs() == []
    assert calls["n"] == 2


def test_fetch_jobs_url_error_retries_then_empty(monkeypatch):
    monkeypatch.setattr(web3_api, "WEB3_API_TOKEN", "tok")
    monkeypatch.setattr(web3_api, "MAX_RETRIES", 3)

    def _urlopen(req, timeout=None):
        raise URLError("connection refused")

    monkeypatch.setattr(web3_api, "urlopen", _urlopen)
    monkeypatch.setattr(web3_api.time, "sleep", lambda *_: None)
    assert web3_api.fetch_jobs() == []


def test_fetch_jobs_recovers_after_transient_error(monkeypatch):
    monkeypatch.setattr(web3_api, "WEB3_API_TOKEN", "tok")
    monkeypatch.setattr(web3_api.time, "sleep", lambda *_: None)
    calls = {"n": 0}

    def _urlopen(req, timeout=None):
        calls["n"] += 1
        if calls["n"] == 1:
            raise URLError("temporary")
        return _FakeResponse(json.dumps(["i", "t", [{"title": "Dev"}]]))

    monkeypatch.setattr(web3_api, "urlopen", _urlopen)
    jobs = web3_api.fetch_jobs()
    assert len(jobs) == 1
    assert calls["n"] == 2
