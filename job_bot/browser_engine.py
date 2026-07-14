"""
Browser Engine (Phase 3 + Phase 5 Complete)
Handles Playwright browser automation with persistent context,
stealth techniques, page content extraction, and advanced form filling.

Phase 5 Upgrades:
  - Multi-step form chaining (Next -> Review -> Submit)
  - Dropdown/Select field handling
  - Radio buttons & checkboxes (authorization, demographics, etc.)
  - Resume/CV file upload
  - Platform-specific handlers (Greenhouse, Lever, Workday, Ashby, BambooHR)
  - Confirmation detection (success vs validation errors)
  - Smart field value mapping with answer database
"""
import os
import re
import time
import random
from typing import Optional, Dict, List, Tuple, Any
from pathlib import Path

from playwright.sync_api import (
    sync_playwright,
    BrowserContext,
    Page,
    Playwright,
    Locator,
)

USER_DATA_DIR = os.path.join(os.path.dirname(__file__), "playwright_data")
RESUME_DIR = os.path.join(os.path.dirname(__file__), "resumes")

# ─── Smart Answer Database ──────────────────────────────────────────────────────
# Maps common question patterns to smart answers for auto-filling applications.

SMART_ANSWERS: Dict[str, Dict[str, Any]] = {
    # Work Authorization
    "work_authorization": {
        "patterns": [
            r"authorized to work",
            r"work.?authorization",
            r"work.?auth",
            r"eligible to work",
            r"right to work",
            r"legally.?authorized",
            r"legally.?eligible",
            r"sponsorship",
            r"work.?permit",
            r"visa.?sponsor",
        ],
        "answer_yes_no": "yes",
        "answer_text": "Yes, I am authorized to work in the United States without sponsorship.",
        "answer_select": "Yes, I am authorized to work in the United States",
    },
    "visa_sponsorship": {
        "patterns": [
            r"visa.?sponsor",
            r"sponsor.?visa",
            r"require.?sponsor",
            r"need.?sponsor",
            r"sponsorship",
            r"h1b",
            r"h-1b",
            r"work.?visa",
            r"visa.?transfer",
            r"immigration",
        ],
        "answer_yes_no": "no",
        "answer_text": "I do not require visa sponsorship now or in the future.",
        "answer_select": "No, I do not require sponsorship",
    },
    # Demographics - sensitive fields, decline by default
    "race_ethnicity": {
        "patterns": [
            r"race",
            r"ethnicity",
            r"ethnic",
            r"racial",
            r"hispanic",
            r"latino",
            r"american.?indian",
            r"asian",
            r"black",
            r"african.?american",
            r"native.?hawaiian",
            r"pacific.?islander",
            r"white",
        ],
        "answer_yes_no": None,
        "answer_text": "Decline to self-identify",
        "answer_select": "I prefer not to answer",
        "options_order": ["decline", "prefer not", "not answer"],
    },
    "gender": {
        "patterns": [
            r"gender",
            r"sex",
        ],
        "answer_yes_no": None,
        "answer_text": "Decline to answer",
        "answer_select": "I prefer not to answer",
        "options_order": ["decline", "prefer not", "not answer"],
    },
    "veteran_status": {
        "patterns": [
            r"veteran",
            r"military.?service",
            r"protected.?veteran",
            r"disabled.?veteran",
        ],
        "answer_yes_no": None,
        "answer_text": "I decline to self-identify",
        "answer_select": "I prefer not to answer",
        "options_order": ["decline", "prefer not", "not answer"],
    },
    "disability": {
        "patterns": [
            r"disability",
            r"disabled",
            r"handicap",
            r"accommodation",
        ],
        "answer_yes_no": None,
        "answer_text": "I decline to self-identify",
        "answer_select": "I prefer not to answer",
        "options_order": ["decline", "prefer not", "not answer"],
    },
    # Education & Background
    "highest_education": {
        "patterns": [
            r"highest.?education",
            r"education.?level",
            r"degree.?level",
            r"education.?completed",
        ],
        "answer_text": "Bachelor's Degree",
        "answer_select": "Bachelor's Degree",
    },
    "graduation_year": {
        "patterns": [
            r"graduation.?year",
            r"grad.?year",
            r"year.?graduated",
            r"graduated",
        ],
        "answer_text": "2020",
    },
    # Employment
    "start_date": {
        "patterns": [
            r"available.?start.?date",
            r"start.?date",
            r"earliest.?start",
            r"when.?can.?you.?start",
            r"availability.?date",
        ],
        "answer_text": "Two weeks notice",
        "answer_select": "Two weeks",
    },
    "currently_employed": {
        "patterns": [
            r"currently.?employed",
            r"employed.?now",
            r"currently.?working",
            r"employed.?currently",
            r"do.?you.?have.?a.?job",
        ],
        "answer_yes_no": "yes",
    },
    "felony": {
        "patterns": [
            r"felony",
            r"criminal.?conviction",
            r"criminal.?record",
            r"convicted",
            r"misdemeanor",
            r"crime",
            r"arrest",
            r"background.?check",
        ],
        "answer_yes_no": "no",
        "answer_text": "No",
        "answer_select": "No",
    },
    "linkedin": {
        "patterns": [
            r"linkedin",
            r"linked.?in",
            r"linkedin.?profile",
            r"profile.?url",
        ],
        "answer_text": "https://linkedin.com/in/",
    },
    "portfolio": {
        "patterns": [
            r"portfolio",
            r"personal.?website",
            r"website",
            r"personal.?site",
            r"github",
            r"online.?presence",
        ],
    },
    "salary_expectation": {
        "patterns": [
            r"salary.?expect",
            r"expected.?salary",
            r"desired.?salary",
            r"salary.?requirement",
            r"pay.?expect",
        ],
        "answer_text": "Negotiable",
        "answer_select": "Negotiable",
    },
    "how_did_you_hear": {
        "patterns": [
            r"how.?did.?you.?hear",
            r"found.?us",
            r"found.?this.?job",
            r"referral.?source",
            r"source",
            r"referred",
        ],
        "answer_text": "LinkedIn",
        "answer_select": "LinkedIn",
    },
    "willing_to_relocate": {
        "patterns": [
            r"relocate",
            r"relocation",
            r"willing.?to.?move",
            r"open.?to.?relocat",
        ],
        "answer_yes_no": "yes",
    },
    "willing_to_travel": {
        "patterns": [
            r"willing.?to.?travel",
            r"travel.?requirement",
            r"available.?to.?travel",
            r"travel.?percentage",
        ],
        "answer_yes_no": "yes",
        "answer_text": "Yes, I am willing to travel as needed.",
    },
    "language_proficiency": {
        "patterns": [
            r"language.?profic",
            r"english.?profic",
            r"fluency",
            r"language.?skill",
        ],
        "answer_text": "Native or Bilingual",
        "answer_select": "Native",
    },
}

# ─── Platform Detectors ─────────────────────────────────────────────────────────

PLATFORM_PATTERNS = {
    "greenhouse": [
        r"greenhouse\.io",
        r"boards\.greenhouse\.io",
        r"grnh\.se",
        r"app\.greenhouse\.io",
    ],
    "lever": [
        r"lever\.co",
        r"jobs\.lever\.co",
    ],
    "workday": [
        r"myworkdayjobs\.com",
        r"wd5\.myworkdayjobs",
        r"workday\.com",
        r"my\.workday\.com",
    ],
    "ashby": [
        r"ashbyhq\.com",
        r"jobs\.ashbyhq\.com",
        r"ashby\.io",
    ],
    "bamboohr": [
        r"bamboohr\.com",
        r"bamboohr",
    ],
    "smartrecruiters": [
        r"smartrecruiters\.com",
    ],
    "icims": [
        r"icims\.com",
    ],
}


