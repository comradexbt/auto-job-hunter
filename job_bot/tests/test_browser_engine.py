"""Unit tests for BrowserEngine pure helpers (no live browser required).

Only the deterministic, browser-independent methods are exercised here:
platform detection, question-type detection, and smart-answer lookup.
``BrowserEngine.__init__`` performs no I/O, so it is safe to instantiate.
"""
import pytest

import browser_engine
from browser_engine import BrowserEngine


@pytest.fixture
def engine():
    return BrowserEngine(headless=True)


# ─── _detect_platform ─────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://boards.greenhouse.io/acme/jobs/1", "greenhouse"),
        ("https://jobs.lever.co/acme/1", "lever"),
        ("https://acme.wd5.myworkdayjobs.com/careers", "workday"),
        ("https://jobs.ashbyhq.com/acme/1", "ashby"),
        ("https://acme.bamboohr.com/jobs/1", "bamboohr"),
        ("https://jobs.smartrecruiters.com/acme/1", "smartrecruiters"),
        ("https://acme.icims.com/jobs/1", "icims"),
        ("https://example.com/careers/1", "generic"),
    ],
)
def test_detect_platform(engine, url, expected):
    assert engine._detect_platform(url) == expected


def test_detect_platform_is_case_insensitive(engine):
    assert engine._detect_platform("HTTPS://BOARDS.GREENHOUSE.IO/x") == "greenhouse"


# ─── _smart_detect_question_type ──────────────────────────────────────────────


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Are you authorized to work in the US?", "work_authorization"),
        ("What is your race/ethnicity?", "race_ethnicity"),
        ("Please select your gender", "gender"),
        ("Are you a protected veteran?", "veteran_status"),
        ("Do you have a disability?", "disability"),
        ("What is your highest education level?", "highest_education"),
        ("Earliest start date?", "start_date"),
        ("Have you ever been convicted of a felony?", "felony"),
    ],
)
def test_smart_detect_question_type(engine, text, expected):
    assert engine._smart_detect_question_type(text) == expected


def test_smart_detect_question_type_unknown_returns_none(engine):
    assert engine._smart_detect_question_type("What is your favorite color?") is None


def test_smart_detect_question_type_is_case_insensitive(engine):
    assert engine._smart_detect_question_type("FELONY conviction?") == "felony"


# ─── _get_smart_answer ────────────────────────────────────────────────────────


def test_get_smart_answer_unknown_type_returns_none(engine):
    assert engine._get_smart_answer("nonexistent") is None


def test_get_smart_answer_yes_no(engine):
    assert engine._get_smart_answer("work_authorization", "yes_no") == "yes"
    assert engine._get_smart_answer("visa_sponsorship", "yes_no") == "no"


def test_get_smart_answer_select(engine):
    assert engine._get_smart_answer("felony", "select") == "No"


def test_get_smart_answer_text_default(engine):
    assert engine._get_smart_answer("felony", "text") == "No"


def test_get_smart_answer_linkedin_is_personalized(engine):
    answer = engine._get_smart_answer("linkedin", "text")
    assert answer.startswith("https://linkedin.com/in/")
    assert answer.endswith("comradexbt")


def test_get_smart_answer_falls_back_to_text_when_no_yes_no(engine):
    # race_ethnicity has answer_yes_no=None, so yes_no should fall through to text.
    assert engine._get_smart_answer("race_ethnicity", "yes_no") == "Decline to self-identify"


def test_smart_answers_and_platform_patterns_are_populated():
    assert "work_authorization" in browser_engine.SMART_ANSWERS
    assert "greenhouse" in browser_engine.PLATFORM_PATTERNS
