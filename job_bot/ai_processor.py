"""
AI Processor (Phase 4)
Uses Google Gemini API to:

  A) Extract structured job info from raw page text
  B) Match job requirements against user's resume (>70% threshold)
  C) Generate customized cover letters

Falls back to regex-based extraction if the API is unavailable.
"""
import json
import os
import re
import time
from typing import Optional

import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from google.api_core import exceptions as google_exceptions
from utils import read_json

# ─── Configuration ──────────────────────────────────────────────────────────────

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or ""

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds

# ─── Gemini Client ──────────────────────────────────────────────────────────────

_genai_model = None
_genai_available = False


def init_gemini():
    """Initialize and return the Gemini model singleton."""
    global _genai_model, _genai_available

    if _genai_model is not None:
        return _genai_model

    if not GEMINI_API_KEY:
        print("  └ ⚠️  GEMINI_API_KEY not set — falling back to regex extraction")
        print("     Set it in .env or as an environment variable.")
        return None

    try:
        genai.configure(api_key=GEMINI_API_KEY)

        safety_settings = {
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
        }

        _genai_model = genai.GenerativeModel(
            GEMINI_MODEL,
            safety_settings=safety_settings,
        )

        # Quick test to verify the API key works
        _genai_model.generate_content("test", generation_config={"max_output_tokens": 1})
        _genai_available = True
        print(f"  └ ✅ Gemini {GEMINI_MODEL} initialized successfully")

    except Exception as e:
        _genai_model = None
        _genai_available = False
        print(f"  └ ⚠️ Gemini init failed: {e}")
        print("  └    Falling back to regex extraction")

    return _genai_model


def _clean_ai_text(text: str) -> str:
    """Remove AI-generated formatting artifacts to prevent detection.
    
    Strips Markdown, asterisks, code blocks, and other AI markers
    that could reveal automated text generation.
    
    Args:
        text: Raw AI-generated text.
    
    Returns:
        Cleaned text suitable for form fields.
    """
    if not text:
        return ""
    
    # Remove markdown code blocks
    text = re.sub(r'```(?:json)?\s*\n?', '', text, flags=re.IGNORECASE)
    text = re.sub(r'```\s*$', '', text)
    
    # Remove markdown formatting
    text = text.replace('**', '').replace('__', '')
    text = text.replace('*', '').replace('_', '')
    text = text.replace('`', '')
    
    # Remove common AI phrases
    text = re.sub(r'^(Here is|Here\'s|The following is|Below is)', '', text, flags=re.IGNORECASE)
    text = re.sub(r'^(I have|I\'ve|I will)', '', text, flags=re.IGNORECASE)
    
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text


def _call_gemini(prompt: str, system_instruction: str = "", json_mode: bool = False, anti_ai_mode: bool = False) -> Optional[str]:
    """Call Gemini with retry logic.

    Args:
        prompt: The user prompt / page content.
        system_instruction: System-level instruction for the model.
        json_mode: If True, requests structured JSON output.
        anti_ai_mode: If True, uses strict anti-detection settings for form filling.

    Returns:
        Response text, or None on failure.
    """
    global _genai_available

    model = _genai_model
    if model is None:
        return None

    # Anti-AI mode: strict settings to prevent detection
    if anti_ai_mode:
        generation_config = {"temperature": 0.1, "max_output_tokens": 1024}
    else:
        generation_config = {"temperature": 0.3, "max_output_tokens": 2048}
    
    if json_mode:
        generation_config["response_mime_type"] = "application/json"

    # Use a fresh model instance with system instruction if provided
    if system_instruction:
        model = genai.GenerativeModel(
            GEMINI_MODEL,
            system_instruction=system_instruction,
            safety_settings={
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
            },
        )

    last_error = None

    for attempt in range(MAX_RETRIES):
        try:
            response = model.generate_content(
                prompt,
                generation_config=generation_config,
            )
            return response.text

        except google_exceptions.ResourceExhausted as e:
            # Rate limit – wait and retry with backoff
            wait = RETRY_DELAY * (2 ** attempt)
            print(f"  └ ⏳ Rate limited, retrying in {wait}s... (attempt {attempt + 1}/{MAX_RETRIES})")
            time.sleep(wait)
            last_error = e

        except google_exceptions.InvalidArgument as e:
            print(f"  └ ❌ Invalid argument: {e}")
            return None

        except google_exceptions.PermissionDenied as e:
            print(f"  └ ❌ API key invalid or permissions denied: {e}")
            _genai_available = False
            return None

        except Exception as e:
            wait = RETRY_DELAY * (2 ** attempt)
            print(f"  └ ⚠️ Gemini error: {e}, retrying in {wait}s...")
            time.sleep(wait)
            last_error = e

    print(f"  └ ❌ All {MAX_RETRIES} attempts failed: {last_error}")
    return None


