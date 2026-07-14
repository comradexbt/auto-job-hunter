"""
Telegram Control Center (Phase 2 + Resume Editor)
Handles Telegram commands, sends notifications, and lets users
edit their resume directly through the bot via /resume command.
"""
import asyncio
import json
import os
import threading
from typing import Optional, Dict, Any

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ConversationHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

from db_manager import get_today_stats, get_total_stats, get_recent_applied

# ─── Configuration ──────────────────────────────────────────────────────────────
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or ""

if not BOT_TOKEN:
    print("⚠️  TELEGRAM_BOT_TOKEN not set! Set it as an environment variable or in a .env file.")

RESUME_PATH = os.path.join(os.path.dirname(__file__), "my_resume.json")
TARGETS_PATH = os.path.join(os.path.dirname(__file__), "target_sites.json")

# Internal state
_CHAT_ID: Optional[int] = None
_CHAT_ID_LOCK = threading.Lock()
_APPLICATION: Optional[Application] = None
_EVENT_LOOP: Optional[asyncio.AbstractEventLoop] = None
BOT_READY = threading.Event()

# Form question handling state
_PENDING_QUESTION: Optional[str] = None
_QUESTION_ANSWER: Optional[str] = None
_QUESTION_READY = threading.Event()

# ─── Conversation States ────────────────────────────────────────────────────────
(
    RESUME_MAIN,
    AWAIT_SKILL_INPUT,
    AWAIT_EXP_TITLE,
    AWAIT_EXP_COMPANY,
    AWAIT_EXP_YEARS,
    AWAIT_EDU_DEGREE,
    AWAIT_EDU_FIELD,
    AWAIT_EDU_SCHOOL,
    AWAIT_NAME,
    AWAIT_EMAIL,
    AWAIT_PHONE,
    AWAIT_LINKEDIN,
    AWAIT_PORTFOLIO,
    AWAIT_GITHUB,
    AWAIT_HEADLINE,
    AWAIT_SUMMARY,
    AWAIT_REMOVE_SKILL,
    AWAIT_REMOVE_EXP,
    AWAIT_REMOVE_EDU,
    AWAIT_PREFERENCES_REMOTE,
    AWAIT_PREFERENCES_MINSCORE,
) = range(21)


# ═══════════════════════════════════════════════════════════════════════════════
# RESUME LOAD / SAVE
# ═══════════════════════════════════════════════════════════════════════════════

def _load_resume() -> dict:
    """Load the resume JSON file."""
    try:
        with open(RESUME_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"❌ Resume load error: {e}")
        return {}


def _save_resume(data: dict) -> bool:
    """Save the resume JSON file."""
    try:
        with open(RESUME_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"❌ Resume save error: {e}")
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# TARGETS LOAD / SAVE
# ═══════════════════════════════════════════════════════════════════════════════

def _load_targets() -> list:
    """Load target URLs from target_sites.json."""
    try:
        with open(TARGETS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _save_targets(targets: list) -> bool:
    """Save target URLs to target_sites.json."""
    try:
        with open(TARGETS_PATH, "w", encoding="utf-8") as f:
            json.dump(targets, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"❌ Targets save error: {e}")
        return False


def _format_targets_summary(targets: list) -> str:
    """Format target URLs as a readable list."""
    if not targets:
        return "🎯 *Target URLs*\n\n_No URLs added yet. Use /targets to add some._"
    lines = [f"🎯 *Target URLs* ({len(targets)})"]
    for i, url in enumerate(targets, 1):
        # Truncate long URLs for display
        display = url[:70] + "..." if len(url) > 70 else url
        lines.append(f"{i}. `{display}`")
    return "\n".join(lines)


def _format_resume_summary(resume: dict) -> str:
    """Format the current resume as a readable summary."""
    info = resume.get("personal_info", {})
    skills = resume.get("skills", [])
    experience = resume.get("experience", [])
    education = resume.get("education", [])
    prefs = resume.get("preferences", {})

    lines = ["📋 *Your Resume*"]

    # Personal Info
    lines.append(f"\n👤 *Personal Info*")
    lines.append(f"   Name: {info.get('name', '—')} {info.get('last_name', '')}")
    lines.append(f"   Email: {info.get('email', '—')}")
    lines.append(f"   Phone: {info.get('phone', '—') or '—'}")
    lines.append(f"   LinkedIn: {info.get('linkedin_username', '—')}")
    lines.append(f"   Portfolio: {info.get('portfolio', '—') or '—'}")
    lines.append(f"   Headline: {info.get('headline', '—') or '—'}")

    # Skills
    if skills:
        lines.append(f"\n🛠 *Skills* ({len(skills)})")
        lines.append(f"   {', '.join(skills)}")
    else:
        lines.append(f"\n🛠 *Skills* (0) — _Add some!_")

    # Experience
    lines.append(f"\n💼 *Experience* ({len(experience)})")
    if experience:
        for i, exp in enumerate(experience, 1):
            lines.append(f"   {i}. {exp.get('title', '—')} @ {exp.get('company', '—')} ({exp.get('years', '?')}yrs)")
    else:
        lines.append(f"   _No experience added yet_")

    # Education
    lines.append(f"\n🎓 *Education* ({len(education)})")
    if education:
        for i, edu in enumerate(education, 1):
            lines.append(f"   {i}. {edu.get('degree', '—')} in {edu.get('field', '—')} — {edu.get('school', '—')}")
    else:
        lines.append(f"   _No education added yet_")

    # Preferences
    lines.append(f"\n⚙️ *Preferences*")
    lines.append(f"   Remote only: {'✅' if prefs.get('remote_only') else '❌'}")
    lines.append(f"   Min match: {prefs.get('min_match_percentage', 70)}%")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# INLINE KEYBOARD BUILDERS
# ═══════════════════════════════════════════════════════════════════════════════

def _resume_main_keyboard() -> InlineKeyboardMarkup:
    """Build the main resume editing keyboard."""
    keyboard = [
        [InlineKeyboardButton("👤 Personal Info", callback_data="resume_personal")],
        [InlineKeyboardButton("🛠 Skills", callback_data="resume_skills")],
        [InlineKeyboardButton("💼 Experience", callback_data="resume_experience")],
        [InlineKeyboardButton("🎓 Education", callback_data="resume_education")],
        [InlineKeyboardButton("⚙️ Preferences", callback_data="resume_preferences")],
        [InlineKeyboardButton("❌ Close Resume", callback_data="resume_close")],
    ]
    return InlineKeyboardMarkup(keyboard)


def _personal_info_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("✏️ Name", callback_data="edit_name")],
        [InlineKeyboardButton("✏️ Email", callback_data="edit_email")],
        [InlineKeyboardButton("✏️ Phone", callback_data="edit_phone")],
        [InlineKeyboardButton("✏️ LinkedIn Username", callback_data="edit_linkedin")],
        [InlineKeyboardButton("✏️ Portfolio URL", callback_data="edit_portfolio")],
        [InlineKeyboardButton("✏️ GitHub Username", callback_data="edit_github")],
        [InlineKeyboardButton("✏️ Headline", callback_data="edit_headline")],
        [InlineKeyboardButton("✏️ Summary", callback_data="edit_summary")],
        [InlineKeyboardButton("🔙 Back", callback_data="resume_back")],
    ]
    return InlineKeyboardMarkup(keyboard)


