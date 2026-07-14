"""
Web3 Jobs API Integration
Fetches job listings from the web3.career API and formats them
for the Auto Job Hunter pipeline.

API Docs: https://docs.bondex.app/api-reference
"""
import json
import os
import re
import time
from typing import Optional
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError

# ─── Configuration ──────────────────────────────────────────────────────────────

WEB3_API_TOKEN = os.getenv("WEB3_API_TOKEN") or ""
API_BASE_URL = "https://web3.career/api/v1"
DEFAULT_LIMIT = 50          # max jobs per fetch (API limit: 100)
REQUEST_TIMEOUT = 15        # seconds
RETRY_DELAY = 5             # seconds between retries
MAX_RETRIES = 3

# ─── Fetcher ────────────────────────────────────────────────────────────────────

def fetch_jobs(
    limit: int = DEFAULT_LIMIT,
    remote_only: bool = True,
    tags: Optional[list[str]] = None,
    country: Optional[str] = None,
) -> list[dict]:
    """Fetch job listings from the Web3 Jobs API.

    Args:
        limit: Max jobs to return (1-100).
        remote_only: If True, only return remote jobs.
        tags: Filter by technology/role tags (e.g. ["solidity", "rust"]).
        country: Filter by country slug.

    Returns:
        List of job dicts with keys matching our job_info format.
        Returns empty list on failure.
    """
    if not WEB3_API_TOKEN:
        print("  └ ⚠️  WEB3_API_TOKEN not set — skipping Web3 Jobs API")
        return []

    # Build query parameters
    params = [f"token={WEB3_API_TOKEN}", f"limit={min(max(1, limit), 100)}"]

    if remote_only:
        params.append("remote=1")

    if tags:
        params.append(f"tags={','.join(tags)}")

    if country:
        params.append(f"country={country}")

    url = f"{API_BASE_URL}?{'&'.join(params)}"

    # Attempt the request with retry logic
    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            req = Request(url, headers={"User-Agent": "AutoJobBot/1.0"})
            with urlopen(req, timeout=REQUEST_TIMEOUT) as response:
                raw = response.read().decode("utf-8")
                data = json.loads(raw)

            # Parse the response format:
            # [0] = info string, [1] = terms string, [2] = array of job objects
            if isinstance(data, list) and len(data) >= 3:
                jobs_raw = data[2] if isinstance(data[2], list) else []
            elif isinstance(data, list) and len(data) >= 2 and isinstance(data[1], list):
                jobs_raw = data[1]
            elif isinstance(data, dict) and "jobs" in data:
                jobs_raw = data["jobs"]
            else:
                jobs_raw = data if isinstance(data, list) else []

            # Convert to our standard job_info format
            jobs = [_normalize_job(j) for j in jobs_raw if isinstance(j, dict)]
            jobs = [j for j in jobs if j is not None]

            print(f"  └ 🌐 Web3 Jobs API: fetched {len(jobs)} jobs from {len(jobs_raw)} entries")
            return jobs

        except HTTPError as e:
            if e.code == 429:
                wait = RETRY_DELAY * (2 ** attempt)
                print(f"  └ ⏳ Web3 API rate limited, retrying in {wait}s...")
                time.sleep(wait)
                last_error = f"HTTP {e.code}"
            elif e.code == 403:
                print("  └ ❌ Web3 API: 403 Forbidden — token may be invalid")
                return []
            elif e.code == 401:
                print("  └ ❌ Web3 API: 401 Unauthorized — token is invalid")
                return []
            else:
                print(f"  └ ⚠️ Web3 API HTTP error {e.code}: {e}")
                return []

        except (URLError, OSError) as e:
            wait = RETRY_DELAY * (2 ** attempt)
            print(f"  └ ⏳ Web3 API connection error: {e}, retrying in {wait}s...")
            time.sleep(wait)
            last_error = str(e)

        except json.JSONDecodeError as e:
            print(f"  └ ❌ Web3 API: invalid JSON response: {e}")
            return []

    print(f"  └ ❌ Web3 API: all {MAX_RETRIES} attempts failed: {last_error}")
    return []


def _normalize_job(raw: dict) -> Optional[dict]:
    """Convert a raw API job entry to our standard job_info format.

    Expected raw fields:
        id, title, company, is_remote, apply_url, tags, location,
        description, date, salary_min_value, salary_max_value, salary_currency
    """
    if not raw or not raw.get("title"):
        return None

    # Clean HTML from description
    description = raw.get("description") or ""
    if description:
        description = re.sub(r"<[^>]+>", " ", description)
        description = re.sub(r"\s+", " ", description).strip()
        description = description[:2000]  # Limit length

    # Format salary
    salary_min = raw.get("salary_min_value")
    salary_max = raw.get("salary_max_value")
    salary_currency = raw.get("salary_currency") or ""
    salary_range = ""
    if salary_min or salary_max:
        if salary_min and salary_max:
            salary_range = f"{salary_currency}{salary_min:,.0f} - {salary_currency}{salary_max:,.0f}"
        elif salary_min:
            salary_range = f"From {salary_currency}{salary_min:,.0f}"
        elif salary_max:
            salary_range = f"Up to {salary_currency}{salary_max:,.0f}"

    return {
        "job_title": raw.get("title", "Unknown Position"),
        "company": raw.get("company", "Unknown Company"),
        "is_remote": bool(raw.get("is_remote", False)),
        "application_url": raw.get("apply_url", ""),
        "job_description": description,
        "required_skills": raw.get("tags", []),
        "salary_range": salary_range,
        "source": "web3",
        "source_id": str(raw.get("id", "")),
        "date_posted": raw.get("date", ""),
        "location": raw.get("location", ""),
    }