# ─── Resume Loading ─────────────────────────────────────────────────────────────


def load_resume() -> dict:
    """Load the user's resume data from my_resume.json."""
    path = os.path.join(os.path.dirname(__file__), "my_resume.json")
    return read_json(path)


# ─── Helpers ────────────────────────────────────────────────────────────────────


def _detect_site_name(url: str = "") -> str:
    """Detect which job board a URL belongs to for site-specific extraction.

    Returns:
        Site name string like 'linkedin', 'indeed', 'remoteok', etc.
    """
    url_lower = url.lower()
    site_patterns = {
        "linkedin": r"linkedin\.",
        "indeed": r"indeed\.",
        "remoteok": r"remoteok\.",
        "weworkremotely": r"weworkremotely\.",
        "wellfound": r"wellfound\.|angellist\.",
        "remotive": r"remotive\.",
        "remotely": r"remotely\.jobs",
        "jobspresso": r"jobspresso\.",
        "workingnomads": r"workingnomads\.",
        "ziprecruiter": r"ziprecruiter\.",
        "glassdoor": r"glassdoor\.",
        "monster": r"monster\.",
        "craigslist": r"craigslist\.",
        "dice": r"dice\.",
        "upwork": r"upwork\.",
    }
    for site, pattern in site_patterns.items():
        if re.search(pattern, url_lower):
            return site
    return "generic"


def _clean_page_text(raw_html: str) -> str:
    """Strip HTML tags and collapse whitespace for cleaner AI input."""
    # First remove script and style blocks (they contain non-content text)
    text = re.sub(
        r"<(script|style)[^>]*>.*?</\1>",
        " ",
        raw_html,
        flags=re.DOTALL | re.IGNORECASE,
    )
    # Then strip remaining HTML tags
    text = re.sub(r"<[^>]+>", " ", text)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    # Limit to 15k chars to stay within token limits
    return text[:15000]


def _parse_json_response(text: str) -> Optional[dict]:
    """Try to parse JSON from Gemini's response text.

    Gemini in JSON mode usually returns clean JSON, but we add
    some resilience for edge cases.
    """
    if not text:
        return None

    # Try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try to extract JSON from markdown code blocks
    json_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass

    # Try to find anything that looks like a JSON object
    json_match = re.search(r"\{.*\}", text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(0))
        except json.JSONDecodeError:
            pass

    return None


def _get_min_match_score(resume: dict) -> int:
    """Get the minimum match score threshold from resume config."""
    return resume.get("preferences", {}).get("min_match_percentage", 70)


# ═══════════════════════════════════════════════════════════════════════════════
# TASK A:  Job Extraction
# ═══════════════════════════════════════════════════════════════════════════════

# ─── Site-Specific Extraction Prompts ──────────────────────────────────────────