def _skills_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("➕ Add Skill", callback_data="skill_add")],
        [InlineKeyboardButton("➖ Remove Skill", callback_data="skill_remove")],
        [InlineKeyboardButton("🔙 Back", callback_data="resume_back")],
    ]
    return InlineKeyboardMarkup(keyboard)


def _experience_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("➕ Add Experience", callback_data="exp_add")],
        [InlineKeyboardButton("➖ Remove Experience", callback_data="exp_remove")],
        [InlineKeyboardButton("🔙 Back", callback_data="resume_back")],
    ]
    return InlineKeyboardMarkup(keyboard)


def _education_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("➕ Add Education", callback_data="edu_add")],
        [InlineKeyboardButton("➖ Remove Education", callback_data="edu_remove")],
        [InlineKeyboardButton("🔙 Back", callback_data="resume_back")],
    ]
    return InlineKeyboardMarkup(keyboard)


def _preferences_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("🌐 Toggle Remote Only", callback_data="pref_remote")],
        [InlineKeyboardButton("📊 Change Min Match %", callback_data="pref_min_score")],
        [InlineKeyboardButton("🔙 Back", callback_data="resume_back")],
    ]
    return InlineKeyboardMarkup(keyboard)


# ═══════════════════════════════════════════════════════════════════════════════
# /RESUME COMMAND
# ═══════════════════════════════════════════════════════════════════════════════

