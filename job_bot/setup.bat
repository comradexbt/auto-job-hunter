@echo off
title Auto Job Hunter - Full Setup
color 0A
echo ============================================================
echo    AUTO JOB HUNTER ^& APPLIER - FULL SETUP
echo ============================================================
echo.
echo This script will:
echo   1. Install all Python dependencies
echo   2. Install Playwright Chromium browser
echo   3. Run import verification tests
echo   4. Initialize git repository
echo   5. Create GitHub repository and push code
echo.
echo ============================================================
echo.

:: ── Step 1: Check Python ──────────────────────────────────────
echo [1/5] Checking Python installation...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Python not found! Please install Python 3.10+ from https://python.org
    pause
    exit /b 1
)
python --version
echo ✅ Python found!
echo.

:: ── Step 2: Install dependencies ──────────────────────────────
echo [2/5] Installing Python packages...
cd /d "%~dp0job_bot"

echo   └ Installing core dependencies...
python -m pip install -r requirements.txt --quiet
if %errorlevel% equ 0 (
    echo   ✅ Core dependencies installed
) else (
    echo   ⚠️ Some packages failed - check errors above
)

echo   └ Installing playwright-stealth (optional)...
python -m pip install playwright-stealth --quiet
if %errorlevel% equ 0 (
    echo   ✅ playwright-stealth installed
) else (
    echo   ⚡ playwright-stealth skipped (optional)
)

echo   └ Installing Playwright Chromium browser...
python -m playwright install chromium
if %errorlevel% equ 0 (
    echo   ✅ Chromium browser installed
) else (
    echo   ❌ Chromium install failed!
)
echo.

:: ── Step 3: Verify imports ────────────────────────────────────
echo [3/5] Verifying imports...
python -c "import json, sqlite3, re, os, sys; print('   ✅ stdlib OK'); from playwright.sync_api import sync_playwright; print('   ✅ playwright OK'); from telegram import Update; from telegram.ext import Application, CommandHandler; print('   ✅ python-telegram-bot OK'); import google.generativeai as genai; print('   ✅ google-generativeai OK'); print('   ✅ All imports OK!')"
if %errorlevel% equ 0 (
    echo ✅ All imports verified successfully!
) else (
    echo ⚠️ Some imports failed. See errors above.
)
echo.

:: ── Step 4: Test database ─────────────────────────────────────
echo [4/5] Testing database...
python -c "from db_manager import init_db, get_today_stats, get_total_stats; init_db(); print(f'   ✅ DB initialized | Today: {get_today_stats()} | Total: {get_total_stats()}')"
if %errorlevel% equ 0 (
    echo ✅ Database working!
) else (
    echo ⚠️ Database test failed.
)
echo.

:: ── Step 5: Create .env from example ──────────────────────────
if not exist ".env" (
    if exist ".env.example" (
        copy ".env.example" ".env" >nul
        echo 📄 Created .env file - EDIT IT with your API keys!
    )
) else (
    echo ✅ .env file already exists
)

:: ── Create resumes folder ─────────────────────────────────────
if not exist "resumes" mkdir resumes
echo 📁 Created resumes/ folder - place your resume PDF here
echo.

:: ── Step 6: Git setup ─────────────────────────────────────────
echo [5/5] Setting up Git repository...
cd /d "%~dp0"

:: Check if git is available
where git >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo ╔══════════════════════════════════════════════════════════════╗
    echo ║  ⚠️  Git not found! Install Git from:                     ║
    echo ║  https://git-scm.com/download/win                          ║
    echo ║                                                             ║
    echo ║  After installing Git, run these commands manually:        ║
    echo ║                                                             ║
    echo ║  cd /d "%~dp0"                    ║
    echo ║  git init                                                  ║
    echo ║  git add .                                                 ║
    echo ║  git commit -m "Initial commit"                            ║
    echo ║  git remote add origin YOUR_GITHUB_URL                     ║
    echo ║  git push -u origin main                                   ║
    echo ╚══════════════════════════════════════════════════════════════╝
    goto :done
)

:: Initialize git repo
if exist ".git" (
    echo ✅ Git repo already initialized
) else (
    git init
    echo ✅ Git repo initialized
)

:: Create .gitignore if it doesn't exist in root
if not exist ".gitignore" (
    copy "job_bot\.gitignore" ".gitignore" >nul
)

:: Add and commit
git add .
git commit -m "Initial commit: Auto Job Hunter with AI matching, Playwright automation, Telegram bot"

echo.
echo ╔══════════════════════════════════════════════════════════════╗
echo ║  ✅ Code committed locally! Now push to GitHub:             ║
echo ║                                                             ║
echo ║  1. Create a repo on GitHub: https://github.com/new         ║
echo ║                                                             ║
echo ║  2. Run these commands:                                     ║
echo ║     git remote add origin https://github.com/YOU/REPO.git   ║
echo ║     git branch -M main                                      ║
echo ║     git push -u origin main                                 ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.

:done
echo.
echo ============================================================
echo   ✅ SETUP COMPLETE!
echo ============================================================
echo.
echo Next: Edit .env with your API keys, then run: python main.py
echo.
pause