SITE_EXTRACTION_HINTS = {
    "linkedin": (
        "This is a **LinkedIn** job page. Look for:\n"
        "- Job title in the top heading or `jobTitle` meta\n"
        "- Company name near the title or in `hiringOrganization` meta\n"
        "- Remote label like 'Remote', 'Hybrid', 'On-site' in the criteria section\n"
        "- Skills in the 'Qualifications' or 'Requirements' section\n"
        "- Easy Apply button URL if present\n"
    ),
    "indeed": (
        "This is an **Indeed** job page. Look for:\n"
        "- Job title in the `jobTitle` class or heading\n"
        "- Company name near the rating/logo area\n"
        "- Remote label in the job meta line\n"
        "- Salary in the meta section (often has '$' sign)\n"
        "- Description in the `jobDescriptionText` div\n"
    ),
    "remoteok": (
        "This is a **RemoteOK** job page. Look for:\n"
        "- Job title in the listing header\n"
        "- Company name and logo area\n"
        "- All jobs here are remote (is_remote=true)\n"
        "- Tech stack tags as skills\n"
        "- Salary range if listed in the posting\n"
    ),
    "weworkremotely": (
        "This is a **WeWorkRemotely** job page. Look for:\n"
        "- Job title in the listing header\n"
        "- Company name in the header area\n"
        "- All jobs here are remote\n"
        "- Description in the main content area\n"
    ),
    "wellfound": (
        "This is a **Wellfound/AngelList** startup job page. Look for:\n"
        "- Job title near the top of the listing\n"
        "- Company name (usually a startup name)\n"
        "- Remote/office location badge\n"
        "- Salary/equity information if listed\n"
        "- Skills in the 'About the role' section\n"
    ),
    "remotive": (
        "This is a **Remotive** job page. Look for:\n"
        "- Job title in the listing header\n"
        "- Company name\n"
        "- All jobs here are remote\n"
        "- Tags/categories as skills\n"
    ),
}

EXTRACTION_SYSTEM_PROMPT = """You are a precise job posting parser. Your job is to extract structured information from job board pages.

Extract the following fields and return them as a JSON object:
- job_title: string — the exact job title (e.g., "Senior Software Engineer")
- company: string — the hiring company name
- is_remote: boolean — true if the job is remote, work-from-home, or distributed
- application_url: string — the direct URL to apply, or empty string if not found
- job_description: string — the full job description text, cleaned and condensed (max 500 chars)
- required_skills: list[string] — a list of explicitly mentioned required skills/technologies
- salary_range: string — salary information if mentioned, empty string otherwise

If you cannot determine a field, use reasonable defaults (empty string, empty list, or false)."""


def extract_job_info(html_text: str, url: str = "") -> dict:
    """Extract structured job details from page HTML/text using Gemini.

    Falls back to regex extraction if Gemini is unavailable or fails.

    Returns:
        dict with keys: job_title, company, is_remote, application_url,
                        job_description, required_skills, salary_range
    """
    # Ensure Gemini is initialized
    init_gemini()

    clean_text = _clean_page_text(html_text)

    # Detect site for tailored extraction
    site_name = _detect_site_name(url)
    site_hint = SITE_EXTRACTION_HINTS.get(site_name, "")
    if site_hint:
        print(f"  └ 🌐 Site detected: {site_name}")

    # ── Try Gemini extraction ──────────────────────────────────────────
    if _genai_available and _genai_model:
        site_instruction = f"\nSite-specific guidance:\n{site_hint}" if site_hint else ""
        prompt = (
            f"Extract job information from the following page content.\n"
            f"The page URL is: {url}{site_instruction}\n\n"
            f"--- PAGE CONTENT ---\n{clean_text}\n"
            f"--- END ---"
        )

        response_text = _call_gemini(
            prompt,
            system_instruction=EXTRACTION_SYSTEM_PROMPT,
            json_mode=True,
        )

        if response_text:
            parsed = _parse_json_response(response_text)
            if parsed:
                print(f"  └ 🤖 Gemini extracted: {parsed.get('job_title', '?')}")
                # Ensure all expected keys exist
                return {
                    "job_title": parsed.get("job_title", "Unknown Position"),
                    "company": parsed.get("company", "Unknown Company"),
                    "is_remote": bool(parsed.get("is_remote", False)),
                    "application_url": parsed.get("application_url", ""),
                    "job_description": parsed.get("job_description", ""),
                    "required_skills": parsed.get("required_skills", []),
                    "salary_range": parsed.get("salary_range", ""),
                }

        print("  └ ⚠️ Gemini extraction failed, falling back to regex")

    # ── Fallback: regex extraction ──────────────────────────────────────
    return _extract_job_info_regex(clean_text)


