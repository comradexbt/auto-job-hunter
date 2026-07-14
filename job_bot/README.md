# 🤖 Auto Job Hunter & Applier

> An autonomous system that scrapes job boards, matches listings against your resume using AI, generates personalized cover letters, and auto-submits applications — all while keeping you notified via Telegram.

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![Playwright](https://img.shields.io/badge/Playwright-1.40%2B-green)
![Gemini](https://img.shields.io/badge/Gemini-2.0--flash-orange)
![Telegram](https://img.shields.io/badge/Telegram-Bot-blue)

---

## ✨ Features

### 🔍 Smart Job Scanning
- Visits multiple job boards in configurable cycles
- Human-like scrolling to bypass bot detection
- Extracts job listings from any website

### 🧠 AI-Powered (Google Gemini)
- **Extraction**: Parses job title, company, skills, salary, remote status from page HTML
- **Matching**: Scores jobs against your resume (0-100), only applies if ≥ 70% match
- **Cover Letters**: Generates personalized, job-specific cover letters (≤200 words)
- Graceful fallback to regex/template extraction if API is unavailable

### 🌐 Advanced Browser Automation (Playwright)
- **Persistent sessions**: Login to job sites once — cookies survive restarts
- **Stealth mode**: Evades Cloudflare, bot detection, and rate limiting
- **Multi-step forms**: Detects and progresses through multi-page applications
- **Smart form filling**: Auto-detects fields by label, placeholder, name, and ID
- **Platform-specific handlers**: Tailored support for Greenhouse, Lever, Workday, Ashby, BambooHR
- **Dropdown/Radio/Checkbox**: Handles select elements, yes/no questions, demographics
- **Resume upload**: Automatically uploads your PDF resume
- **Confirmation detection**: Validates success vs. validation errors post-submit

### 📊 Smart Answer Database
Auto-answers 20+ common application questions:
- Work authorization ✅ No visa sponsorship needed ❌
- Demographics → "Decline to self-identify"
- Criminal history → No
- Salary → Negotiable
- Start date → Two weeks notice
- And more...

### 💾 Duplicate Prevention (SQLite)
- Tracks all applied jobs by URL
- Prevents double-applications
- Daily & total statistics

### 📱 Telegram Command Center
| Command | Description |
|---------|-------------|
| `/start` | Welcome & initialize |
| `/stats` | View daily/total application stats |
| `/status` | Check if bot is running |
| `/recent` | Show last 5 applications |
| `/help` | Show all commands |

---

## 🚀 Quick Start

### 1. Prerequisites
- Python 3.10+
- A [Telegram Bot Token](https://t.me/BotFather)
- A [Google Gemini API Key](https://makersuite.google.com/app/apikey)
- Google Chrome (for Playwright)

### 2. Clone & Setup

```bash
git clone https://github.com/yourusername/auto-job-hunter.git
cd auto-job-hunter/job_bot
```

#### Windows (PowerShell)
```powershell
.\setup.ps1
```

#### macOS / Linux
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install playwright-stealth  # optional but recommended
python3 -m playwright install chromium
```

### 3. Configure

```bash
# Copy and fill in your API keys
cp .env.example .env
```

Edit `.env` with your tokens:
```
TELEGRAM_BOT_TOKEN=your_bot_token_here
GEMINI_API_KEY=your_gemini_key_here
```

### 4. Prepare Your Data

**📄 `my_resume.json`** — Fill in your skills, experience, and education:
```json
{
  "personal_info": {
    "name": "Your Name",
    "email": "you@email.com",
    "linkedin_username": "yourprofile"
  },
  "skills": ["Python", "JavaScript", "React", ...],
  "experience": [
    {"title": "Software Engineer", "company": "ACME Corp", "years": "3"}
  ]
}
```

**🎯 `target_sites.json`** — Replace with real job search URLs:
```json
[
  "https://www.linkedin.com/jobs/search/?keywords=python&remote=true",
  "https://www.indeed.com/q-python-remote-jobs.html"
]
```

**📎 `resumes/` folder** — Place your resume PDF here:
```
job_bot/resumes/
  └── my_resume.pdf
```

### 5. Run

```bash
python main.py
```

Open Telegram and send `/start` to your bot. You'll receive live updates as jobs are found and applied to!

---

## 🏗️ Project Structure

```
job_bot/
├── main.py                  # Main orchestration loop
├── ai_processor.py          # Gemini AI integration (extract, match, cover letters)
├── browser_engine.py        # Playwright automation & form filling
├── bot_telegram.py          # Telegram bot with /start, /stats, /recent, /help
├── db_manager.py            # SQLite database (tracks applied jobs)
├── my_resume.json           # YOUR RESUME DATA — edit this!
├── target_sites.json        # YOUR JOB SEARCH URLs — edit this!
├── requirements.txt         # Python dependencies
├── .env.example             # Environment variables template
├── .gitignore               # Git ignore rules
├── README.md                # ← You are here
├── setup.ps1                # Windows PowerShell setup script
├── resumes/                 # Place your resume PDfs here
└── playwright_data/         # Browser profile (auto-created, gitignored)
```

---

## ⚙️ How It Works

```
                     ┌─────────────────┐
                     │   Telegram Bot   │◄──  You send /start, /stats
                     │  (Background)    │──►  You receive alerts
                     └────────┬────────┘
                              │
┌──────────┐    ┌────────────▼────────────┐    ┌──────────────┐
│ Job      │───►│     main.py            │───►│  SQLite DB   │
│ Boards   │    │  Orchestration Loop     │    │  (duplicate  │
│ URLs     │    │                         │    │   tracking)  │
└──────────┘    └────────────┬────────────┘    └──────────────┘
                             │
                    ┌────────▼────────┐
                    │  AI Processor   │
                    │  ─────────────  │
                    │  A) Extract job │
                    │  B) Match (70%) │
                    │  C) Cover letter│
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │ Browser Engine  │
                    │  ─────────────  │
                    │  • Fill forms   │
                    │  • Upload CV    │
                    │  • Click submit │
                    │  • Confirm ✓/✗  │
                    └─────────────────┘
```

---

## 🛡️ Security Notes

- **API keys** are stored in `.env` (gitignored) — never commit them
- **Browser profiles** in `playwright_data/` are gitignored (contain cookies/sessions)
- **Database** files (`*.db`) are gitignored
- **Resumes** in `resumes/` are gitignored

---

## 🚧 Phase 6 — Future Enhancements

- [ ] Dry-run mode (`--dry-run` flag to test extraction without submitting)
- [ ] Stats dashboard / web UI
- [ ] Docker containerization
- [ ] Proxy rotation for rate limit avoidance
- [ ] Better error recovery & retry logic
- [ ] Email notifications (SMTP)
- [ ] Multi-resume support

---

## 📝 License

MIT — Use freely, modify as needed.