async def resume_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle /resume - Show resume summary with edit options."""
    resume = _load_resume()
    summary = _format_resume_summary(resume)
    await update.message.reply_text(
        summary + "\n\n_Choose what to edit:_",
        parse_mode="Markdown",
        reply_markup=_resume_main_keyboard(),
    )
    return RESUME_MAIN


# ═══════════════════════════════════════════════════════════════════════════════
# CALLBACK QUERY HANDLER (Main Menu)
# ═══════════════════════════════════════════════════════════════════════════════

async def resume_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle all inline keyboard button presses for resume editing."""
    query = update.callback_query
    await query.answer()
    data = query.data
    resume = _load_resume()

    # ── Back / Close ────────────────────────────────────────────────────
    if data == "resume_back":
        summary = _format_resume_summary(resume)
        await query.edit_message_text(
            summary + "\n\n_Choose what to edit:_",
            parse_mode="Markdown",
            reply_markup=_resume_main_keyboard(),
        )
        return RESUME_MAIN

    if data == "resume_close":
        await query.edit_message_text(
            "✅ Resume editor closed. Use /resume to open it again.",
        )
        return ConversationHandler.END

    # ── Personal Info Submenu ───────────────────────────────────────────
    if data == "resume_personal":
        info = resume.get("personal_info", {})
        text = (
            f"👤 *Personal Info*\n\n"
            f"Name: `{info.get('name', '—')}`\n"
            f"Email: `{info.get('email', '—')}`\n"
            f"Phone: `{info.get('phone', '—') or '—'}`\n"
            f"LinkedIn: `{info.get('linkedin_username', '—')}`\n"
            f"Portfolio: `{info.get('portfolio', '—') or '—'}`\n"
            f"GitHub: `{info.get('github_username', '—')}`\n"
            f"Headline: `{info.get('headline', '—') or '—'}`\n\n"
            f"Tap a field to edit it:"
        )
        await query.edit_message_text(
            text,
            parse_mode="Markdown",
            reply_markup=_personal_info_keyboard(),
        )
        return RESUME_MAIN

    # ── Skills Submenu ─────────────────────────────────────────────────
    if data == "resume_skills":
        skills = resume.get("skills", [])
        text = f"🛠 *Skills* ({len(skills)})\n\n"
        if skills:
            text += "\n".join(f"  `{i+1}. {s}`" for i, s in enumerate(skills))
        else:
            text += "_No skills added yet._"
        text += "\n\nChoose an action:"
        await query.edit_message_text(
            text, parse_mode="Markdown", reply_markup=_skills_keyboard()
        )
        return RESUME_MAIN

    # ── Experience Submenu ──────────────────────────────────────────────
    if data == "resume_experience":
        exp = resume.get("experience", [])
        text = f"💼 *Experience* ({len(exp)})\n\n"
        if exp:
            for i, e in enumerate(exp, 1):
                text += f"  `{i}. {e.get('title', '—')} @ {e.get('company', '—')} ({e.get('years', '?')}yrs)`\n"
        else:
            text += "_No experience added yet._"
        text += "\n\nChoose an action:"
        await query.edit_message_text(
            text, parse_mode="Markdown", reply_markup=_experience_keyboard()
        )
        return RESUME_MAIN

    # ── Education Submenu ───────────────────────────────────────────────
    if data == "resume_education":
        edu = resume.get("education", [])
        text = f"🎓 *Education* ({len(edu)})\n\n"
        if edu:
            for i, e in enumerate(edu, 1):
                text += f"  `{i}. {e.get('degree', '—')} in {e.get('field', '—')} — {e.get('school', '—')}`\n"
        else:
            text += "_No education added yet._"
        text += "\n\nChoose an action:"
        await query.edit_message_text(
            text, parse_mode="Markdown", reply_markup=_education_keyboard()
        )
        return RESUME_MAIN

    # ── Preferences Submenu ─────────────────────────────────────────────
    if data == "resume_preferences":
        prefs = resume.get("preferences", {})
        text = (
            f"⚙️ *Preferences*\n\n"
            f"🌐 Remote only: `{'✅ Yes' if prefs.get('remote_only') else '❌ No'}`\n"
            f"📊 Min match score: `{prefs.get('min_match_percentage', 70)}%`\n\n"
            f"Choose an action:"
        )
        await query.edit_message_text(
            text, parse_mode="Markdown", reply_markup=_preferences_keyboard()
        )
        return RESUME_MAIN

    # ── Edit Personal Info Fields ───────────────────────────────────────
    field_map = {
        "edit_name": ("name", "Enter your full name:"),
        "edit_email": ("email", "Enter your email address:"),
        "edit_phone": ("phone", "Enter your phone number:"),
        "edit_linkedin": ("linkedin_username", "Enter your LinkedIn username:"),
        "edit_portfolio": ("portfolio", "Enter your portfolio URL:"),
        "edit_github": ("github_username", "Enter your GitHub username:"),
        "edit_headline": ("headline", "Enter your professional headline (e.g. Senior Software Engineer):"),
        "edit_summary": ("professional_summary", "Enter your professional summary (short paragraph):"),
    }

    if data in field_map:
        field_key, prompt = field_map[data]
        context.user_data["editing_field"] = field_key
        await query.edit_message_text(
            f"✏️ *{prompt}*\n\nSend me the new value, or /cancel to abort.",
            parse_mode="Markdown",
        )
        # Determine which state to go to based on field
        if data == "edit_name":
            return AWAIT_NAME
        elif data == "edit_email":
            return AWAIT_EMAIL
        elif data == "edit_phone":
            return AWAIT_PHONE
        elif data == "edit_linkedin":
            return AWAIT_LINKEDIN
        elif data == "edit_portfolio":
            return AWAIT_PORTFOLIO
        elif data == "edit_github":
            return AWAIT_GITHUB
        elif data == "edit_headline":
            return AWAIT_HEADLINE
        elif data == "edit_summary":
            return AWAIT_SUMMARY

    # ── Skill Actions ──────────────────────────────────────────────────
    if data == "skill_add":
        await query.edit_message_text(
            "✏️ *Add Skill*\n\nSend me the skill name (e.g. `Python`), or /cancel to abort.\n\n"
            "You can send multiple skills separated by commas.",
            parse_mode="Markdown",
        )
        return AWAIT_SKILL_INPUT

    if data == "skill_remove":
        skills = resume.get("skills", [])
        if not skills:
            await query.edit_message_text("❌ No skills to remove!", reply_markup=_skills_keyboard())
            return RESUME_MAIN
        text = "✏️ *Remove Skill*\n\nSend me the **number** of the skill to remove:\n\n"
        text += "\n".join(f"  `{i+1}. {s}`" for i, s in enumerate(skills))
        await query.edit_message_text(text, parse_mode="Markdown")
        return AWAIT_REMOVE_SKILL

    # ── Experience Actions ─────────────────────────────────────────────
    if data == "exp_add":
        await query.edit_message_text(
            "✏️ *Add Experience — Step 1/3*\n\nSend me the **job title** (e.g. `Senior Software Engineer`), "
            "or /cancel to abort.",
            parse_mode="Markdown",
        )
        return AWAIT_EXP_TITLE

    if data == "exp_remove":
        exp = resume.get("experience", [])
        if not exp:
            await query.edit_message_text("❌ No experience entries to remove!", reply_markup=_experience_keyboard())
            return RESUME_MAIN
        text = "✏️ *Remove Experience*\n\nSend me the **number** of the entry to remove:\n\n"
        text += "\n".join(
            f"  `{i+1}. {e.get('title', '—')} @ {e.get('company', '—')}`"
            for i, e in enumerate(exp)
        )
        await query.edit_message_text(text, parse_mode="Markdown")
        return AWAIT_REMOVE_EXP

    # ── Education Actions ──────────────────────────────────────────────
    if data == "edu_add":
        await query.edit_message_text(
            "✏️ *Add Education — Step 1/3*\n\nSend me the **degree** (e.g. `Bachelor of Science`), "
            "or /cancel to abort.",
            parse_mode="Markdown",
        )
        return AWAIT_EDU_DEGREE

    if data == "edu_remove":
        edu = resume.get("education", [])
        if not edu:
            await query.edit_message_text("❌ No education entries to remove!", reply_markup=_education_keyboard())
            return RESUME_MAIN
        text = "✏️ *Remove Education*\n\nSend me the **number** of the entry to remove:\n\n"
        text += "\n".join(
            f"  `{i+1}. {e.get('degree', '—')} in {e.get('field', '—')}`"
            for i, e in enumerate(edu)
        )
        await query.edit_message_text(text, parse_mode="Markdown")
        return AWAIT_REMOVE_EDU

    # ── Preference Actions ─────────────────────────────────────────────
    if data == "pref_remote":
        resume["preferences"]["remote_only"] = not resume.get("preferences", {}).get("remote_only", True)
        _save_resume(resume)
        await query.edit_message_text(
            f"✅ Remote only set to `{resume['preferences']['remote_only']}`!\n\n"
            f"_Use /resume to see updated resume._",
            parse_mode="Markdown",
        )
        return RESUME_MAIN

    if data == "pref_min_score":
        await query.edit_message_text(
            "✏️ *Change Minimum Match Score*\n\n"
            "Send me a number between 50 and 100 (e.g. `70`), "
            "or /cancel to abort.\n\n"
            "_Higher = stricter matching. Default: 70._",
            parse_mode="Markdown",
        )
        return AWAIT_PREFERENCES_MINSCORE

    return RESUME_MAIN