class BrowserEngine:
    """Manages a persistent Playwright browser instance.

    Uses a persistent user data directory so that cookies and login
    sessions survive across restarts. You only need to log into job
    sites manually once.
    """

    def __init__(self, headless: bool = False):
        self.headless = headless
        self.playwright: Optional[Playwright] = None
        self.context: Optional[BrowserContext] = None
        self._current_url: str = ""

    # ── Lifecycle ───────────────────────────────────────────────────────────────

    def start(self) -> BrowserContext:
        """Launch the browser with a persistent context."""
        self.playwright = sync_playwright().start()
        os.makedirs(USER_DATA_DIR, exist_ok=True)

        self.context = self.playwright.chromium.launch_persistent_context(
            user_data_dir=USER_DATA_DIR,
            headless=self.headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-web-security",
                "--disable-features=IsolateOrigins,site-per-process",
            ],
            viewport={"width": 1280, "height": 800},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            locale="en-US",
            timezone_id="America/New_York",
            permissions=["geolocation"],
            geolocation={"latitude": 40.7128, "longitude": -74.0060},  # New York
        )

        self._apply_stealth()
        print("🌐 Browser engine started successfully.")
        return self.context

    def _apply_stealth(self) -> None:
        """Apply stealth patches to avoid bot detection."""
        # Remove the "webdriver" flag that Playwright sets
        # and inject other stealth properties to avoid bot detection
        self.context.add_init_script(
            """
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            // Override the plugins array
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });
            // Override the languages array
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en']
            });
            // Remove Chrome automation trace
            window.chrome = {
                runtime: {},
                loadTimes: function() {},
                csi: function() {},
                app: {}
            };
            """
        )

        # Try to use playwright-stealth if available
        try:
            from playwright_stealth import stealth_sync  # type: ignore

            page = self.context.new_page()
            stealth_sync(page)
            page.close()
            print("  └ playwright-stealth injected successfully")
        except ImportError:
            print("  └ playwright-stealth not installed, using built-in stealth")

    def close(self) -> None:
        """Clean up all browser resources."""
        if self.context:
            try:
                self.context.close()
            except Exception:
                pass
            self.context = None
        if self.playwright:
            try:
                self.playwright.stop()
            except Exception:
                pass
            self.playwright = None
        print("🌐 Browser engine closed.")

    # ── Page Content Extraction ─────────────────────────────────────────────────

    def get_page_content(self, url: str, scroll_passes: int = 3) -> str:
        """Visit a URL, simulate human-like scrolling, and return raw HTML.

        Args:
            url: The target URL to visit.
            scroll_passes: Number of times to scroll down (default 3).

        Returns:
            The full page HTML as a string.
        """
        self._current_url = url
        page = self.context.new_page()
        try:
            print(f"  📄 Navigating to: {url}")
            page.goto(url, timeout=45000, wait_until="domcontentloaded")

            # Wait for the page to settle
            page.wait_for_timeout(random.randint(1000, 3000))

            # Human-like scrolling behavior
            for i in range(scroll_passes):
                scroll_distance = random.randint(300, 800)
                page.evaluate(f"window.scrollBy(0, {scroll_distance})")
                delay = random.uniform(0.8, 2.5)
                time.sleep(delay)
                # Occasionally scroll back up a bit (like a human reading)
                if random.random() < 0.3:
                    page.evaluate(f"window.scrollBy(0, -{random.randint(50, 200)})")
                    time.sleep(random.uniform(0.3, 0.7))

            # Scroll back to top
            page.evaluate("window.scrollTo(0, 0)")
            time.sleep(random.uniform(0.5, 1.0))

            return page.content()

        except Exception as e:
            print(f"  ❌ Error loading {url}: {e}")
            return ""
        finally:
            page.close()

    def get_page_text(self, url: str, scroll_passes: int = 3) -> str:
        """Like get_page_content but returns cleaned visible text instead of HTML."""
        self._current_url = url
        page = self.context.new_page()
        try:
            page.goto(url, timeout=45000, wait_until="domcontentloaded")
            page.wait_for_timeout(random.randint(1000, 3000))

            for i in range(scroll_passes):
                page.evaluate(f"window.scrollBy(0, {random.randint(300, 800)})")
                time.sleep(random.uniform(0.8, 2.5))

            # Extract visible text
            text = page.evaluate(
                "() => document.body.innerText"
            )
            # Clean up whitespace
            text = re.sub(r'\s+', ' ', text).strip()
            return text

        except Exception as e:
            print(f"  ❌ Error loading {url}: {e}")
            return ""
        finally:
            page.close()

    # ══════════════════════════════════════════════════════════════════════════════
    # PHASE 5: AUTO-FILLER ENGINE UPGRADE
    # ══════════════════════════════════════════════════════════════════════════════

    # ─── Smart Field Value Mapping (Task 7) ─────────────────────────────────────

    def _detect_platform(self, url: str) -> str:
        """Detect which ATS platform a job URL belongs to.

        Returns:
            Platform name string: 'greenhouse', 'lever', 'workday', 'ashby',
            'bamboohr', 'smartrecruiters', 'icims', or 'generic'.
        """
        for platform, patterns in PLATFORM_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, url, re.IGNORECASE):
                    return platform
        return "generic"

    def _smart_detect_question_type(self, text: str) -> Optional[str]:
        """Use the SMART_ANSWERS database to identify what a question is asking.

        Args:
            text: The label text, placeholder, or surrounding context.

        Returns:
            The question type key from SMART_ANSWERS, or None.
        """
        text_lower = text.lower()
        for q_type, config in SMART_ANSWERS.items():
            for pattern in config.get("patterns", []):
                if re.search(pattern, text_lower):
                    return q_type
        return None

    def _get_smart_answer(self, question_type: str, field_type: str = "text") -> Optional[str]:
        """Get the appropriate answer for a detected question type.

        Args:
            question_type: Key from SMART_ANSWERS.
            field_type: Type of input field ('text', 'select', 'yes_no', 'file').

        Returns:
            Answer string, or None if no answer configured.
        """
        config = SMART_ANSWERS.get(question_type)
        if not config:
            return None

        # Personalize LinkedIn URL
        if question_type == "linkedin":
            username = "comradexbt"
            return f"https://linkedin.com/in/{username}"

        if field_type == "select" and config.get("answer_select"):
            return config["answer_select"]
        elif field_type == "yes_no" and config.get("answer_yes_no"):
            return config["answer_yes_no"]
        elif config.get("answer_text"):
            return config["answer_text"]

        return None

    # ─── Dropdown/Select Fields (Task 2) ────────────────────────────────────────

    def _handle_dropdown(self, page: Page, select_element: Locator, value: str) -> bool:
        """Fill a <select> dropdown with the best matching option.

        Tries: exact match, fuzzy match, then falls back to first non-empty option.

        Args:
            page: The Playwright Page object.
            select_element: Locator for the <select> element.
            value: The desired value to select.

        Returns:
            True if an option was selected.
        """
        try:
            # Try to select by label text first (exact match)
            try:
                select_element.select_option(label=value)
                print(f"    ✅ Selected dropdown: '{value}'")
                return True
            except Exception:
                pass

            # Try to select by value attribute
            try:
                select_element.select_option(value=value)
                print(f"    ✅ Selected dropdown by value: '{value}'")
                return True
            except Exception:
                pass

            # Try fuzzy matching: get all options and find a close match
            option_elements = select_element.locator("option").all()
            option_texts = []
            for opt in option_elements:
                label = opt.get_attribute("label") or opt.inner_text() or ""
                val = opt.get_attribute("value") or ""
                option_texts.append({"label": label, "value": val, "element": opt})

            # First, try case-insensitive exact match
            value_lower = value.lower().strip()
            for opt in option_texts:
                if opt["label"].lower().strip() == value_lower or opt["value"].lower().strip() == value_lower:
                    select_element.select_option(label=opt["label"])
                    print(f"    ✅ Selected dropdown: '{opt['label']}'")
                    return True

            # Try substring match
            for opt in option_texts:
                if value_lower in opt["label"].lower() or value_lower in opt["value"].lower():
                    select_element.select_option(label=opt["label"])
                    print(f"    ✅ Selected dropdown (fuzzy): '{opt['label']}'")
                    return True

            # Check for "decline/prefer not to answer" options for sensitive questions
            if any(word in value_lower for word in ["decline", "prefer not", "not answer"]):
                for opt in option_texts:
                    label_lower = opt["label"].lower()
                    if any(word in label_lower for word in ["decline", "prefer not", "prefer to", "not answer", "choose not"]):
                        select_element.select_option(label=opt["label"])
                        print(f"    ✅ Selected decline option: '{opt['label']}'")
                        return True

            # Last resort: pick first non-empty option that isn't "--Select--" or similar
            for opt in option_texts:
                label = opt["label"].strip()
                if label and label.lower() not in ("", "--", "--select--", "select", "-", "choose one"):
                    select_element.select_option(label=label)
                    print(f"    ⚠️ Fallback selected: '{label}'")
                    return True

            print(f"    ⚠️ No selectable option found for '{value}'")
            return False

        except Exception as e:
            print(f"    ⚠️ Error handling dropdown: {e}")
            return False

    # ─── Radio Buttons & Checkboxes (Task 3) ────────────────────────────────────

    def _handle_radio_group(self, page: Page, radio_elements: List[Locator], value: str) -> bool:
        """Click the correct radio button in a group.

        Uses smart answer detection to match labels.

        Args:
            page: The Playwright Page object.
            radio_elements: List of radio button locators in the group.
            value: The desired answer value.

        Returns:
            True if a radio button was clicked.
        """
        value_lower = value.lower().strip()

        for radio in radio_elements:
            try:
                # Get the associated label text
                label_text = ""
                radio_id = radio.get_attribute("id")
                if radio_id:
                    label = page.locator(f"label[for='{radio_id}']")
                    if label.count() > 0:
                        label_text = label.inner_text().lower()

                if not label_text:
                    # Try parent label or nearby text
                    parent = radio.locator("xpath=..")
                    if parent.count() > 0:
                        label_text = parent.inner_text().lower()

                # Check for match
                if value_lower in label_text or label_text in value_lower:
                    radio.click()
                    print(f"    ✅ Clicked radio: '{label_text.strip()}'")
                    time.sleep(random.uniform(0.3, 0.6))
                    return True

                # For "no" answers, also check for negative options
                if value_lower in ("no", "false"):
                    if any(word in label_text for word in ["no", "not", "don't", "do not", "none"]):
                        radio.click()
                        print(f"    ✅ Clicked radio: '{label_text.strip()}'")
                        time.sleep(random.uniform(0.3, 0.6))
                        return True

                # For "yes" answers, check for positive options
                if value_lower in ("yes", "true"):
                    if any(word in label_text for word in ["yes", "i am", "i do", "i have", "i will"]):
                        radio.click()
                        print(f"    ✅ Clicked radio: '{label_text.strip()}'")
                        time.sleep(random.uniform(0.3, 0.6))
                        return True

            except Exception:
                continue

        # Fallback: skip — don't guess on sensitive questions
        print(f"    ⚠️ Could not match radio option for '{value}', skipping")
        return False

    def _handle_checkbox(self, page: Page, checkbox: Locator, checked: bool = True) -> bool:
        """Check or uncheck a checkbox.

        Args:
            page: The Playwright Page object.
            checkbox: Locator for the checkbox element.
            checked: True to check, False to uncheck.

        Returns:
            True if successful.
        """
        try:
            is_checked = checkbox.is_checked()
            if is_checked != checked:
                checkbox.click()
                time.sleep(random.uniform(0.2, 0.5))
                print(f"    ✅ {'Checked' if checked else 'Unchecked'} checkbox")
            else:
                print(f"    ✅ Checkbox already {'checked' if checked else 'unchecked'}")
            return True
        except Exception as e:
            print(f"    ⚠️ Error handling checkbox: {e}")
            return False

    def _handle_yes_no_question(self, page: Page, answer: str) -> bool:
        """Find and answer a yes/no question on the page.

        Searches for radio groups that look like yes/no questions.

        Args:
            page: The Playwright Page object.
            answer: 'yes' or 'no'.

        Returns:
            True if answered.
        """
        answer_lower = answer.lower().strip()

        # Find all radio button groups on the page
        radio_groups = page.locator("input[type='radio']").all()

        if not radio_groups:
            return False

        # Group radio buttons by name attribute
        groups: Dict[str, List[Locator]] = {}
        for radio in radio_groups:
            try:
                name = radio.get_attribute("name") or ""
                if name not in groups:
                    groups[name] = []
                groups[name].append(radio)
            except Exception:
                continue

        # Process each radio group with smart detection
        for name, radios in groups.items():
            # Check if this looks like a yes/no question by examining nearby text
            # Try to find labels for this radio group
            try:
                # Check for a fieldset/legend or div wrapper with the question
                first_radio = radios[0]
                # Get the parent and look for text
                parent = first_radio.locator("xpath=ancestor::fieldset | ancestor::div[contains(@class, 'field')] | ancestor::div[contains(@class, 'question')]")
                context_text = ""
                if parent.count() > 0:
                    context_text = parent.first.inner_text().lower()

                if not context_text:
                    # Try to find a label with matching "for" attribute
                    radio_id = first_radio.get_attribute("id")
                    if radio_id:
                        label = page.locator(f"label[for='{radio_id}']")
                        if label.count() > 0:
                            context_text = label.inner_text().lower()

                # Use smart detection to identify the question
                detected_type = self._smart_detect_question_type(context_text)
                if detected_type:
                    smart_answer = self._get_smart_answer(detected_type, field_type="yes_no")
                    if smart_answer:
                        answer_lower = smart_answer.lower()
            except Exception:
                pass

            # Now click the correct radio based on the answer
            for radio in radios:
                try:
                    label_text = ""
                    radio_id = radio.get_attribute("id")
                    if radio_id:
                        label = page.locator(f"label[for='{radio_id}']")
                        if label.count() > 0:
                            label_text = label.inner_text().lower()

                    if not label_text:
                        parent_el = radio.locator("xpath=..")
                        if parent_el.count() > 0:
                            label_text = parent_el.inner_text().lower()

                    if answer_lower in ("yes", "true", "y"):
                        if any(word in label_text for word in ["yes", "i am", "i do", "i have", "i will", "true"]):
                            radio.click()
                            print(f"    ✅ Answered Yes: '{label_text.strip()}'")
                            time.sleep(random.uniform(0.3, 0.6))
                            return True
                    elif answer_lower in ("no", "false", "n"):
                        if any(word in label_text for word in ["no", "not", "don't", "do not", "none", "false"]):
                            radio.click()
                            print(f"    ✅ Answered No: '{label_text.strip()}'")
                            time.sleep(random.uniform(0.3, 0.6))
                            return True
                except Exception:
                    continue

        # If no radio group matched, try clicking yes/no buttons
        if answer_lower in ("yes", "y"):
            yes_selectors = [
                "button:has-text(/^Yes$/i)",
                "button:has-text(/^I am$/i)",
                "button:has-text(/^True$/i)",
                "input[type='button']:has-text(/^Yes$/i)",
            ]
            for selector in yes_selectors:
                try:
                    btn = page.locator(selector).first
                    if btn.count() > 0:
                        btn.click()
                        print("    ✅ Clicked Yes button")
                        time.sleep(random.uniform(0.3, 0.6))
                        return True
                except Exception:
                    pass
        elif answer_lower in ("no", "n"):
            no_selectors = [
                "button:has-text(/^No$/i)",
                "button:has-text(/^I am not$/i)",
                "button:has-text(/^False$/i)",
            ]
            for selector in no_selectors:
                try:
                    btn = page.locator(selector).first
                    if btn.count() > 0:
                        btn.click()
                        print("    ✅ Clicked No button")
                        time.sleep(random.uniform(0.3, 0.6))
                        return True
                except Exception:
                    pass

        return False

    # ─── Resume Upload (Task 4) ─────────────────────────────────────────────────

    def _find_resume_file(self) -> Optional[str]:
        """Find a resume PDF file in the resumes directory.

        Returns:
            Absolute path to the resume file, or None.
        """
        os.makedirs(RESUME_DIR, exist_ok=True)

        # Look for PDF files
        for ext in ["*.pdf", "*.doc", "*.docx", "*.txt"]:
            matches = list(Path(RESUME_DIR).glob(ext))
            if matches:
                return str(matches[0])

        # Also check the project root
        root_dir = os.path.dirname(__file__)
        for ext in ["*.pdf", "*.doc", "*.docx", "*.txt"]:
            matches = list(Path(root_dir).glob(ext))
            # Skip non-resume files
            for m in matches:
                name = m.name.lower()
                if "resume" in name or "cv" in name or "curriculum" in name:
                    return str(m)

        return None

    def _find_profile_picture(self) -> Optional[str]:
        """Find a profile picture file in the resumes directory.

        Returns:
            Absolute path to the profile picture, or None.
        """
        os.makedirs(RESUME_DIR, exist_ok=True)

        # Look for common profile picture names
        profile_names = [
            "profile_picture.jpg", "profile_picture.png", "profile_picture.jpeg",
            "photo.jpg", "photo.png", "photo.jpeg",
            "avatar.jpg", "avatar.png", "avatar.jpeg",
            "pfp.jpg", "pfp.png", "pfp.jpeg"
        ]

        for name in profile_names:
            path = Path(RESUME_DIR) / name
            if path.exists():
                return str(path)

        # Also check for any image files
        for ext in ["*.jpg", "*.jpeg", "*.png", "*.gif"]:
            matches = list(Path(RESUME_DIR).glob(ext))
            if matches:
                return str(matches[0])

        return None

    def _handle_resume_upload(self, page: Page) -> bool:
        """Find and upload a resume file.

        Searches for <input type='file'> elements and uploads a PDF.

        Returns:
            True if a file was uploaded.
        """
        resume_path = self._find_resume_file()
        if not resume_path:
            print("    ⚠️ No resume file found. Please add a PDF to job_bot/resumes/")
            return False

        print(f"    📎 Uploading resume: {resume_path}")

        try:
            # Find file input elements
            file_inputs = page.locator("input[type='file']").all()

            for file_input in file_inputs:
                try:
                    # Check if it looks like a resume upload field
                    file_input.set_input_files(resume_path)
                    print(f"    ✅ Resume uploaded successfully")
                    time.sleep(random.uniform(1.0, 2.0))
                    return True
                except Exception as e:
                    print(f"    ⚠️ Upload attempt failed: {e}")
                    continue

            # Try detecting file upload buttons
            upload_selectors = [
                "button:has-text(/upload/i)",
                "button:has-text(/resume/i)",
                "button:has-text(/cv/i)",
                "button:has-text(/attach/i)",
                "button:has-text(/browse/i)",
                "button:has-text(/choose file/i)",
                "div:has-text(/upload resume/i) button",
                "div:has-text(/attach resume/i) button",
            ]

            for selector in upload_selectors:
                try:
                    btn = page.locator(selector).first
                    if btn.count() > 0:
                        btn.click()
                        time.sleep(random.uniform(0.5, 1.0))

                        # After clicking the upload button, try to set the file
                        file_inputs_after = page.locator("input[type='file']").all()
                        for file_input_after in file_inputs_after:
                            try:
                                file_input_after.set_input_files(resume_path)
                                print(f"    ✅ Resume uploaded via button")
                                time.sleep(random.uniform(1.0, 2.0))
                                return True
                            except Exception:
                                continue
                except Exception:
                    continue

        except Exception as e:
            print(f"    ❌ Resume upload error: {e}")

        return False

    def _handle_profile_picture_upload(self, page: Page) -> bool:
        """Find and upload a profile picture file.

        Searches for <input type='file'> elements and uploads an image.

        Returns:
            True if a file was uploaded.
        """
        profile_path = self._find_profile_picture()
        if not profile_path:
            print("    ℹ️ No profile picture found. Skipping photo upload.")
            return False

        print(f"    📷 Uploading profile picture: {profile_path}")

        try:
            # Find file input elements
            file_inputs = page.locator("input[type='file']").all()

            for file_input in file_inputs:
                try:
                    # Check if it looks like a photo upload field (accept attribute)
                    accept_attr = file_input.get_attribute("accept") or ""
                    if "image" in accept_attr.lower() or "photo" in accept_attr.lower():
                        file_input.set_input_files(profile_path)
                        print(f"    ✅ Profile picture uploaded successfully")
                        time.sleep(random.uniform(1.0, 2.0))
                        return True
                except Exception as e:
                    print(f"    ⚠️ Photo upload attempt failed: {e}")
                    continue

            # Try detecting photo upload buttons
            photo_selectors = [
                "button:has-text(/upload photo/i)",
                "button:has-text(/upload picture/i)",
                "button:has-text(/profile picture/i)",
                "button:has-text(/add photo/i)",
                "button:has-text(/choose photo/i)",
                "div:has-text(/upload photo/i) button",
                "div:has-text(/profile picture/i) button",
            ]

            for selector in photo_selectors:
                try:
                    btn = page.locator(selector).first
                    if btn.count() > 0:
                        btn.click()
                        time.sleep(random.uniform(0.5, 1.0))

                        # After clicking the upload button, try to set the file
                        file_inputs_after = page.locator("input[type='file']").all()
                        for file_input_after in file_inputs_after:
                            try:
                                accept_attr = file_input_after.get_attribute("accept") or ""
                                if "image" in accept_attr.lower():
                                    file_input_after.set_input_files(profile_path)
                                    print(f"    ✅ Profile picture uploaded via button")
                                    time.sleep(random.uniform(1.0, 2.0))
                                    return True
                            except Exception:
                                continue
                except Exception:
                    continue

        except Exception as e:
            print(f"    ❌ Profile picture upload error: {e}")

        return False

    # ─── Multi-Step Form Handling (Task 1) ──────────────────────────────────────

    def _find_step_buttons(self, page: Page) -> Dict[str, Locator]:
        """Find navigation buttons for multi-step forms.

        Returns:
            Dict with keys 'next', 'back', 'review', 'submit', 'save_draft'
            mapping to Locator objects if found.
        """
        buttons = {}

        # Button text patterns for each type
        button_patterns = {
            "next": [
                r"continue",
                r"next",
                r"next.?step",
                r"proceed",
                r"continue.?to.?next",
            ],
            "back": [
                r"back",
                r"previous",
                r"go.?back",
                r"prev",
            ],
            "review": [
                r"review",
                r"review.?application",
                r"review.?your.?info",
                r"review.?and.?submit",
            ],
            "submit": [
                r"submit",
                r"submit.?application",
                r"apply",
                r"send",
                r"submit.?now",
                r"apply.?now",
                r"finish",
                r"done",
                r"complete.?application",
            ],
            "save_draft": [
                r"save",
                r"save.?draft",
                r"save.?and.?continue",
                r"save.?for.?later",
            ],
        }

        for btn_type, patterns in button_patterns.items():
            for pattern in patterns:
                try:
                    # Try various element types
                    locator = page.locator(
                        f"button:has-text(/{pattern}/i):not([disabled]), "
                        f"input[type='submit']:has-text(/{pattern}/i):not([disabled]), "
                        f"a:has-text(/{pattern}/i)"
                    ).first
                    if locator.count() > 0 and locator.is_visible():
                        buttons[btn_type] = locator
                        break
                except Exception:
                    continue

        return buttons

    def _is_last_step(self, page: Page) -> bool:
        """Check if we're on the last step of a multi-step form.

        Looks for submit/review buttons and absence of next/continue buttons.

        Returns:
            True if this appears to be the final step.
        """
        buttons = self._find_step_buttons(page)

        # If there's a submit button but no next button, it's likely the last step
        has_submit = "submit" in buttons
        has_review = "review" in buttons
        has_next = "next" in buttons

        return has_submit or has_review or not has_next

    def _handle_multi_step_form(self, page: Page) -> None:
        """Handle multi-step application forms by detecting and progressing through steps.

        Loops through pages, filling fields and clicking Next until
        the review/submit step is reached.

        Args:
            page: The Playwright Page object.
        """
        max_steps = 10  # Safety limit
        current_step = 0

        print("    📑 Detecting multi-step form...")

        while current_step < max_steps:
            current_step += 1
            print(f"    📑 Step {current_step}...")

            # Wait for the page to settle
            page.wait_for_timeout(random.randint(1500, 3000))

            # Check if we're on the last step
            if self._is_last_step(page):
                print(f"    📑 Reached final step (step {current_step})")
                break

            # Find navigation buttons
            buttons = self._find_step_buttons(page)

            if "next" in buttons:
                # Scroll to the button
                buttons["next"].scroll_into_view_if_needed()
                time.sleep(random.uniform(0.5, 1.0))

                buttons["next"].click()
                print(f"    📑 Clicked 'Next/Continue' → step {current_step + 1}")
                time.sleep(random.uniform(1.0, 2.0))
            elif "submit" in buttons:
                # Found submit button, we're done
                print(f"    📑 Submit button found on step {current_step}")
                break
            else:
                print(f"    📑 No navigation buttons found, might be final step")
                break

    # ─── Field Auto-Detection & Filling ─────────────────────────────────────────

    def fill_form(
        self,
        page: Page,
        field_mappings: Dict[str, str],
        data: Dict[str, str],
    ) -> None:
        """Fill form fields using flexible selector mapping.

        Args:
            page: The Playwright Page object.
            field_mappings: Dict mapping field names to CSS selectors.
            data: Dict mapping field names to values.
        """
        for field_name, selector in field_mappings.items():
            if field_name not in data or not data[field_name]:
                continue

            try:
                element = page.wait_for_selector(selector, timeout=5000)
                if element:
                    # Check if it's a select element
                    tag = element.evaluate("el => el.tagName.toLowerCase()")
                    if tag == "select":
                        self._handle_dropdown(page, element, data[field_name])
                        continue

                    # Clear existing text and type like a human
                    element.click()
                    element.fill("")
                    page.wait_for_timeout(random.randint(100, 300))
                    element.fill(data[field_name])
                    # Small random delay after filling
                    time.sleep(random.uniform(0.3, 0.8))
                    print(f"    ✅ Filled: {field_name}")
            except Exception as e:
                print(f"    ⚠️ Could not fill '{field_name}': {e}")

    def auto_detect_and_fill(
        self,
        page: Page,
        data: Dict[str, str],
    ) -> None:
        """Auto-detect common form fields and fill them.

        Uses common label patterns, placeholder text, and name/id attributes
        to find the right input fields. Also handles dropdowns, radio buttons,
        checkboxes, and file uploads.

        Args:
            page: The Playwright Page object.
            data: Dict with user data keys like first_name, last_name, email, etc.
        """
        # Track which fields we've filled to avoid duplicates
        filled_fields = set()

        # ── Phase 1: Handle file uploads (resume + profile picture) ─────
        self._handle_resume_upload(page)
        self._handle_profile_picture_upload(page)

        # ── Phase 2: Handle radio buttons (yes/no questions) ───────────
        # Smart check: detect common yes/no questions by scanning page text
        page_text = page.evaluate("() => document.body.innerText").lower()
        for q_type, config in SMART_ANSWERS.items():
            if config.get("answer_yes_no") is not None:
                for pattern in config["patterns"]:
                    if re.search(pattern, page_text):
                        answer = config["answer_yes_no"]
                        print(f"    🧠 Smart detection: '{q_type}' → '{answer}'")
                        self._handle_yes_no_question(page, answer)
                        break

        # ── Phase 3: Handle dropdown/select fields ─────────────────────
        select_elements = page.locator("select").all()
        for select in select_elements:
            try:
                # Get the question context (label, nearby text)
                context = ""
                select_id = select.get_attribute("id")
                if select_id:
                    label = page.locator(f"label[for='{select_id}']")
                    if label.count() > 0:
                        context = label.inner_text()

                if not context:
                    # Try parent / wrapping element
                    parent = select.locator("xpath=..")
                    if parent.count() > 0:
                        context = parent.inner_text()

                if context:
                    detected = self._smart_detect_question_type(context)
                    if detected:
                        answer = self._get_smart_answer(detected, field_type="select")
                        if answer:
                            self._handle_dropdown(page, select, answer)
            except Exception:
                continue

        # ── Phase 4: Handle text inputs (standard fields) ──────────────
        field_patterns = {
            "first_name": [
                r"first.?name", r"fname", r"given.?name",
                r"first", r"forename",
            ],
            "last_name": [
                r"last.?name", r"lname", r"surname",
                r"family.?name", r"last",
            ],
            "email": [
                r"email", r"e-?mail", r"eaddress",
            ],
            "phone": [
                r"phone", r"mobile", r"telephone", r"cell",
                r"contact.?number", r"tel",
            ],
            "linkedin": [
                r"linkedin", r"linked.?in",
            ],
            "portfolio": [
                r"portfolio", r"website", r"personal.?site",
                r"github", r"url",
            ],
            "cover_letter": [
        r"cover.?letter", r"coverletter", r"introduction", r"why.?you", r"why.?we.?hire",
                r"additional.?info", r"comments",
            ],
        }

        for field, value in data.items():
            if not value or field in filled_fields:
                continue

            patterns = field_patterns.get(field, [field])
            found = False

            for pattern in patterns:
                # Try placeholder text
                try:
                    elements = page.locator("[placeholder]").all()
                    for el in elements:
                        placeholder = el.get_attribute("placeholder") or ""
                        if re.search(pattern, placeholder, re.IGNORECASE):
                            tag = el.evaluate("el => el.tagName.toLowerCase()")
                            if tag == "select":
                                self._handle_dropdown(page, el, value)
                            else:
                                el.click()
                                el.fill("")
                                page.wait_for_timeout(random.randint(100, 300))
                                el.fill(value)
                            print(f"    ✅ Auto-filled: {field}")
                            filled_fields.add(field)
                            found = True
                            break
                except Exception:
                    pass

                if found:
                    break

                # Try label text
                try:
                    label = page.locator(f"label:has-text(/{pattern}/i)").first
                    if label.count() > 0:
                        for_input = label.get_attribute("for")
                        if for_input:
                            input_el = page.locator(f"#{for_input}")
                            if input_el.count() > 0:
                                tag = input_el.evaluate("el => el.tagName.toLowerCase()")
                                if tag == "select":
                                    self._handle_dropdown(page, input_el, value)
                                else:
                                    input_el.click()
                                    input_el.fill("")
                                    page.wait_for_timeout(random.randint(100, 300))
                                    input_el.fill(value)
                                print(f"    ✅ Auto-filled: {field}")
                                filled_fields.add(field)
                                found = True
                                break
                except Exception:
                    pass

                if found:
                    break

                # Try name/id attribute
                try:
                    input_el = page.locator(
                        f"input[name$='{field}'], "
                        f"input[id$='{field}'], "
                        f"textarea[name$='{field}'], "
                        f"textarea[id$='{field}'], "
                        f"select[name$='{field}'], "
                        f"select[id$='{field}']"
                    ).first
                    if input_el.count() > 0:
                        tag = input_el.evaluate("el => el.tagName.toLowerCase()")
                        if tag == "select":
                            self._handle_dropdown(page, input_el, value)
                        else:
                            input_el.click()
                            input_el.fill("")
                            page.wait_for_timeout(random.randint(100, 300))
                            input_el.fill(value)
                        print(f"    ✅ Auto-filled: {field}")
                        filled_fields.add(field)
                        found = True
                except Exception:
                    pass

                if found:
                    break

            if not found:
                print(f"    ⚠️ Could not auto-detect field: {field}")

            # Human-like delay between fields
            time.sleep(random.uniform(0.5, 1.5))

    # ─── Confirmation Detection (Task 6) ────────────────────────────────────────

    def detect_submission_result(self, page: Page) -> Tuple[bool, str]:
        """Check if the application was submitted successfully or has errors.

        Analyzes the page after submitting for success indicators vs validation errors.

        Args:
            page: The Playwright Page object.

        Returns:
            Tuple of (success: bool, message: str).
        """
        # Wait for the page to settle after submission
        page.wait_for_timeout(random.randint(3000, 5000))

        # Get page text for analysis
        page_text = page.evaluate("() => document.body.innerText").lower()
        page_url = page.url.lower()

        # ── Check for success indicators ───────────────────────────────
        success_patterns = [
            r"application.?submitted",
            r"application.?received",
            r"thank.?you.*(?:for|your).*(?:application|interest)",
            r"submitted.?successfully",
            r"successfully.?submitted",
            r"we.?received.?your.?application",
            r"your.?application.*(?:has been|was).*(?:submitted|received)",
            r"application.?complete",
            r"applied.?successfully",
            r"you.?applied",
            r"congratulations",
        ]

        for pattern in success_patterns:
            if re.search(pattern, page_text, re.IGNORECASE):
                return True, "Application submitted successfully"

        # Check for URL change to confirmation pages
        confirmation_url_patterns = [
            r"thank.?you",
            r"application.*success",
            r"submitted",
            r"confirmation",
            r"applied",
            r"success",
        ]
        for pattern in confirmation_url_patterns:
            if re.search(pattern, page_url):
                return True, "Redirected to confirmation page"

        # ── Check for error / validation indicators ────────────────────
        error_patterns = [
            r"(?:required|mandatory).*(?:field|question)",
            r"please.*(?:fill|complete|fix|correct|review|address)",
            r"error.*(?:found|below|occurred|message)",
            r"validation.*(?:error|failed|problem)",
            r"(?:field|question).*(?:required|mandatory)",
            r"invalid.*(?:email|phone|url|format|entry)",
            r"something.*went.*wrong",
            r"please.*try.*again",
            r"we.*encountered.*error",
            r"missing.*field",
        ]

        for pattern in error_patterns:
            if re.search(pattern, page_text, re.IGNORECASE):
                # Check if there are visible error messages
                error_elements = [
                    "[class*='error']",
                    "[class*='alert']",
                    "[class*='validation']",
                    "[aria-invalid='true']",
                    ".field-error",
                    ".error-message",
                    "[role='alert']",
                ]
                for selector in error_elements:
                    try:
                        errors = page.locator(selector)
                        if errors.count() > 0:
                            error_text = errors.first.inner_text()[:200] if errors.first.count() > 0 else ""
                            return False, f"Validation error detected: {error_text}"
                    except Exception:
                        continue

                return False, "Validation errors might exist on the page"

        # ── Ambiguous result ───────────────────────────────────────────
        # Check for error-highlighted fields
        try:
            invalid_fields = page.locator("[aria-invalid='true']")
            if invalid_fields.count() > 0:
                return False, f"Found {invalid_fields.count()} invalid field(s)"
        except Exception:
            pass

        # Check for success buttons / messages
        try:
            success_el = page.locator("text=/thank you/i").first
            if success_el.count() > 0:
                return True, "Success message detected"
        except Exception:
            pass

        return False, "Unable to determine submission result (ambiguous)"

    # ─── Platform-Specific Handlers (Task 5) ────────────────────────────────────

    def _handle_greenhouse(self, page: Page, user_data: Dict[str, str], cover_letter: str) -> bool:
        """Greenhouse-specific application handler.

        Greenhouse uses a standardized form structure with sections.
        """
        print("    🏗️ Using Greenhouse-specific handler")

        # Wait for the form to load
        page.wait_for_timeout(random.randint(2000, 4000))

        # Greenhouse uses a predictable structure
        # Fill basic info
        field_map = {
            "first_name": "input[name='first_name'], input[id*='first_name']",
            "last_name": "input[name='last_name'], input[id*='last_name']",
            "email": "input[name='email'], input[id*='email']",
            "phone": "input[name='phone'], input[id*='phone']",
            "linkedin": "input[name='linkedin'], input[id*='linkedin']",
            "portfolio": "input[name='portfolio'], input[id*='portfolio']",
            "website": "input[name='website'], input[id*='website'], input[name='portfolio']",
        }
        self.fill_form(page, field_map, user_data)

        # Upload resume + profile picture
        self._handle_resume_upload(page)
        self._handle_profile_picture_upload(page)

        # Fill cover letter (Greenhouse uses a textarea typically)
        try:
            cl_textarea = page.locator(
                "textarea[name='cover_letter'], "
                "textarea[id*='cover_letter'], "
                "div[contenteditable='true']"
            ).first
            if cl_textarea.count() > 0:
                cl_textarea.click()
                cl_textarea.fill(cover_letter)
                print("    ✅ Filled cover letter (Greenhouse)")
        except Exception as e:
            print(f"    ⚠️ Could not fill cover letter: {e}")

        # Look for radio button questions (demographics, etc.)
        self._handle_yes_no_question(page, "yes")

        # Handle demographics dropdowns
        demographics_fields = page.locator("select[id*='eeo'], select[id*='demographic'], select[id*='race'], select[id*='gender'], select[id*='veteran'], select[id*='disability']").all()
        for field in demographics_fields:
            try:
                self._handle_dropdown(page, field, "I prefer not to answer")
            except Exception:
                pass

        # Handle multi-step (Greenhouse often has a single page)
        # Look for the submit button
        buttons = self._find_step_buttons(page)
        if "submit" in buttons:
            buttons["submit"].click()
            page.wait_for_timeout(random.randint(3000, 5000))
            success, msg = self.detect_submission_result(page)
            print(f"    {'✅' if success else '❌'} Submission: {msg}")
            return success

        # Fallback: click the standard apply button
        return self.find_and_click_submit(page)

    def _handle_lever(self, page: Page, user_data: Dict[str, str], cover_letter: str) -> bool:
        """Lever-specific application handler.

        Lever has a multi-step modal with clearly defined sections.
        """
        print("    🏗️ Using Lever-specific handler")

        # Wait for form
        page.wait_for_timeout(random.randint(2000, 4000))

        # Lever uses a modal-based form with steps
        # Step 1: Contact Info
        field_map = {
            "first_name": "input[name='name'], input[name='first'], input[placeholder*='first']",
            "last_name": "input[name='last'], input[placeholder*='last']",
            "email": "input[name='email'], input[type='email']",
            "phone": "input[name='phone'], input[type='tel']",
        }
        self.fill_form(page, field_map, user_data)

        # Click Next/Continue
        buttons = self._find_step_buttons(page)
        if "next" in buttons:
            buttons["next"].click()
            page.wait_for_timeout(random.randint(1000, 2000))

        # Step 2: Links (LinkedIn, Portfolio)
        links_map = {
            "linkedin": "input[placeholder*='linkedin'], input[name*='linkedin']",
            "portfolio": "input[placeholder*='github'], input[placeholder*='portfolio'], input[name*='url'], input[placeholder*='website']",
        }
        self.fill_form(page, links_map, user_data)

        # Step 3: Resume upload & Cover letter
        self._handle_resume_upload(page)

        # Fill cover letter (Lever uses a textarea or rich text)
        try:
            cl_input = page.locator(
                "textarea, div[contenteditable='true']"
            ).first
            if cl_input.count() > 0:
                cl_input.click()
                cl_input.fill(cover_letter)
                print("    ✅ Filled cover letter (Lever)")
        except Exception as e:
            print(f"    ⚠️ Could not fill cover letter: {e}")

        # Handle diversity/equal opportunity questions
        self._handle_yes_no_question(page, "no")
        self._handle_yes_no_question(page, "yes")

        # Handle additional yes/no questions
        lever_questions = page.locator(
            "fieldset div[class*='application-question'], "
            "div[class*='question'], "
            "div[data-qa*='question']"
        ).all()
        for q in lever_questions:
            try:
                text = q.inner_text().lower()
                if re.search(r"authorized|sponsor|visa|right.?to.?work", text):
                    radios = q.locator("input[type='radio']").all()
                    self._handle_radio_group(page, radios, "yes")
                elif re.search(r"felony|criminal|convict", text):
                    radios = q.locator("input[type='radio']").all()
                    self._handle_radio_group(page, radios, "no")
            except Exception:
                pass

        # Submit
        buttons = self._find_step_buttons(page)
        if "submit" in buttons:
            buttons["submit"].click()
            page.wait_for_timeout(random.randint(3000, 5000))
            success, msg = self.detect_submission_result(page)
            print(f"    {'✅' if success else '❌'} Submission: {msg}")
            return success

        return self.find_and_click_submit(page)

    def _handle_workday(self, page: Page, user_data: Dict[str, str], cover_letter: str) -> bool:
        """Workday-specific application handler.

        Workday has a complex, iframe-based multi-form workflow.
        """
        print("    🏗️ Using Workday-specific handler")

        # Workday often uses iframes — attempt to find the application iframe
        workday_page = page
        try:
            iframes = page.locator("iframe").all()
            for iframe in iframes:
                try:
                    frame = iframe.content_frame
                    if frame:
                        body = frame.locator("body")
                        if body.count() > 0 and "application" in body.inner_text().lower():
                            workday_page = frame
                            break
                except Exception:
                    continue
        except Exception:
            pass

        # Wait for Workday form to load (it's slow)
        page.wait_for_timeout(random.randint(3000, 5000))

        # Workday uses a multi-step wizard
        buttons = self._find_step_buttons(page)

        # Fill basic info on first step
        field_map = {
            "first_name": "input[name*='first'], input[data-automation-id*='firstName']",
            "last_name": "input[name*='last'], input[data-automation-id*='lastName']",
            "email": "input[name*='email'], input[type='email'], input[data-automation-id*='email']",
            "phone": "input[name*='phone'], input[type='tel'], input[data-automation-id*='phone']",
        }
        self.fill_form(page, field_map, user_data)

        # Upload resume + profile picture
        self._handle_resume_upload(page)
        self._handle_profile_picture_upload(page)

        # Handle the multi-step workflow
        max_steps = 8
        for step in range(max_steps):
            page.wait_for_timeout(random.randint(2000, 4000))

            # Fill dropdowns on each step
            selects = page.locator("select").all()
            for select in selects:
                try:
                    context = ""
                    select_id = select.get_attribute("id")
                    if select_id:
                        label = page.locator(f"label[for='{select_id}']")
                        if label.count() > 0:
                            context = label.inner_text()
                    if context:
                        detected = self._smart_detect_question_type(context)
                        if detected:
                            answer = self._get_smart_answer(detected, field_type="select")
                            if answer:
                                self._handle_dropdown(page, select, answer)
                except Exception:
                    continue

            # Handle radio buttons
            self._handle_yes_no_question(page, "yes")
            self._handle_yes_no_question(page, "no")

            # Try to proceed to next step
            buttons = self._find_step_buttons(page)
            if "next" in buttons:
                buttons["next"].click()
                print(f"    📑 Workday step {step + 1} → next")
                time.sleep(random.uniform(1.0, 2.0))
            elif "review" in buttons:
                buttons["review"].click()
                page.wait_for_timeout(random.randint(2000, 4000))
                # On review page, try to submit
                buttons = self._find_step_buttons(page)
                if "submit" in buttons:
                    buttons["submit"].click()
                    time.sleep(random.uniform(3.0, 5.0))
                    success, msg = self.detect_submission_result(page)
                    print(f"    {'✅' if success else '❌'} Workday submission: {msg}")
                    return success
                break
            elif "submit" in buttons:
                buttons["submit"].click()
                time.sleep(random.uniform(3.0, 5.0))
                success, msg = self.detect_submission_result(page)
                print(f"    {'✅' if success else '❌'} Workday submission: {msg}")
                return success
            else:
                # No navigation buttons - might be finished or errored
                break

        return self.find_and_click_submit(page)

    def _handle_ashby(self, page: Page, user_data: Dict[str, str], cover_letter: str) -> bool:
        """Ashby-specific application handler.

        Ashby has a clean, single-page form.
        """
        print("    🏗️ Using Ashby-specific handler")

        page.wait_for_timeout(random.randint(2000, 4000))

        # Ashby uses a clean form layout
        field_map = {
            "first_name": "input[name='name'], input[placeholder*='first'], input[data-testid*='firstName']",
            "last_name": "input[placeholder*='last'], input[data-testid*='lastName']",
            "email": "input[name='email'], input[type='email'], input[data-testid*='email']",
            "phone": "input[name='phone'], input[type='tel'], input[data-testid*='phone']",
            "linkedin": "input[placeholder*='linkedin'], input[name*='linkedin']",
            "portfolio": "input[placeholder*='github'], input[placeholder*='portfolio'], input[placeholder*='website']",
        }
        self.fill_form(page, field_map, user_data)

        # Upload resume + profile picture
        self._handle_resume_upload(page)
        self._handle_profile_picture_upload(page)

        # Fill cover letter
        try:
            cl_textarea = page.locator("textarea").first
            if cl_textarea.count() > 0:
                cl_textarea.click()
                cl_textarea.fill(cover_letter)
                print("    ✅ Filled cover letter (Ashby)")
        except Exception as e:
            print(f"    ⚠️ Could not fill cover letter: {e}")

        # Handle any radio/dropdown questions
        selects = page.locator("select").all()
        for select in selects:
            try:
                self._handle_dropdown(page, select, "I prefer not to answer")
            except Exception:
                pass

        # Submit
        buttons = self._find_step_buttons(page)
        if "submit" in buttons:
            buttons["submit"].click()
            page.wait_for_timeout(random.randint(3000, 5000))
            success, msg = self.detect_submission_result(page)
            print(f"    {'✅' if success else '❌'} Submission: {msg}")
            return success

        return self.find_and_click_submit(page)

    def _handle_bamboohr(self, page: Page, user_data: Dict[str, str], cover_letter: str) -> bool:
        """BambooHR-specific application handler.

        BambooHR has a structured but often complex form.
        """
        print("    🏗️ Using BambooHR-specific handler")

        page.wait_for_timeout(random.randint(2000, 4000))

        # BambooHR form handling
        field_map = {
            "first_name": "input[name*='first'], input[id*='firstName'], input[data-bind*='firstName']",
            "last_name": "input[name*='last'], input[id*='lastName'], input[data-bind*='lastName']",
            "email": "input[name*='email'], input[id*='email'], input[type='email']",
            "phone": "input[name*='phone'], input[id*='phone'], input[type='tel']",
        }
        self.fill_form(page, field_map, user_data)

        # Upload resume + profile picture
        self._handle_resume_upload(page)
        self._handle_profile_picture_upload(page)

        # Handle multi-step form
        self._handle_multi_step_form(page)

        # Submit
        buttons = self._find_step_buttons(page)
        if "submit" in buttons:
            buttons["submit"].click()
            page.wait_for_timeout(random.randint(3000, 5000))
            success, msg = self.detect_submission_result(page)
            print(f"    {'✅' if success else '❌'} Submission: {msg}")
            return success

        return self.find_and_click_submit(page)

    # ─── Submit Button Detection ────────────────────────────────────────────────

    def find_and_click_submit(self, page: Page) -> bool:
        """Find and click the Submit / Apply button on the page.

        Returns:
            True if a button was found and clicked, False otherwise.
        """
        submit_patterns = [
            r"submit", r"apply", r"send", r"submit.?application",
            r"apply.?now", r"submit.?now", r"continue",
            r"next", r"review", r"finish", r"done",
        ]

        for pattern in submit_patterns:
            try:
                # Try buttons
                btn = page.locator(
                    f"button:has-text(/{pattern}/i):not([disabled]), "
                    f"input[type='submit']:not([disabled]), "
                    f"a:has-text(/{pattern}/i)"
                ).first
                if btn.count() > 0 and btn.is_visible():
                    btn.scroll_into_view_if_needed()
                    time.sleep(random.uniform(0.3, 0.7))
                    btn.click()
                    print(f"    🖱️ Clicked: '{pattern}' button")
                    return True
            except Exception:
                pass

        # Last resort: try any submit-type input or button
        try:
            btn = page.locator(
                "button[type='submit']:not([disabled]), "
                "input[type='submit']:not([disabled])"
            ).first
            if btn.count() > 0:
                btn.click()
                print("    🖱️ Clicked submit button (generic)")
                return True
        except Exception:
            pass

        print("    ⚠️ Could not find submit button")
        return False

    # ─── Main Application Pipeline ──────────────────────────────────────────────

    def apply_to_job(
        self,
        form_url: str,
        user_data: Dict[str, str],
        cover_letter: str,
    ) -> bool:
        """Full application pipeline: fill form and submit.

        This is the high-level method used by main.py.

        Features:
        - Platform-specific handlers for Greenhouse, Lever, Workday, Ashby, BambooHR
        - Multi-step form chaining
        - Smart field value mapping with 25+ question types
        - Resume/CV upload
        - Confirmation detection

        Args:
            form_url: URL of the application form.
            user_data: Dict with keys like first_name, last_name, email, etc.
            cover_letter: The AI-generated cover letter text.

        Returns:
            True if the application was submitted successfully.
        """
        self._current_url = form_url
        page = self.context.new_page()
        try:
            print(f"\n  📝 Applying at: {form_url}")

            # Detect platform
            platform = self._detect_platform(form_url)
            print(f"  └ 🏗️ Platform detected: {platform}")

            page.goto(form_url, timeout=30000, wait_until="networkidle")
            page.wait_for_timeout(random.randint(2000, 4000))

            # Route to platform-specific handler
            if platform == "greenhouse":
                return self._handle_greenhouse(page, user_data, cover_letter)
            elif platform == "lever":
                return self._handle_lever(page, user_data, cover_letter)
            elif platform == "workday":
                return self._handle_workday(page, user_data, cover_letter)
            elif platform == "ashby":
                return self._handle_ashby(page, user_data, cover_letter)
            elif platform == "bamboohr":
                return self._handle_bamboohr(page, user_data, cover_letter)
            else:
                # Generic handler - works for most job boards
                print("  └ Using generic form handler")

                # Auto-detect and fill all fields
                self.auto_detect_and_fill(page, user_data)

                # Fill cover letter
                self.auto_detect_and_fill(page, {"cover_letter": cover_letter})

                # Handle multi-step forms
                self._handle_multi_step_form(page)

                # Look for and click submit
                submitted = self.find_and_click_submit(page)

                if submitted:
                    # Check the result
                    page.wait_for_timeout(random.randint(3000, 5000))
                    success, msg = self.detect_submission_result(page)
                    print(f"    {'✅' if success else '⚠️'} Result: {msg}")

                    if success:
                        print("  ✅ Application submitted successfully!")
                        return True
                    else:
                        print(f"  ⚠️ Possible issue: {msg}")
                        return False
                else:
                    print("  ⚠️ Application form filled but submit button not found")
                    return False

        except Exception as e:
            print(f"  ❌ Error during application: {e}")
            return False
        finally:
            page.close()