def _extract_job_info_regex(text: str) -> dict:
    """Fallback regex-based job info extraction."""
    job_title = ""
    company = ""

    # Title patterns
    title_patterns = [
        r"(?:Job Title|Position|Role)[:\s]+(.{2,60}?)(?:\n|$)",
        r"<title>(.*?)</title>",
        r'"jobTitle"\s*:\s*"([^"]+)"',
        r'"title"\s*:\s*"([^"]+)"',
        r'<h1[^>]*>(.*?)</h1>',
    ]
    for pat in title_patterns:
        m = re.search(pat, text, re.IGNORECASE | re.DOTALL)
        if m:
            job_title = re.sub(r"<[^>]+>", "", m.group(1).strip())
            break

    # Company patterns
    company_patterns = [
        r"(?:Company|Organization|Employer)[:\s]+(.{2,60}?)(?:\n|$)",
        r'"company"\s*:\s*"([^"]+)"',
        r'"hiringOrganization"\s*:\s*"([^"]+)"',
        r'@\s*([A-Z][A-Za-z0-9\s&.]+?)(?:\s*\||\s*–|\s*—|\n|$)',
    ]
    for pat in company_patterns:
        m = re.search(pat, text, re.IGNORECASE | re.DOTALL)
        if m:
            company = re.sub(r"<[^>]+>", "", m.group(1).strip())
            break

    is_remote = bool(
        re.search(
            r"remote|work from home|wfh|distributed|virtual|telecommute|100% remote",
            text,
            re.IGNORECASE,
        )
    )

    return {
        "job_title": job_title or "Unknown Position",
        "company": company or "Unknown Company",
        "is_remote": is_remote,
        "application_url": "",
        "job_description": text[:500],
        "required_skills": [],
        "salary_range": "",
    }


# ═══════════════════════════════════════════════════════════════════════════════
# TASK B:  Job Matching
# ═══════════════════════════════════════════════════════════════════════════════

MATCHING_SYSTEM_PROMPT = """You are a hiring matchmaker. Your job is to objectively compare a job posting against a candidate's resume and determine how well they align.

Consider:
1. Required skills vs candidate's skills
2. Years and relevance of experience
3. Education requirements
4. Role seniority level
5. Industry alignment

Be honest and somewhat strict — only say "should_apply" if you genuinely believe the candidate is a strong match.

Return a JSON object with these exact fields:
- match_score: integer (0-100) — overall alignment score
- should_apply: boolean — true if match_score >= the minimum threshold
- reasoning: string — 1-2 sentence explanation
- matching_skills: list[string] — skills from the job that match the candidate
- missing_skills: list[string] — important skills the job requires but the candidate lacks"""