# ═══════════════════════════════════════════════════════════════════════════════
# TEXT INPUT HANDLERS (Conversation States)
# ═══════════════════════════════════════════════════════════════════════════════

async def handle_skill_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle skill addition."""
    text = update.message.text.strip()
    resume = _load_resume()
    skills = resume.get("skills", [])

    # Split by commas for multiple skills
    new_skills = [s.strip() for s in text.replace("،", ",").split(",") if s.strip()]
    added = []
    for skill in new_skills:
        if skill not in skills:
            skills.append(skill)
            added.append(skill)

    resume["skills"] = skills
    _save_resume(resume)

    if added:
        await update.message.reply_text(
            f"✅ Added skill(s): `{', '.join(added)}`\n\n"
            f"Total skills now: {len(skills)}",
            parse_mode="Markdown",
            reply_markup=_skills_keyboard(),
        )
    else:
        await update.message.reply_text(
            "⚠️ Those skills are already in your resume!",
            reply_markup=_skills_keyboard(),
        )
    return RESUME_MAIN


async def handle_skill_remove(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle skill removal by index."""
    text = update.message.text.strip()
    resume = _load_resume()
    skills = resume.get("skills", [])

    try:
        idx = int(text) - 1
        if 0 <= idx < len(skills):
            removed = skills.pop(idx)
            resume["skills"] = skills
            _save_resume(resume)
            await update.message.reply_text(
                f"✅ Removed skill: `{removed}`\n\n"
                f"Total skills now: {len(skills)}",
                parse_mode="Markdown",
                reply_markup=_skills_keyboard(),
            )
        else:
            await update.message.reply_text(
                f"❌ Invalid number! Choose 1-{len(skills)}",
                reply_markup=_skills_keyboard(),
            )
    except ValueError:
        await update.message.reply_text(
            "❌ Please send a valid number!",
            reply_markup=_skills_keyboard(),
        )
    return RESUME_MAIN


