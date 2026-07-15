"""Unit tests for ai_processor pure helpers and no-API fallback paths.

These tests deliberately avoid any live Gemini calls by forcing the module
into its "AI unavailable" state so the deterministic fallback logic runs.
"""
import json

import pytest

import ai_processor


@pytest.fixture(autouse=True)
def disable_gemini(monkeypatch):
    """Force the module into fallback mode and neutralize init_gemini."""
    monkeypatch.setattr(ai_processor, "_genai_available", False)
    monkeypatch.setattr(ai_processor, "_genai_model", None)
    monkeypatch.setattr(ai_processor, "init_gemini", lambda: None)


# ─── _clean_ai_text ───────────────────────────────────────────────────────────


def test_clean_ai_text_empty():
    assert ai_processor._clean_ai_text("") == ""
    assert ai_processor._clean_ai_text(None) == ""


def test_clean_ai_text_strips_markdown_and_code_fences():
    raw = "```json\n**Hello** _world_ `code`\n```"
    cleaned = ai_processor._clean_ai_text(raw)
    assert "*" not in cleaned
    assert "_" not in cleaned
    assert "`" not in cleaned
    assert "Hello world code" == cleaned


def test_clean_ai_text_removes_intro_phrases():
    assert ai_processor._clean_ai_text("Here is the answer") == "the answer"
    assert ai_processor._clean_ai_text("I will do the thing") == "do the thing"


def test_clean_ai_text_collapses_whitespace():
    assert ai_processor._clean_ai_text("a\n\n  b\t c") == "a b c"


# ─── _detect_site_name ────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://www.linkedin.com/jobs/view/123", "linkedin"),
        ("https://www.indeed.com/viewjob?jk=1", "indeed"),
        ("https://remoteok.com/remote-jobs/1", "remoteok"),
        ("https://weworkremotely.com/jobs/1", "weworkremotely"),
        ("https://wellfound.com/jobs/1", "wellfound"),
        ("https://angellist.com/l/1", "wellfound"),
        ("https://remotive.com/x", "remotive"),
        ("https://glassdoor.com/job/1", "glassdoor"),
        ("https://example.com/careers", "generic"),
        ("", "generic"),
    ],
)
def test_detect_site_name(url, expected):
    assert ai_processor._detect_site_name(url) == expected


# ─── _clean_page_text ─────────────────────────────────────────────────────────


def test_clean_page_text_removes_scripts_styles_and_tags():
    html = (
        "<html><head><style>.a{color:red}</style>"
        "<script>alert('x')</script></head>"
        "<body><h1>Title</h1>  <p>Body   text</p></body></html>"
    )
    text = ai_processor._clean_page_text(html)
    assert "alert" not in text
    assert "color:red" not in text
    assert "<" not in text
    assert "Title Body text" in text


def test_clean_page_text_truncates_to_15k():
    html = "<p>" + ("x" * 20000) + "</p>"
    assert len(ai_processor._clean_page_text(html)) == 15000


# ─── _parse_json_response ─────────────────────────────────────────────────────


def test_parse_json_response_direct():
    assert ai_processor._parse_json_response('{"a": 1}') == {"a": 1}


def test_parse_json_response_from_code_fence():
    text = 'Some text\n```json\n{"a": 2}\n```\nmore'
    assert ai_processor._parse_json_response(text) == {"a": 2}


def test_parse_json_response_embedded_object():
    text = 'garbage {"a": 3} trailing'
    assert ai_processor._parse_json_response(text) == {"a": 3}


def test_parse_json_response_empty_or_invalid():
    assert ai_processor._parse_json_response("") is None
    assert ai_processor._parse_json_response("no json here") is None


# ─── _get_min_match_score ─────────────────────────────────────────────────────


def test_get_min_match_score_default():
    assert ai_processor._get_min_match_score({}) == 70


def test_get_min_match_score_from_preferences():
    resume = {"preferences": {"min_match_percentage": 85}}
    assert ai_processor._get_min_match_score(resume) == 85


# ─── _extract_job_info_regex ──────────────────────────────────────────────────


def test_extract_job_info_regex_from_labels():
    text = "Job Title: Senior Python Developer\nCompany: ACME Corp\nWork from home role"
    info = ai_processor._extract_job_info_regex(text)
    assert info["job_title"] == "Senior Python Developer"
    assert info["company"] == "ACME Corp"
    assert info["is_remote"] is True


def test_extract_job_info_regex_from_json_fields():
    text = '{"jobTitle": "Data Scientist", "company": "DataInc"}'
    info = ai_processor._extract_job_info_regex(text)
    assert info["job_title"] == "Data Scientist"
    assert info["company"] == "DataInc"


def test_extract_job_info_regex_defaults_when_missing():
    info = ai_processor._extract_job_info_regex("nothing useful here on site")
    assert info["job_title"] == "Unknown Position"
    assert info["company"] == "Unknown Company"
    assert info["required_skills"] == []
    assert info["job_description"] == "nothing useful here on site"


def test_extract_job_info_regex_not_remote():
    info = ai_processor._extract_job_info_regex("Title: Onsite clerk in office")
    assert info["is_remote"] is False


# ─── extract_job_info (fallback path) ─────────────────────────────────────────


