<#
.SYNOPSIS
    Auto Job Hunter & Applier — Windows Setup Script
.DESCRIPTION
    Installs Python dependencies, Playwright browsers, and optionally playwright-stealth.
    Run this from PowerShell in the job_bot/ directory.
.EXAMPLE
    .\setup.ps1
#>

Write-Host "╔══════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║   Auto Job Hunter & Applier — Windows Setup     ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# ── Check Python ────────────────────────────────────────────────────────────────
try {
    $pythonVersion = python --version 2>&1
    Write-Host "✅ Python: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ Python not found! Install Python 3.10+ from https://python.org" -ForegroundColor Red
    exit 1
}

# ── Upgrade pip ─────────────────────────────────────────────────────────────────
Write-Host "`n📦 Upgrading pip..." -ForegroundColor Yellow
python -m pip install --upgrade pip --quiet

# ── Install dependencies ────────────────────────────────────────────────────────
Write-Host "`n📦 Installing Python packages from requirements.txt..." -ForegroundColor Yellow
python -m pip install -r requirements.txt --quiet
if ($LASTEXITCODE -eq 0) {
    Write-Host "   ✅ Core dependencies installed" -ForegroundColor Green
} else {
    Write-Host "   ❌ Failed to install dependencies" -ForegroundColor Red
    exit 1
}

# ── Install playwright-stealth (optional) ────────────────────────────────────────
Write-Host "`n📦 Installing playwright-stealth (optional, for better bot evasion)..." -ForegroundColor Yellow
python -m pip install playwright-stealth --quiet
if ($LASTEXITCODE -eq 0) {
    Write-Host "   ✅ playwright-stealth installed" -ForegroundColor Green
} else {
    Write-Host "   ⚠️ playwright-stealth not available (non-critical)" -ForegroundColor Yellow
}

# ── Install Playwright browsers ─────────────────────────────────────────────────
Write-Host "`n🌐 Installing Playwright Chromium browser..." -ForegroundColor Yellow
python -m playwright install chromium
if ($LASTEXITCODE -eq 0) {
    Write-Host "   ✅ Chromium installed" -ForegroundColor Green
} else {
    Write-Host "   ❌ Failed to install Chromium" -ForegroundColor Red
    exit 1
}

# ── Verify imports ──────────────────────────────────────────────────────────────
Write-Host "`n🔍 Verifying imports..." -ForegroundColor Yellow
$importTest = @"
import json, sqlite3, re, os, sys
print('   ✅ stdlib imports OK')
from playwright.sync_api import sync_playwright
print('   ✅ playwright OK')
from telegram import Update
from telegram.ext import Application, CommandHandler
print('   ✅ python-telegram-bot OK')
import google.generativeai as genai
print('   ✅ google-generativeai OK')
print('   ✅ All imports verified successfully!')
"@
python -c $importTest
if ($LASTEXITCODE -eq 0) {
    Write-Host "   ✅ All imports verified!" -ForegroundColor Green
} else {
    Write-Host "   ⚠️ Some imports failed. Check the output above." -ForegroundColor Yellow
}

# ── Test database ───────────────────────────────────────────────────────────────
Write-Host "`n🗄️  Testing database initialization..." -ForegroundColor Yellow
$dbTest = @"
from db_manager import init_db, get_today_stats, get_total_stats
init_db()
print(f'   ✅ Database initialized')
print(f'   📊 Applied today: {get_today_stats()} | Total: {get_total_stats()}')
"@
python -c $dbTest
if ($LASTEXITCODE -eq 0) {
    Write-Host "   ✅ Database OK" -ForegroundColor Green
} else {
    Write-Host "   ⚠️ Database test failed. Check the output above." -ForegroundColor Yellow
}

# ── Create resume directory ─────────────────────────────────────────────────────
if (-not (Test-Path "resumes")) {
    New-Item -ItemType Directory -Path "resumes" -Force | Out-Null
    Write-Host "`n📁 Created 'resumes/' folder — place your resume PDF here" -ForegroundColor Yellow
}

# ── Check .env ──────────────────────────────────────────────────────────────────
if (-not (Test-Path ".env")) {
    if (Test-Path ".env.example") {
        Copy-Item ".env.example" ".env"
        Write-Host "`n📄 Created .env from .env.example — EDIT IT with your API keys!" -ForegroundColor Yellow
    }
} else {
    Write-Host "`n✅ .env file found" -ForegroundColor Green
}

# ── Done ────────────────────────────────────────────────────────────────────────
Write-Host "`n╔══════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║   ✅ Setup Complete!                             ║" -ForegroundColor Cyan
Write-Host "╠══════════════════════════════════════════════════╣" -ForegroundColor Cyan
Write-Host "║   Next steps:                                    ║" -ForegroundColor Cyan
Write-Host "║   1. Edit .env with your API keys                ║" -ForegroundColor Cyan
Write-Host "║   2. Edit my_resume.json with your info          ║" -ForegroundColor Cyan
Write-Host "║   3. Edit target_sites.json with job URLs        ║" -ForegroundColor Cyan
Write-Host "║   4. Place your resume PDF in resumes/ folder    ║" -ForegroundColor Cyan
Write-Host "║   5. Run: python main.py                         ║" -ForegroundColor Cyan
Write-Host "║   6. Send /start to your bot on Telegram         ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════════════╝" -ForegroundColor Cyan