async def handle_exp_title(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle experience title (step 1/3)."""
    context.user_data["new_exp"] = {"title": update.message.text.strip()}
    await update.message.reply_text(
        "✏️ *Add Experience — Step 2/3*\n\nSend me the **company name** (e.g. `Google`), "
        "or /cancel to abort.",
        parse_mode="Markdown",
    )
    return AWAIT_EXP_COMPANY


async def handle_exp_company(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle experience company (step 2/3)."""
    context.user_data["new_exp"]["company"] = update.message.text.strip()
    await update.message.reply_text(
        "✏️ *Add Experience — Step 3/3*\n\nSend me the **years** (e.g. `3`), "
        "or /cancel to abort.",
        parse_mode="Markdown",
    )
    return AWAIT_EXP_YEARS


async def handle_exp_years(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle experience years (step 3/3) and save."""
    years_text = update.message.text.strip()
    resume = _load_resume()
    exp = context.user_data.get("new_exp", {})
    exp["years"] = years_text
    resume.setdefault("experience", []).append(exp)
    _save_resume(resume)
    context.user_data.pop("new_exp", None)

    await update.message.reply_text(
        f"✅ Added experience: *{exp['title']}* @ {exp['company']} ({exp['years']}yrs)",
        parse_mode="Markdown",
        reply_markup=_experience_keyboard(),
    )
    return RESUME_MAIN


async def handle_exp_remove(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle experience removal by index."""
    text = update.message.text.strip()
    resume = _load_resume()
    exp = resume.get("experience", [])

    try:
        idx = int(text) - 1
        if 0 <= idx < len(exp):
            removed = exp.pop(idx)
            resume["experience"] = exp
            _save_resume(resume)
            await update.message.reply_text(
                f"✅ Removed: *{removed['title']}* @ {removed['company']}",
                parse_mode="Markdown",
                reply_markup=_experience_keyboard(),
            )
        else:
            await update.message.reply_text(
                f"❌ Invalid number! Choose 1-{len(exp)}",
                reply_markup=_experience_keyboard(),
            )
    except ValueError:
        await update.message.reply_text(
            "❌ Please send a valid number!",
            reply_markup=_experience_keyboard(),
        )
    return RESUME_MAIN


async def handle_edu_degree(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle education degree (step 1/3)."""
    context.user_data["new_edu"] = {"degree": update.message.text.strip()}
    await update.message.reply_text(
        "✏️ *Add Education — Step 2/3*\n\nSend me the **field of study** (e.g. `Computer Science`), "
        "or /cancel to abort.",
        parse_mode="Markdown",
    )
    return AWAIT_EDU_FIELD


async def handle_edu_field(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle education field (step 2/3)."""
    context.user_data["new_edu"]["field"] = update.message.text.strip()
    await update.message.reply_text(
        "✏️ *Add Education — Step 3/3*\n\nSend me the **school/university name** (e.g. `MIT`), "
        "or /cancel to abort.",
        parse_mode="Markdown",
    )
    return AWAIT_EDU_SCHOOL


async def handle_edu_school(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle education school (step 3/3) and save."""
    school = update.message.text.strip()
    edu = context.user_data.get("new_edu", {})
    edu["school"] = school
    resume = _load_resume()
    resume.setdefault("education", []).append(edu)
    _save_resume(resume)
    context.user_data.pop("new_edu", None)

    await update.message.reply_text(
        f"✅ Added education: *{edu['degree']}* in {edu['field']} — {edu['school']}",
        parse_mode="Markdown",
        reply_markup=_education_keyboard(),
    )
    return RESUME_MAIN


async def handle_edu_remove(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle education removal by index."""
    text = update.message.text.strip()
    resume = _load_resume()
    edu = resume.get("education", [])

    try:
        idx = int(text) - 1
        if 0 <= idx < len(edu):
            removed = edu.pop(idx)
            resume["education"] = edu
            _save_resume(resume)
            await update.message.reply_text(
                f"✅ Removed: *{removed['degree']}* in {removed['field']}",
                parse_mode="Markdown",
                reply_markup=_education_keyboard(),
            )
        else:
            await update.message.reply_text(
                f"❌ Invalid number! Choose 1-{len(edu)}",
                reply_markup=_education_keyboard(),
            )
    except ValueError:
        await update.message.reply_text(
            "❌ Please send a valid number!",
            reply_markup=_education_keyboard(),
        )
    return RESUME_MAIN


async def handle_field_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle generic personal info field input."""
    field_key = context.user_data.get("editing_field", "")
    value = update.message.text.strip()
    resume = _load_resume()

    if field_key in ("professional_summary",):
        resume[field_key] = value
    else:
        resume.setdefault("personal_info", {})[field_key] = value

    _save_resume(resume)
    context.user_data.pop("editing_field", None)

    field_labels = {
        "name": "Name", "email": "Email", "phone": "Phone",
        "linkedin_username": "LinkedIn", "portfolio": "Portfolio",
        "github_username": "GitHub", "headline": "Headline",
        "professional_summary": "Professional Summary",
    }
    label = field_labels.get(field_key, field_key)

    await update.message.reply_text(
        f"✅ *{label}* updated to:\n`{value}`",
        parse_mode="Markdown",
        reply_markup=_personal_info_keyboard(),
    )
    return RESUME_MAIN


async def handle_pref_min_score(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle minimum match score change."""
    text = update.message.text.strip()
    try:
        score = int(text)
        if 50 <= score <= 100:
            resume = _load_resume()
            resume.setdefault("preferences", {})["min_match_percentage"] = score
            _save_resume(resume)
            await update.message.reply_text(
                f"✅ Minimum match score set to `{score}%`!\n\n"
                f"_Use /resume to see updated resume._",
                parse_mode="Markdown",
                reply_markup=_preferences_keyboard(),
            )
            return RESUME_MAIN
        else:
            await update.message.reply_text(
                "❌ Please send a number between **50 and 100**.",
                parse_mode="Markdown",
            )
            return AWAIT_PREFERENCES_MINSCORE
    except ValueError:
        await update.message.reply_text(
            "❌ Please send a valid number (e.g. `70`).",
            parse_mode="Markdown",
        )
        return AWAIT_PREFERENCES_MINSCORE


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel the current resume editing operation."""
    context.user_data.clear()
    await update.message.reply_text(
        "❌ Operation cancelled. Use /resume to try again.",
        reply_markup=_resume_main_keyboard(),
    )
    return RESUME_MAIN


# ═══════════════════════════════════════════════════════════════════════════════
# /TARGETS COMMAND & CALLBACK
# ═══════════════════════════════════════════════════════════════════════════════

TARGETS_MAIN, AWAIT_TARGET_ADD, AWAIT_TARGET_REMOVE = range(21, 24)


def _targets_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("➕ Add URL", callback_data="target_add")],
        [InlineKeyboardButton("➖ Remove URL", callback_data="target_remove")],
        [InlineKeyboardButton("❌ Close", callback_data="target_close")],
    ]
    return InlineKeyboardMarkup(keyboard)


async def targets_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle /targets - Show and manage target job board URLs."""
    targets = _load_targets()
    summary = _format_targets_summary(targets)
    await update.message.reply_text(
        f"{summary}\n\n"
        f"Add job search URLs so the bot knows where to scan.\n"
        f"Example: `https://www.linkedin.com/jobs/search/?keywords=python`",
        parse_mode="Markdown",
        reply_markup=_targets_keyboard(),
    )
    return TARGETS_MAIN


async def targets_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle inline keyboard presses for targets menu."""
    query = update.callback_query
    await query.answer()
    data = query.data
    targets = _load_targets()

    if data == "target_add":
        await query.edit_message_text(
            "✏️ *Add Target URL*\n\n"
            "Send me a job search URL.\n\n"
            "Examples:\n"
            "• `https://www.linkedin.com/jobs/search/?keywords=python&remote=true`\n"
            "• `https://www.indeed.com/q-python-remote-jobs.html`\n"
            "• `https://remoteok.com/remote-dev-jobs`\n\n"
            "Send /cancel to abort.",
            parse_mode="Markdown",
        )
        return AWAIT_TARGET_ADD

    if data == "target_remove":
        if not targets:
            await query.edit_message_text(
                "❌ No URLs to remove!",
                reply_markup=_targets_keyboard(),
            )
            return TARGETS_MAIN
        text = "✏️ *Remove URL*\n\nSend me the **number** of the URL to remove:\n\n"
        for i, url in enumerate(targets, 1):
            display = url[:60] + "..." if len(url) > 60 else url
            text += f"  `{i}. {display}`\n"
        await query.edit_message_text(text, parse_mode="Markdown")
        return AWAIT_TARGET_REMOVE

    if data == "target_close":
        await query.edit_message_text("✅ Targets closed. Use /targets to manage again.")
        return ConversationHandler.END

    return TARGETS_MAIN


async def handle_target_add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle adding a target URL."""
    url = update.message.text.strip()
    targets = _load_targets()

    if not url.startswith("http://") and not url.startswith("https://"):
        await update.message.reply_text(
            "❌ Invalid URL! Must start with `http://` or `https://`.\n\n"
            "Example: `https://www.linkedin.com/jobs/`",
            parse_mode="Markdown",
        )
        return AWAIT_TARGET_ADD

    if url in targets:
        await update.message.reply_text(
            "⚠️ This URL is already in your targets!",
            reply_markup=_targets_keyboard(),
        )
        return TARGETS_MAIN

    targets.append(url)
    _save_targets(targets)

    await update.message.reply_text(
        f"✅ URL added! Total targets: {len(targets)}\n\n"
        f"`{url[:80]}{'...' if len(url) > 80 else ''}`",
        parse_mode="Markdown",
        reply_markup=_targets_keyboard(),
    )
    return TARGETS_MAIN


async def handle_target_remove(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle removing a target URL by index."""
    text = update.message.text.strip()
    targets = _load_targets()

    try:
        idx = int(text) - 1
        if 0 <= idx < len(targets):
            removed = targets.pop(idx)
            _save_targets(targets)
            display = removed[:60] + "..." if len(removed) > 60 else removed
            await update.message.reply_text(
                f"✅ Removed: `{display}`\n\n"
                f"Total targets now: {len(targets)}",
                parse_mode="Markdown",
                reply_markup=_targets_keyboard(),
            )
        else:
            await update.message.reply_text(
                f"❌ Invalid number! Choose 1-{len(targets)}",
                reply_markup=_targets_keyboard(),
            )
    except ValueError:
        await update.message.reply_text(
            "❌ Please send a valid number!",
            reply_markup=_targets_keyboard(),
        )
    return TARGETS_MAIN


async def targets_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel targets operation."""
    await update.message.reply_text(
        "❌ Cancelled. Use /targets to try again.",
        reply_markup=_targets_keyboard(),
    )
    return TARGETS_MAIN


# ═══════════════════════════════════════════════════════════════════════════════
# EXISTING COMMAND HANDLERS
# ═══════════════════════════════════════════════════════════════════════════════

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start - Initialize the bot and confirm it's running."""
    global _CHAT_ID
    with _CHAT_ID_LOCK:
        _CHAT_ID = update.effective_chat.id

    await update.message.reply_text(
        "🤖 *Auto Job Bot Active*\n\n"
        "I'm monitoring job boards and applying automatically on your behalf.\n\n"
        "*Available Commands:*\n"
        "├ /start – Show this welcome message\n"
        "├ /stats – View today's application statistics\n"
        "├ /status – Check if the bot is currently running\n"
        "├ /recent – Show recent applications\n"
        "├ /resume – Edit your resume (skills, experience, education)\n"
        "├ /targets – Manage job search URLs\n"
        "└ /help – Get help\n\n"
        "_You'll receive notifications here when jobs are found and applied to._",
        parse_mode="Markdown",
    )


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /stats - Show application statistics."""
    today_count = get_today_stats()
    total_count = get_total_stats()

    await update.message.reply_text(
        f"📊 *Job Application Stats*\n\n"
        f"📅 Applied today: *{today_count}*\n"
        f"📦 Total applied: *{total_count}*\n\n"
        f"_Keep going! Every application brings you closer._",
        parse_mode="Markdown",
    )


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /status - Check if the bot is running."""
    await update.message.reply_text(
        "✅ *Bot Status: RUNNING*\n\n"
        "• Scanning job boards: Active\n"
        "• Database: Connected\n"
        "• Telegram notifications: Enabled\n"
        "• Resume editor: Ready\n\n"
        "_All systems operational._",
        parse_mode="Markdown",
    )


async def recent(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /recent - Show recent job applications."""
    recent_jobs = get_recent_applied(5)

    if not recent_jobs:
        await update.message.reply_text(
            "📭 No job applications recorded yet.\n"
            "_Start scanning to see results here._",
            parse_mode="Markdown",
        )
        return

    lines = ["📋 *Recent Applications*\n"]
    for i, job in enumerate(recent_jobs, 1):
        lines.append(
            f"{i}. *{job['job_title']}* @ {job['company']}\n"
            f"   └ {job['date_applied']}"
        )

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help - Show available commands."""
    await update.message.reply_text(
        "🆘 *Help*\n\n"
        "This bot automatically scans job boards, matches jobs against your "
        "resume, and submits applications.\n\n"
        "*Commands:*\n"
        "• /start – Initialize the bot\n"
        "• /stats – View application stats\n"
        "• /status – Check bot status\n"
        "• /recent – Show recent applications\n"
        "• /resume – 👈 *Edit your resume* (add skills, experience, education)\n"
        "• /targets – 🎯 *Manage target URLs* (add/remove job sites)\n"
        "• /answer – Answer a pending form question\n"
        "• /help – Show this message\n\n"
        "*Workflow:*\n"
        "1. Bot scans target job URLs\n"
        "2. AI extracts job details\n"
        "3. Matches against your resume (>70%)\n"
        "4. Generates custom cover letter\n"
        "5. Fills and submits the application\n"
        "6. Saves to database & notifies you\n\n"
        "*Form Questions:*\n"
        "If the bot encounters an unknown form field, it will ask you via Telegram.\n"
        "Use /answer <your response> to provide the answer.",
        parse_mode="Markdown",
    )


# ═══════════════════════════════════════════════════════════════════════════════
# FORM QUESTION HANDLING
# ═══════════════════════════════════════════════════════════════════════════════

async def answer_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /answer - Provide answer to a pending form question."""
    global _QUESTION_ANSWER, _QUESTION_READY
    
    # Get the answer from the command arguments
    if context.args:
        answer_text = " ".join(context.args)
    else:
        # If no args, try to get from the message text (replied to a question)
        if update.message.reply_to_message:
            answer_text = update.message.text
        else:
            await update.message.reply_text(
                "❌ Please provide an answer.\n\n"
                "Usage: /answer <your response>\n\n"
                "Or reply to the question message with /answer.",
                parse_mode="Markdown",
            )
            return
    
    # Store the answer and signal ready
    _QUESTION_ANSWER = answer_text
    _QUESTION_READY.set()
    
    await update.message.reply_text(
        "✅ Answer recorded! The bot will continue filling the form.",
        parse_mode="Markdown",
    )


def ask_form_question(question: str, field_label: str = "") -> Optional[str]:
    """Ask the user a form question via Telegram and wait for answer.
    
    This is a blocking call that waits for the user to respond via /answer.
    
    Args:
        question: The form question to ask the user.
        field_label: Optional field label for context.
    
    Returns:
        The user's answer, or None if timeout/error.
    """
    global _PENDING_QUESTION, _QUESTION_ANSWER, _QUESTION_READY
    
    # Reset state
    _PENDING_QUESTION = question
    _QUESTION_ANSWER = None
    _QUESTION_READY.clear()
    
    # Format the message
    message = (
        f"❓ *Form Question*\n\n"
        f"**{field_label}**\n\n"
        f"{question}\n\n"
        f"Please provide an answer using:\n"
        f"`/answer <your response>`\n\n"
        f"_The bot will wait for your response before continuing._"
    )
    
    # Send alert
    send_alert(message)
    
    # Wait for answer with timeout (2 minutes)
    if _QUESTION_READY.wait(timeout=120):
        answer = _QUESTION_ANSWER
        print(f"  └ ✅ Received user answer: {answer[:50]}...")
        return answer
    else:
        print(f"  └ ⚠️ Timeout waiting for user answer to: {field_label}")
        send_alert("⏰ Timeout waiting for answer. The bot will skip this field.")
        return None


# ─── Alert Functions ────────────────────────────────────────────────────────────

async def _send_alert_async(message: str) -> None:
    """Internal async function to send a Telegram message."""
    global _APPLICATION

    with _CHAT_ID_LOCK:
        chat_id = _CHAT_ID

    if not chat_id:
        print(f"[Telegram Alert] {message}")
        return

    try:
        await _APPLICATION.bot.send_message(
            chat_id=chat_id,
            text=message,
            parse_mode="Markdown",
        )
    except Exception as e:
        print(f"[Telegram Error] Failed to send alert: {e}")
        print(f"[Telegram Alert] {message}")


def send_alert(message: str) -> None:
    """Thread-safe way to send a notification to the user via Telegram.

    This can be called from any thread - it schedules the coroutine
    on the bot's event loop running in the background thread.
    """
    global _APPLICATION, _EVENT_LOOP

    with _CHAT_ID_LOCK:
        chat_id = _CHAT_ID

    if not chat_id or not _APPLICATION or not _EVENT_LOOP:
        print(f"[Telegram Alert] {message}")
        return

    asyncio.run_coroutine_threadsafe(_send_alert_async(message), _EVENT_LOOP)


# ─── Bot Lifecycle ──────────────────────────────────────────────────────────────

async def run_bot() -> None:
    """Run the Telegram bot (non-blocking polling)."""
    global _APPLICATION, _EVENT_LOOP

    if not BOT_TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN is empty. Set it in .env or as an environment variable.")
        print("   The bot will not start, but the scanning loop can still run.")
        BOT_READY.set()
        return

    _EVENT_LOOP = asyncio.get_running_loop()
    _APPLICATION = Application.builder().token(BOT_TOKEN).build()

    # ── Resume Editor Conversation Handler ─────────────────────────────
    resume_conv = ConversationHandler(
        entry_points=[CommandHandler("resume", resume_command)],
        states={
            RESUME_MAIN: [
                CallbackQueryHandler(resume_callback, pattern="^resume_"),
                CallbackQueryHandler(resume_callback, pattern="^edit_"),
                CallbackQueryHandler(resume_callback, pattern="^skill_"),
                CallbackQueryHandler(resume_callback, pattern="^exp_"),
                CallbackQueryHandler(resume_callback, pattern="^edu_"),
                CallbackQueryHandler(resume_callback, pattern="^pref_"),
            ],
            AWAIT_SKILL_INPUT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_skill_input),
            ],
            AWAIT_REMOVE_SKILL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_skill_remove),
            ],
            AWAIT_EXP_TITLE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_exp_title),
            ],
            AWAIT_EXP_COMPANY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_exp_company),
            ],
            AWAIT_EXP_YEARS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_exp_years),
            ],
            AWAIT_REMOVE_EXP: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_exp_remove),
            ],
            AWAIT_EDU_DEGREE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_edu_degree),
            ],
            AWAIT_EDU_FIELD: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_edu_field),
            ],
            AWAIT_EDU_SCHOOL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_edu_school),
            ],
            AWAIT_REMOVE_EDU: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_edu_remove),
            ],
            AWAIT_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_field_input),
            ],
            AWAIT_EMAIL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_field_input),
            ],
            AWAIT_PHONE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_field_input),
            ],
            AWAIT_LINKEDIN: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_field_input),
            ],
            AWAIT_PORTFOLIO: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_field_input),
            ],
            AWAIT_GITHUB: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_field_input),
            ],
            AWAIT_HEADLINE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_field_input),
            ],
            AWAIT_SUMMARY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_field_input),
            ],
            AWAIT_PREFERENCES_MINSCORE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_pref_min_score),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            # start/help remain as top-level handlers, not fallbacks
        ],
        allow_reentry=True,
    )

    # Register command handlers
    _APPLICATION.add_handler(CommandHandler("start", start))
    _APPLICATION.add_handler(CommandHandler("stats", stats))
    _APPLICATION.add_handler(CommandHandler("status", status))
    _APPLICATION.add_handler(CommandHandler("recent", recent))
    _APPLICATION.add_handler(CommandHandler("answer", answer_command))
    _APPLICATION.add_handler(CommandHandler("help", help_command))
    _APPLICATION.add_handler(resume_conv)

    # ── Targets Conversation Handler ──────────────────────────────────
    targets_conv = ConversationHandler(
        entry_points=[CommandHandler("targets", targets_command)],
        states={
            TARGETS_MAIN: [
                CallbackQueryHandler(targets_callback, pattern="^target_"),
            ],
            AWAIT_TARGET_ADD: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_target_add),
            ],
            AWAIT_TARGET_REMOVE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_target_remove),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", targets_cancel),
        ],
        allow_reentry=True,
    )
    _APPLICATION.add_handler(targets_conv)

    print("🤖 Telegram bot starting...")

    await _APPLICATION.initialize()
    await _APPLICATION.start()
    await _APPLICATION.updater.start_polling()

    print("✅ Telegram bot is running and ready for commands!")
    BOT_READY.set()

    try:
        while True:
            await asyncio.sleep(60)
    except asyncio.CancelledError:
        pass
    finally:
        await _APPLICATION.updater.stop()
        await _APPLICATION.stop()
        await _APPLICATION.shutdown()


def start_bot_thread() -> threading.Thread:
    """Start the Telegram bot in a daemon background thread."""
    def _run():
        asyncio.run(run_bot())

    thread = threading.Thread(target=_run, name="TelegramBot", daemon=True)
    thread.start()
    return thread