def test_extract_job_info_uses_regex_when_ai_unavailable():
    # _clean_page_text strips HTML before the regex fallback runs, so use
    # label-based plain text that the fallback extractor can parse.
    html = "Job Title: Backend Engineer. This is a fully remote role. Company: Foo"
    info = ai_processor.extract_job_info(html, url="https://example.com")
    assert info["job_title"] == "Backend Engineer. This is a fully remote role. Company: Foo"
    assert info["company"] == "Foo"
    assert info["is_remote"] is True


# ─── match_job (quick filters + fallback) ─────────────────────────────────────


def test_match_job_rejects_non_remote_when_remote_only():
    resume = {"preferences": {"remote_only": True}}
    job = {"is_remote": False, "job_title": "Dev"}
    assert ai_processor.match_job(job, resume) is False


def test_match_job_rejects_unknown_position():
    resume = {"preferences": {"remote_only": True}}
    job = {"is_remote": True, "job_title": "Unknown Position"}
    assert ai_processor.match_job(job, resume) is False


def test_match_job_fallback_accepts_remote():
    resume = {"preferences": {"remote_only": True}}
    job = {"is_remote": True, "job_title": "Senior Engineer"}
    assert ai_processor.match_job(job, resume) is True


def test_match_job_accepts_non_remote_when_remote_only_false():
    resume = {"preferences": {"remote_only": False}}
    job = {"is_remote": False, "job_title": "Onsite Engineer"}
    assert ai_processor.match_job(job, resume) is True


# ─── _fallback_form_answer ────────────────────────────────────────────────────


RESUME = {
    "personal_info": {
        "name": "Jane Doe",
        "first_name": "Jane",
        "last_name": "Doe",
        "email": "jane@example.com",
        "phone": "555-1234",
        "linkedin_username": "janedoe",
        "portfolio": "https://jane.dev",
        "location": "NYC",
    },
    "skills": ["Python", "Solidity"],
    "experience": [{"title": "Engineer", "company": "ACME"}],
}


@pytest.mark.parametrize(
    "question,expected",
    [
        ("Are you authorized to work?", "Yes"),
        ("Do you require visa sponsorship?", "No"),
        ("Have you ever been convicted of a felony?", "No"),
        ("Are you currently employed?", "Yes"),
    ],
)
def test_fallback_form_answer_yes_no(question, expected):
    assert ai_processor._fallback_form_answer(question, RESUME, "yes_no") == expected


def test_fallback_form_answer_first_last_name():
    assert ai_processor._fallback_form_answer("First name", RESUME) == "Jane"
    assert ai_processor._fallback_form_answer("Last name", RESUME) == "Doe"


def test_fallback_form_answer_contact_fields():
    assert ai_processor._fallback_form_answer("Email address", RESUME) == "jane@example.com"
    assert ai_processor._fallback_form_answer("Phone number", RESUME) == "555-1234"
    assert (
        ai_processor._fallback_form_answer("LinkedIn URL", RESUME)
        == "https://linkedin.com/in/janedoe"
    )
    assert ai_processor._fallback_form_answer("Portfolio website", RESUME) == "https://jane.dev"


def test_fallback_form_answer_location_skills_experience():
    assert ai_processor._fallback_form_answer("City / Location", RESUME) == "NYC"
    assert ai_processor._fallback_form_answer("List your skills", RESUME) == "Python, Solidity"
    assert (
        ai_processor._fallback_form_answer("Describe your experience", RESUME)
        == "Engineer at ACME"
    )


def test_fallback_form_answer_salary_and_start_date():
    assert ai_processor._fallback_form_answer("Expected salary", RESUME) == "Negotiable"
    assert ai_processor._fallback_form_answer("Available start date", RESUME) == "Two weeks notice"


def test_fallback_form_answer_demographics_decline():
    assert (
        ai_processor._fallback_form_answer("What is your gender?", RESUME)
        == "Decline to self-identify"
    )


def test_fallback_form_answer_unknown_returns_empty():
    assert ai_processor._fallback_form_answer("Favorite color?", RESUME) == ""


def test_generate_form_answer_uses_fallback_when_ai_unavailable():
    # With AI disabled, generate_form_answer should defer to the template logic.
    assert ai_processor.generate_form_answer("Email", RESUME) == "jane@example.com"


# ─── generate_cover_letter (fallback path) ────────────────────────────────────


def test_generate_cover_letter_uses_template_when_present():
    resume = dict(RESUME)
    resume["cover_letter_template"] = "Hi, I want the {job_title} role at {company}."
    job = {"job_title": "SRE", "company": "Foo"}
    letter = ai_processor.generate_cover_letter(job, resume)
    assert letter == "Hi, I want the SRE role at Foo."


def test_generate_cover_letter_default_template():
    job = {"job_title": "SRE", "company": "Foo"}
    letter = ai_processor.generate_cover_letter(job, RESUME)
    assert "SRE" in letter
    assert "Foo" in letter
    assert "Jane Doe" in letter


def test_generate_cover_letter_handles_bad_template_keys():
    resume = dict(RESUME)
    # {missing} is not a supported placeholder -> KeyError -> default letter.
    resume["cover_letter_template"] = "Role: {missing}"
    job = {"job_title": "SRE", "company": "Foo"}
    letter = ai_processor.generate_cover_letter(job, resume)
    assert "Jane Doe" in letter
