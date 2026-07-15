# 🚀 24/7 Server Deployment Guide

This guide shows how to deploy the Auto Job Hunter Bot on a Linux server for continuous 24/7 operation with 1-hour scanning intervals.

## Prerequisites

- Linux server (Ubuntu 20.04+, Debian, CentOS, etc.)
- Python 3.10+
- Git
- Systemd (for service management)
- GitHub account with repository

## Step 1: Clone Repository

```bash
# Clone your repository
git clone https://github.com/ComradeXBT/auto-job-hunter.git
cd auto-job-hunter/job_bot
```

## Step 2: Install Dependencies

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install playwright-stealth

# Install Playwright browsers
python3 -m playwright install chromium
```

## Step 3: Configure Environment Variables

```bash
# Copy example env file
cp .env.example .env

# Edit .env with your actual tokens
nano .env
```

Add your tokens:
```
TELEGRAM_BOT_TOKEN=your_actual_bot_token
TELEGRAM_ALLOWED_USER_IDS=your_numeric_telegram_user_id
GEMINI_API_KEY=your_actual_gemini_key
WEB3_API_TOKEN=your_actual_web3_api_token
```

## Step 4: Place Your Files

```bash
# Create resumes directory
mkdir -p resumes

# Place your resume PDF here
# Copy: Comrade_XBT_Resume_v3.pdf to resumes/

# Place your profile picture here  
# Copy: profile_picture.jpg to resumes/
```

## Step 5: Configure Systemd Service

```bash
# Copy the service file
sudo cp job_bot.service /etc/systemd/system/

# Edit the service file with your actual paths
sudo nano /etc/systemd/system/job_bot.service
```

Update these lines in the service file:
```
User=your_actual_linux_username
WorkingDirectory="/actual/path/to/AUTO JOBS TOOL/job_bot"
ExecStart=/usr/bin/python3 "/actual/path/to/AUTO JOBS TOOL/job_bot/main.py"
EnvironmentFile="/actual/path/to/AUTO JOBS TOOL/job_bot/.env"
```

## Step 6: Enable and Start Service

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable service to start on boot
sudo systemctl enable job_bot

# Start the service
sudo systemctl start job_bot

# Check status
sudo systemctl status job_bot
```

## Step 7: Monitor Logs

```bash
# View real-time logs
sudo journalctl -u job_bot -f

# View last 100 lines
sudo journalctl -u job_bot -n 100

# View logs since today
sudo journalctl -u job_bot --since today
```

## Step 8: Service Management Commands

```bash
# Stop the service
sudo systemctl stop job_bot

# Restart the service
sudo systemctl restart job_bot

# Disable auto-start on boot
sudo systemctl disable job_bot

# Check if service is running
sudo systemctl is-active job_bot
```

## Alternative: Cron Job Setup

If you prefer cron over systemd:

```bash
# Open crontab
crontab -e

# Add this line to run every hour
0 * * * * cd /path/to/AUTO JOBS TOOL/job_bot && /usr/bin/python3 main.py >> /var/log/job_bot.log 2>&1
```

## Troubleshooting

### Service won't start
```bash
# Check detailed error logs
sudo journalctl -u job_bot -xe

# Check if Python path is correct
which python3
```

### Permission issues
```bash
# Make sure the service user owns the files
sudo chown -R your_username:your_username /path/to/AUTO JOBS TOOL
```

### Playwright browser issues
```bash
# Reinstall Playwright browsers
python3 -m playwright install chromium --with-deps
```

## Monitoring

The bot will send Telegram notifications for:
- Job applications submitted
- Scan cycle completions
- Errors and issues

Use Telegram commands:
- `/status` - Check if bot is running
- `/stats` - View application statistics
- `/recent` - Show recent applications

## Security Notes

- Never commit `.env` file to git
- Keep API tokens secure
- Set `TELEGRAM_ALLOWED_USER_IDS` so only trusted users can control the bot
- Use firewall rules to restrict access
- Regularly update dependencies
- Monitor logs for suspicious activity

## Performance Tuning

For high-performance servers:
- Increase `SCAN_INTERVAL_MIN/MAX` for more frequent scans
- Adjust `CYCLE_DELAY_MIN/MAX` for faster form filling
- Use multiple instances for parallel processing

## Backup Strategy

```bash
# Backup database
cp jobs.db jobs.db.backup

# Backup resume data
cp my_resume.json my_resume.json.backup

# Backup to cloud storage
rsync -avz /path/to/AUTO JOBS TOOL/ user@backup-server:/backup/path/
```

## Updates

To update the bot:
```bash
# Pull latest changes
git pull origin main

# Restart service
sudo systemctl restart job_bot
```