def match_job(job_info: dict, resume: dict) -> bool:
    """Check if a job matches the user's resume criteria using Gemini.

    Considers:
    - Minimum match score from resume config (default 70%)
    - Remote-only preference
    - Gemini-powered skill/experience matching

    Args:
        job_info: dict from extract_job_info()
        resume: dict from load_resume()

    Returns:
        True if the job matches criteria and should be applied to.
    """
    # Ensure Gemini is initialized (in case called before extract_job_info)
    init_gemini()

    preferences = resume.get("preferences", {})
    min_score = _get_min_match_score(resume)
    remote_only = preferences.get("remote_only", True)

    # ── Quick filters (before calling AI) ──────────────────────────────

    # Remote-only check
    if remote_only and not job_info.get("is_remote", False):
        print(f"  └ [MATCH] ❌ Not remote (remote_only={remote_only})")
        return False

    # Unknown position – can't match, skip
    if job_info.get("job_title", "").lower() in ("", "unknown position", "unknown"):
        print("  └ [MATCH] ❌ Unknown position, skipping")
        return False

    # ── Gemini-powered matching ─────────────────────────────────────────
    if _genai_available and _genai_model:
        # Build a compact resume summary for the prompt
        info = resume.get("personal_info", {})
        skills_str = ", ".join(resume.get("skills", [])) or "not specified"
        exp_summary = "; ".join(
            f"{e.get('title', '')} at {e.get('company', '')} ({e.get('years', '?')}yrs)"
            for e in resume.get("experience", [])
        ) or "not specified"
        edu_summary = "; ".join(
            f"{e.get('degree', '')} in {e.get('field', '')}"
            for e in resume.get("education", [])
        ) or "not specified"

        resume_summary = (
            f"Name: {info.get('name', '')}\n"
            f"Headline: {info.get('headline', '')}\n"
            f"Skills: {skills_str}\n"
            f"Experience: {exp_summary}\n"
            f"Education: {edu_summary}"
        )

        prompt = (
            f"--- CANDIDATE RESUME ---\n{resume_summary}\n\n"
            f"--- JOB POSTING ---\n"
            f"Title: {job_info.get('job_title', '')}\n"
            f"Company: {job_info.get('company', '')}\n"
            f"Remote: {job_info.get('is_remote', False)}\n"
            f"Description: {job_info.get('job_description', '')}\n"
            f"Required Skills: {', '.join(job_info.get('required_skills', []))}\n"
            f"Salary: {job_info.get('salary_range', '')}\n\n"
            f"The minimum acceptable match score is {min_score}."
            f" Return should_apply=true only if match_score >= {min_score}."
        )

        response_text = _call_gemini(
            prompt,
            system_instruction=MATCHING_SYSTEM_PROMPT,
            json_mode=True,
        )

        if response_text:
            parsed = _parse_json_response(response_text)
            if parsed:
                score = parsed.get("match_score", 0)
                should = parsed.get("should_apply", False)
                reasoning = parsed.get("reasoning", "")
                matching = parsed.get("matching_skills", [])
                missing = parsed.get("missing_skills", [])

                print(f"  └ [MATCH] 🤖 Score: {score}/100 | Apply: {should}")
                if reasoning:
                    print(f"     └ {reasoning}")
                if matching:
                    print(f"     └ ✅ Matching skills: {', '.join(matching[:5])}")
                if missing:
                    print(f"     └ ❌ Missing skills: {', '.join(missing[:3])}")

                return bool(should)

        print("  └ ⚠️ Gemini matching failed, using fallback logic")

    # ── Fallback matching logic ─────────────────────────────────────────
    # Accept all remote jobs as a safe fallback
    print("  └ [MATCH] ✅ Remote job accepted (fallback mode)")
    return True


# ═══════════════════════════════════════════════════════════════════════════════
# TASK C:  Cover Letter Generation (with Anti-AI protection)
# ═══════════════════════════════════════════════════════════════════════════════

COVER_LETTER_SYSTEM_PROMPT = """You are a human applicant. Write a concise, genuine, and personalized cover letter.

CRITICAL RULES:
- Maximum 200 words
- Address the specific job and company
- Highlight 2-3 specific skills or experiences from the candidate's background that are relevant
- Mention why the candidate is interested in THIS role specifically
- Professional but warm tone
- Include the candidate's name at the end
- Do NOT use generic filler phrases
- Return ONLY the exact text string to be pasted
- DO NOT use Markdown formatting (no **, no __, no `)
- DO NOT use introductory phrases like "Here is the cover letter"
- Keep tone natural and professional like a real human"""


# ═══════════════════════════════════════════════════════════════════════════════
# TASK D:  Form Field Answer Generation (Anti-AI Mode)
# ═══════════════════════════════════════════════════════════════════════════════

