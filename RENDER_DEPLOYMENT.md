# Render Deployment Guide - Auto Job Hunter Bot

## 🚀 Render pa Deploy Karne Ka Tareeqa

### Step 1: Render Account Banayein

1. https://render.com par jayein
2. "Sign Up" par click karein
3. GitHub account se login karein
4. Free tier select karein

### Step 2: GitHub Repository Connect Karein

1. Render dashboard par "New +" button par click karein
2. "Web Service" select karein
3. GitHub repository connect karein:
   - Repository: `comradexbt/auto-job-hunter`
   - Branch: `main`
   - "Connect" par click karein

### Step 3: Build Settings Configure Karein

**Build & Deploy Settings:**

```
Build Command: pip install -r job_bot/requirements.txt && pip install playwright-stealth && python -m playwright install chromium
Start Command: cd job_bot && python main.py
```

**Runtime:**
- Runtime: `Python 3`
- Region: `Oregon (us-west)` ya closest region

### Step 4: Environment Variables Add Karein

**Environment Variables Section mein ye sab add karein:**

```
WEB3_API_TOKEN = U8sMcZhH43rDxQuEAgTiHRJcAh1QKrED
TELEGRAM_BOT_TOKEN = your_telegram_bot_token_here
GEMINI_API_KEY = your_gemini_api_key_here
```

**Important:**
- TELEGRAM_BOT_TOKEN apna BotFather se lein
- GEMINI_API_KEY Google AI Studio se lein
- WEB3_API_TOKEN already hai

### Step 5: Instance Type Select Karein

**Free Tier:**
- Type: `Free`
- RAM: 512MB
- CPU: 0.1 vCPU
- **Note:** Free tier mein 15 minutes baad sleep ho jata hai

**Paid Tier (Recommended for 24/7):**
- Type: `Starter` ($7/month)
- RAM: 0.5GB
- CPU: 0.5 vCPU
- 24/7 running

### Step 6: Deploy Button Par Click Karein

1. "Create Web Service" par click karein
2. Render build shuru karega
3. 2-3 minutes mein deploy ho jayega
4. Logs mein status check karein

### Step 7: Logs Monitor Karein

1. Dashboard par jayein
2. "Logs" tab par click karein
3. Bot ka status dekhein:
   - "Scanning job boards..."
   - "AI matching..."
   - "Application submitted..."

### Step 8: Telegram Bot Test Karein

1. Apna Telegram bot open karein
2. `/start` command bhejein
3. `/status` se check karein bot running hai ya nahi
4. `/stats` se application stats dekhein

## 🔧 Troubleshooting

### Build Fail Ho Jaye:
```
Error: Module not found
Solution: Requirements.txt check karein, saari dependencies honi chahiye
```

### Bot Start Na Ho:
```
Error: Permission denied
Solution: File permissions check karein, executable honi chahiye
```

### Memory Issues:
```
Error: Out of memory
Solution: Paid tier upgrade karein ya code optimize karein
```

## 💡 Alternative: Background Worker Service

Agar web service kaam na kare, toh "Background Worker" use karein:

1. "New +" → "Background Worker"
2. Same settings
3. Background worker better hai long-running tasks ke liye

## 📊 Monitoring

**Render Dashboard Features:**
- Real-time logs
- CPU/RAM usage
- Uptime monitoring
- Error alerts
- Auto-restart on failure

## 🔒 Security

- Environment variables secure hain
- GitHub repository private rakhna
- API tokens kabhi share na karein
- Regular updates check karein

## 💰 Cost

**Free Tier:** $0/month (15 min sleep)
**Starter:** $7/month (24/7 running)
**Standard:** $25/month (more resources)

## 🎯 Success Indicators

- ✅ Build successful
- ✅ Bot running status
- ✅ Telegram bot responding
- ✅ Jobs being applied
- ✅ Logs showing activity

## 📞 Support

Agar koi issue aaye:
- Render documentation: https://render.com/docs
- Community support: https://community.render.com
- GitHub issues: https://github.com/comradexbt/auto-job-hunter/issues
