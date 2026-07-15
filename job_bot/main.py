"""
Main Execution Loop (Phase 6)
Orchestrates the Browser Engine, AI Processor, Database Manager,
and Telegram Bot into a continuous job-hunting workflow.
"""
import json
import os
import random
import signal
import time
import traceback
from typing import Optional

from db_manager import init_db, is_job_applied, save_job, get_today_stats
import bot_telegram
from browser_engine import BrowserEngine
from ai_processor import load_resume, extract_job_info, match_job, generate_cover_letter
import web3_api

# ─── Configuration ──────────────────────────────────────────────────────────────
CONFIG_DIR = os.path.dirname(__file__)
CYCLE_DELAY_MIN = 10      # minimum seconds between actions
CYCLE_DELAY_MAX = 30      # maximum seconds between actions
SCAN_INTERVAL_MIN = 3600    # minimum seconds between full scan cycles (1 hour for 24/7)
SCAN_INTERVAL_MAX = 3600   # maximum seconds between full scan cycles (1 hour for 24/7)

# Global flag for graceful shutdown
_running = True


def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully."""
    global _running
    print("\n\n🛑 Shutdown signal received. Cleaning up...")
    _running = False


def load_targets() -> list:
    """Load target job board URLs from target_sites.json."""
    path = os.path.join(CONFIG_DIR, "target_sites.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            targets = json.load(f)
    except FileNotFoundError:
        print(f"  └ ⚠️ Target URL file not found: {path}")
        return []
    except json.JSONDecodeError as error:
        raise RuntimeError(f"Target URL file contains invalid JSON: {path}") from error

    if not isinstance(targets, list) or not all(
        isinstance(target, str) for target in targets
    ):
        raise ValueError("target_sites.json must contain a list of URL strings")

    print(f"  └ Loaded {len(targets)} target URLs")
    return targets


def prepare_user_data(resume: dict) -> dict:
    """Extract form-filling data from the resume config.

    Constructs dynamic fields like LinkedIn URL from the username.
    """
    info = resume.get("personal_info", {})
    username = info.get("linkedin_username", "comradexbt")

    return {
        "first_name": info.get("first_name") or (info.get("name", "").split()[0] if " " in info.get("name", "") else info.get("name", "")),
        "last_name": info.get("last_name", ""),
        "email": info.get("email", ""),
        "phone": info.get("phone", ""),
        "linkedin": f"https://linkedin.com/in/{username}",
        "portfolio": info.get("portfolio", ""),
        "github": f"https://github.com/{info.get('github_username', username)}",
        "website": info.get("portfolio", ""),
        "location": info.get("location", ""),
    }


def _process_web3_job(
    engine: BrowserEngine,
    resume: dict,
    user_data: dict,
    job_info: dict,
) -> Optional[bool]:
    """Process one Web3 job, returning None when it is intentionally skipped."""
    job_title = job_info.get("job_title", "Unknown")
    company = job_info.get("company", "Unknown")
    print(f"\n  ── Web3 Job: {job_title} at {company}")

    app_url = job_info.get("application_url", "")
    if not app_url:
        print("  └ ⏭️ No application URL, skipping")
        return None

    if is_job_applied(app_url):
        print(f"  └ ⏭️ Already applied to '{job_title}'")
        return None

    if not match_job(job_info, resume):
        print(f"  └ ⏭️ '{job_title}' doesn't match criteria")
        return None

    print("  └ ✍️ Generating cover letter...")
    cover_letter = generate_cover_letter(job_info, resume)

    print(f"  └ 📝 Applying for '{job_title}'...")
    success = engine.apply_to_job(
        form_url=app_url,
        user_data=user_data,
        cover_letter=cover_letter,
    )

    if not success:
        print("  └ ⚠️ Application may not have been submitted")
        return False

    if not save_job(job_title, company, app_url):
        print(f"  └ ⚠️ Application URL was already recorded: {app_url}")

    bot_telegram.send_alert(
        f"✅ *Web3 Application Submitted!*\n\n"
        f"📌 *Position:* {job_title}\n"
        f"🏢 *Company:* {company}\n"
        f"🌐 *Source:* Web3 Jobs API\n"
        f"📊 *Total Applied:* {get_today_stats()} today"
    )
    print("  └ ✅ Application submitted successfully!")
    return True


def process_web3_jobs(engine: BrowserEngine, resume: dict, user_data: dict) -> int:
    """Fetch and process Web3 jobs while isolating failures to one listing."""
    global _running
    applied_count = 0

    print("\n  🌐 Fetching Web3 jobs from API...")
    jobs = web3_api.fetch_jobs(limit=30, remote_only=True)

    if not jobs:
        print("  └ No new Web3 jobs found.")
        return 0

    print(f"  └ Processing {len(jobs)} Web3 jobs...")

    for job_info in jobs:
        if not _running:
            break

        try:
            result = _process_web3_job(engine, resume, user_data, job_info)
        except Exception as error:
            title = job_info.get("job_title", "Unknown")
            print(f"  └ ❌ Error processing Web3 job '{title}': {error}")
            traceback.print_exc()
            bot_telegram.send_alert(
                f"❌ *Web3 Job Error*\nFailed to process `{title}`:\n`{error}`"
            )
            continue

        if result is None:
            continue
        if result:
            applied_count += 1

        delay = random.uniform(CYCLE_DELAY_MIN, CYCLE_DELAY_MAX)
        print(f"  └ ⏳ Waiting {delay:.1f}s before next action...")
        for _ in range(int(delay)):
            if not _running:
                break
            time.sleep(1)

    return applied_count


def scanning_loop():
    """The main job scanning and application loop."""
    global _running

    print("\n" + "=" * 60)
    print("  🔍 AUTO JOB HUNTER - SCANNING LOOP ACTIVE")
    print("=" * 60)

    resume = load_resume()
    targets = load_targets()
    user_data = prepare_user_data(resume)

    # Check if we have any job sources
    has_web3 = bool(os.getenv("WEB3_API_TOKEN"))
    has_targets = len(targets) > 0

    if not has_targets and not has_web3:
        message = (
            "No job sources configured; add URLs to target_sites.json "
            "or set WEB3_API_TOKEN"
        )
        print(f"❌ {message}")
        bot_telegram.send_alert(
            "⚠️ *Job Bot Alert*\nNo job sources found!\n"
            "Add URLs to `target_sites.json` or set `WEB3_API_TOKEN`"
        )
        raise RuntimeError(message)

    if has_web3:
        print("  └ 🌐 Web3 Jobs API: connected")

    engine = BrowserEngine(headless=False)

    try:
        engine.start()

        # Notify user
        bot_telegram.send_alert(
            "🚀 *Job Bot Started!*\n\n"
            f"Scanning {len(targets)} target URLs for matching jobs.\n"
            "_You'll receive updates as jobs are found and applied to._"
        )

        cycle_count = 0

        while _running:
            bot_error = bot_telegram.get_bot_error()
            if bot_error is not None:
                raise RuntimeError("Telegram bot stopped unexpectedly") from bot_error

            cycle_count += 1
            print(f"\n{'='*60}")
            print(f"  📡 Scan Cycle #{cycle_count}")
            print(f"  🎯 Targets: {len(targets)} | Web3 API: {'ON' if has_web3 else 'OFF'}")
            print(f"{'='*60}")

            # ── Phase A: Check Web3 Jobs API ───────────────────────────
            if has_web3:
                try:
                    process_web3_jobs(engine, resume, user_data)
                except web3_api.Web3APIError as error:
                    print(f"  └ ❌ Web3 source failed: {error}")
                    traceback.print_exc()
                    bot_telegram.send_alert(
                        f"❌ *Web3 API Error*\n`{error}`"
                    )

            # ── Phase B: Scan target URLs ──────────────────────────────
            if has_targets:
                # Shuffle targets to vary the order each cycle
                random.shuffle(targets)

                for url in targets:
                    if not _running:
                        break

                    print(f"\n  ── Checking: {url}")

                    try:
                        # Phase 3: Get page content
                        html_content = engine.get_page_content(url, scroll_passes=3)

                        if not html_content:
                            print("  └ ⚠️ No content retrieved, skipping")
                            continue

                        # Phase 4: Extract job info using AI (site-aware)
                        job_info = extract_job_info(html_content, url=url)

                        if not job_info or not job_info.get("job_title"):
                            print("  └ ⚠️ Could not extract job info, skipping")
                            continue

                        job_title = job_info["job_title"]
                        company = job_info["company"]
                        print(f"  └ 📋 Found: {job_title} at {company}")

                        # Check database for duplicates
                        app_url = job_info.get("application_url", url)
                        if is_job_applied(app_url):
                            print(f"  └ ⏭️ Already applied to '{job_title}'")
                            continue

                        # Phase 4: Match against resume
                        if not match_job(job_info, resume):
                            print(f"  └ ⏭️ '{job_title}' doesn't match criteria")
                            continue

                        # Phase 4: Generate cover letter
                        print("  └ ✍️ Generating cover letter...")
                        cover_letter = generate_cover_letter(job_info, resume)

                        # Phase 5: Apply to the job
                        print(f"  └ 📝 Applying for '{job_title}'...")
                        success = engine.apply_to_job(
                            form_url=app_url or url,
                            user_data=user_data,
                            cover_letter=cover_letter,
                        )

                        if success:
                            # Save to database
                            if not save_job(
                                job_title,
                                company,
                                app_url or url,
                            ):
                                print(
                                    "  └ ⚠️ Application URL was already "
                                    f"recorded: {app_url or url}"
                                )

                            # Send Telegram notification
                            bot_telegram.send_alert(
                                f"✅ *Application Submitted!*\n\n"
                                f"📌 *Position:* {job_title}\n"
                                f"🏢 *Company:* {company}\n"
                                f"📊 *Total Applied:* {get_today_stats()} today"
                            )

                            print("  └ ✅ Application submitted successfully!")
                        else:
                            print("  └ ⚠️ Application may not have been submitted")

                    except Exception as error:
                        print(f"  └ ❌ Error processing {url}: {error}")
                        traceback.print_exc()
                        bot_telegram.send_alert(
                            f"❌ *Job Processing Error*\n"
                            f"Failed to process `{url}`:\n`{error}`"
                        )

                    # Human-like random delay between actions
                    delay = random.uniform(CYCLE_DELAY_MIN, CYCLE_DELAY_MAX)
                    print(f"  └ ⏳ Waiting {delay:.1f}s before next action...")
                    for _ in range(int(delay)):
                        if not _running:
                            break
                        time.sleep(1)

            # After completing a full cycle
            if _running:
                today_stats = get_today_stats()
                print(f"\n{'='*60}")
                print(f"  ✅ Scan Cycle #{cycle_count} Complete")
                print(f"  📊 Applied today: {today_stats}")
                print(f"{'='*60}")

                bot_telegram.send_alert(
                    f"🔄 *Scan Cycle Complete*\n\n"
                    f"Cycle #{cycle_count} finished.\n"
                    f"📊 Applied today: *{today_stats}*\n"
                    f"_Next scan starting soon..._"
                )

                # Longer delay between full cycles
                cycle_delay = random.uniform(SCAN_INTERVAL_MIN, SCAN_INTERVAL_MAX)
                print(f"\n⏳ Waiting {cycle_delay:.0f}s before next scan cycle...")
                for _ in range(int(cycle_delay)):
                    if not _running:
                        break
                    time.sleep(1)

    except KeyboardInterrupt:
        print("\n\n🛑 Interrupted by user.")
    except Exception as error:
        print(f"\n❌ Fatal error: {error}")
        bot_telegram.send_alert(
            f"❌ *Bot Error*\nThe job hunter encountered an error:\n`{error}`"
        )
        raise
    finally:
        engine.close()
        print("👋 Bot shutdown complete.")


def main():
    """Entry point: initialize everything and start the scanning loop."""
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    print("=" * 60)
    print("  🚀 AUTO JOB HUNTER & APPLIER")
    print("  Powered by Playwright + Gemini + Telegram")
    print("=" * 60)

    # Phase 1: Initialize database
    print("\n📦 Initializing database...")
    init_db()
    print("  └ Done.")

    # Phase 2: Start Telegram bot in background
    print("\n🤖 Starting Telegram bot...")
    bot_telegram.start_bot_thread()
    print("  └ Bot running in background thread.")

    # Wait for the Telegram bot to be fully initialized
    print("\n⏳ Waiting for Telegram bot to initialize...")
    if not bot_telegram.BOT_READY.wait(timeout=30):
        raise TimeoutError("Telegram bot did not initialize within 30 seconds")

    bot_error = bot_telegram.get_bot_error()
    if bot_error is not None:
        raise RuntimeError("Telegram bot failed to start") from bot_error

    print("  └ Bot is ready!")

    # Start the main scanning loop
    scanning_loop()


if __name__ == "__main__":
    main()