FORM_FIELD_SYSTEM_PROMPT = """You are a human applicant filling out a job application form. Provide ONLY the exact text string to be pasted into the form field.

CRITICAL RULES:
- Return ONLY the answer text, nothing else
- DO NOT use Markdown formatting (no **, no __, no `)
- DO NOT use introductory phrases like "The answer is" or "Here is"
- DO NOT use bullet points or numbered lists
- Keep tone natural and professional like a real human
- If the question is about skills/experience, be specific and factual
- If the question is yes/no, answer with just "Yes" or "No"
- If the question requires a number, provide just the number
- Keep answers concise (under 100 words unless more is clearly needed)"""


def generate_form_answer(question: str, resume: dict, field_type: str = "text") -> str:
    """Generate a human-like answer for a job application form field.
    
    Uses Anti-AI mode with strict prompts and low temperature to prevent
    HR detection of automated text generation.
    
    Args:
        question: The form field question or label text.
        resume: dict from load_resume().
        field_type: Type of field ('text', 'yes_no', 'number', 'textarea').
    
    Returns:
        A clean, human-like answer string.
    """
    init_gemini()
    
    if not _genai_available or not _genai_model:
        # Fallback to simple template-based answers
        return _fallback_form_answer(question, resume, field_type)
    
    info = resume.get("personal_info", {})
    skills_str = ", ".join(resume.get("skills", [])) or "various technical skills"
    exp_str = "; ".join(
        f"{e.get('title', '')} at {e.get('company', '')}"
        for e in resume.get("experience", [])
    ) or "background in the field"
    
    prompt = (
        f"Question: {question}\n\n"
        f"About the applicant:\n"
        f"Name: {info.get('name', 'Applicant')}\n"
        f"Skills: {skills_str}\n"
        f"Experience: {exp_str}\n"
        f"Location: {info.get('location', 'Remote')}\n"
        f"Field type: {field_type}\n\n"
        f"Provide a natural, human-like answer suitable for this field."
    )
    
    response_text = _call_gemini(
        prompt,
        system_instruction=FORM_FIELD_SYSTEM_PROMPT,
        json_mode=False,
        anti_ai_mode=True,  # Enable strict anti-detection settings
    )
    
    if response_text:
        # Clean any remaining AI artifacts
        cleaned = _clean_ai_text(response_text)
        if len(cleaned.strip()) > 0:
            print(f"  └ 🤖 Generated form answer ({len(cleaned)} chars)")
            return cleaned
    
    print("  └ ⚠️ AI form answer failed, using fallback")
    return _fallback_form_answer(question, resume, field_type)


def _fallback_form_answer(question: str, resume: dict, field_type: str = "text") -> str:
    """Fallback template-based form answers when AI is unavailable."""
    question_lower = question.lower()
    info = resume.get("personal_info", {})
    
    # Yes/No questions
    if field_type == "yes_no":
        if any(word in question_lower for word in ["authorized", "eligible", "right to work"]):
            return "Yes"
        elif any(word in question_lower for word in ["sponsor", "visa", "require sponsorship"]):
            return "No"
        elif any(word in question_lower for word in ["felony", "criminal", "convicted"]):
            return "No"
        elif any(word in question_lower for word in ["currently employed", "working now"]):
            return "Yes"
    
    # Name
    if any(word in question_lower for word in ["first name", "given name"]):
        return info.get("first_name", info.get("name", "").split()[0] if " " in info.get("name", "") else info.get("name", ""))
    elif any(word in question_lower for word in ["last name", "family name", "surname"]):
        return info.get("last_name", "")
    elif "name" in question_lower:
        return info.get("name", "")
    
    # Contact
    if "email" in question_lower:
        return info.get("email", "")
    elif "phone" in question_lower:
        return info.get("phone", "")
    elif "linkedin" in question_lower:
        return f"https://linkedin.com/in/{info.get('linkedin_username', '')}"
    elif "portfolio" in question_lower or "website" in question_lower:
        return info.get("portfolio", "")
    
    # Location
    if "location" in question_lower or "city" in question_lower:
        return info.get("location", "Remote")
    
    # Skills/Experience
    if "skill" in question_lower or "technology" in question_lower:
        return ", ".join(resume.get("skills", [])) or "Python, JavaScript, Web3"
    elif "experience" in question_lower or "background" in question_lower:
        exp = resume.get("experience", [])
        if exp:
            return f"{exp[0].get('title', '')} at {exp[0].get('company', '')}"
        return "Software Development"
    
    # Salary
    if "salary" in question_lower or "compensation" in question_lower:
        return "Negotiable"
    
    # Start date
    if "start" in question_lower or "available" in question_lower:
        return "Two weeks notice"
    
    # Demographics - decline
    if any(word in question_lower for word in ["gender", "race", "ethnicity", "veteran", "disability"]):
        return "Decline to self-identify"
    
    # Default fallback
    return ""


def generate_cover_letter(job_info: dict, resume: dict) -> str:
    """Generate a customized, specific cover letter using Gemini.

    Falls back to a template-based letter if Gemini is unavailable.

    Args:
        job_info: dict from extract_job_info()
        resume: dict from load_resume()

    Returns:
        A cover letter string.
    """
    # Ensure Gemini is initialized (in case called before extract_job_info)
    init_gemini()

    # ── Try Gemini generation ───────────────────────────────────────────
    if _genai_available and _genai_model:
        info = resume.get("personal_info", {})
        skills_str = ", ".join(resume.get("skills", [])) or "various technical skills"
        exp_str = "; ".join(
            f"{e.get('title', '')} at {e.get('company', '')}"
            for e in resume.get("experience", [])
        ) or "background in the field"

        prompt = (
            f"Write a short, personalized cover letter for:\n\n"
            f"**Job:** {job_info.get('job_title', 'the position')}\n"
            f"**Company:** {job_info.get('company', 'the company')}\n"
            f"**Job Description:** {job_info.get('job_description', '')[:1000]}\n"
            f"**Required Skills:** {', '.join(job_info.get('required_skills', []))}\n\n"
            f"**About the Candidate:**\n"
            f"Name: {info.get('name', 'Applicant')}\n"
            f"Skills: {skills_str}\n"
            f"Experience: {exp_str}\n"
            f"Portfolio: {info.get('portfolio', '')}\n"
            f"LinkedIn: https://linkedin.com/in/{info.get('linkedin_username', '')}\n\n"
            f"The letter should be specific to this job, mentioning relevant skills "
            f"from the candidate's background that match the job requirements. "
            f"Maximum 200 words. Professional but warm tone. "
            f"Sign with the candidate's name at the end."
        )

        response_text = _call_gemini(
            prompt,
            system_instruction=COVER_LETTER_SYSTEM_PROMPT,
            json_mode=False,
            anti_ai_mode=True,  # Enable strict anti-detection settings
        )

        if response_text and len(response_text.strip()) > 50:
            # Clean any remaining AI artifacts
            cleaned = _clean_ai_text(response_text)
            print(f"  └ ✍️ Gemini generated cover letter ({len(cleaned)} chars)")
            return cleaned.strip()

        print("  └ ⚠️ Gemini cover letter failed, using template")

    # ── Fallback: template-based letter ─────────────────────────────────
    name = resume.get("personal_info", {}).get("name", "Applicant")
    portfolio = resume.get("personal_info", {}).get("portfolio", "")
    template = resume.get("cover_letter_template", "")

    if template:
        try:
            return template.format(
                job_title=job_info.get("job_title", "the position"),
                company=job_info.get("company", "your company"),
            )
        except KeyError:
            pass

    return (
        f"Dear Hiring Manager,\n\n"
        f"I am writing to express my strong interest in the "
        f"{job_info.get('job_title', 'open position')} "
        f"position at {job_info.get('company', 'your company')}. "
        f"As a dedicated professional with a proven track record, I am "
        f"confident that my skills and experience make me an excellent "
        f"candidate for this role.\n\n"
        f"I am particularly drawn to this opportunity because it aligns "
        f"with my career goals and expertise. I am eager to contribute "
        f"to your team and help drive success.\n\n"
        f"You can learn more about my work at {portfolio}.\n\n"
        f"Thank you for your time and consideration.\n\n"
        f"Best regards,\n{name}"
    )
