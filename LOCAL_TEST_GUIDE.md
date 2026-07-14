# Local Testing Guide with Proxy Support (Pakistan)

## 🧪 Local Testing Steps

### Step 1: Install Dependencies

```bash
cd "/run/media/comradexbt/MY FILES/BUILDING/AUTO JOBS TOOL/job_bot"

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install playwright-stealth

# Install Playwright browsers
python -m playwright install chromium
```

### Step 2: Configure Environment Variables

```bash
# Copy example env file
cp .env.example .env

# Edit .env file
nano .env
```

**Add your tokens:**
```
TELEGRAM_BOT_TOKEN=your_actual_bot_token
GEMINI_API_KEY=your_actual_gemini_key
WEB3_API_TOKEN=U8sMcZhH43rDxQuEAgTiHRJcAh1QKrED
```

### Step 3: Set Up Proxy for Telegram (Pakistan)

**Since Telegram is blocked in Pakistan, you need a proxy:**

**Option 1: System Proxy (VPN)**
```bash
# If you have VPN running, it should work automatically
# Make sure VPN is active before running the bot
```

**Option 2: HTTP/SOCKS Proxy**
```bash
# Add proxy to .env file
HTTP_PROXY=http://proxy-server:port
HTTPS_PROXY=http://proxy-server:port
```

**Option 3: Telegram Proxy (MTProto)**
```bash
# Use Telegram's built-in proxy
# In Telegram app: Settings → Advanced → Connection Settings
# Add proxy server (MTProto)
```

### Step 4: Run Bot Locally

```bash
cd "/run/media/comradexbt/MY FILES/BUILDING/AUTO JOBS TOOL/job_bot"
source venv/bin/activate
python main.py
```

### Step 5: Test Telegram Bot

1. Open Telegram app
2. Search for your bot (@your_bot_name)
3. Send `/start` command
4. Test other commands: `/status`, `/stats`, `/help`

## 🌐 Proxy Configuration for Pakistan

### Method 1: VPN (Recommended)

**Best VPNs for Pakistan:**
- ExpressVPN
- NordVPN
- Surfshark
- ProtonVPN (Free tier available)

**Setup:**
1. Install VPN client
2. Connect to server (US/Europe recommended)
3. Run bot with VPN active

### Method 2: HTTP Proxy

**If you have HTTP proxy:**
```bash
# Add to .env file
HTTP_PROXY=http://username:password@proxy-server:port
HTTPS_PROXY=http://username:password@proxy-server:port

# Or run with proxy
HTTP_PROXY=http://proxy-server:port python main.py
```

### Method 3: SOCKS Proxy

```bash
# Add to .env file
ALL_PROXY=socks5://proxy-server:port

# Or use with proxychains
sudo apt install proxychains
# Edit /etc/proxychains.conf
proxychains python main.py
```

### Method 4: SSH Tunnel

```bash
# If you have SSH access to a server outside Pakistan
ssh -D 1080 -N user@remote-server.com

# Then use SOCKS proxy
ALL_PROXY=socks5://127.0.0.1:1080 python main.py
```

## 🔧 Code Modifications for Proxy

### Update bot_telegram.py for Proxy Support

```python
# Add proxy configuration to bot initialization
from telegram.ext import Updater
import os

# Get proxy from environment
proxy_url = os.getenv('HTTP_PROXY') or os.getenv('HTTPS_PROXY')

if proxy_url:
    from telegram.request import HTTPXRequest
    request = HTTPXRequest(proxy=proxy_url)
    updater = Updater(token=TELEGRAM_BOT_TOKEN, request=request)
else:
    updater = Updater(token=TELEGRAM_BOT_TOKEN)
```

## 🖥️ Server Deployment with Proxy

### For Render (Cloud Server)

**Render mein proxy automatically work karega** kyunki Render servers US/Europe mein hain jahan Telegram block nahi hai.

**No proxy needed for Render deployment!**

### For Pakistan-based Server Agar Pakistan mein server hai:

**Method 1: VPN on Server**
```bash
# Install VPN client on server
sudo apt install openvpn
# Configure VPN
sudo systemctl start openvpn@your-config
```

**Method 2: Proxy Service**
```bash
# Use proxy service like Shadowsocks
sudo apt install shadowsocks-libev
# Configure and start
```

**Method 3: SSH Tunnel to External Server**
```bash
# Create SSH tunnel
ssh -D 1080 -N user@external-server.com
# Run bot with proxy
ALL_PROXY=socks5://127.0.0.1:1080 python main.py
```

## 🧪 Testing Checklist

**Local Testing:**
- [ ] Dependencies installed
- [ ] Environment variables configured
- [ ] Proxy/VPN working
- [ ] Bot starts without errors
- [ ] Telegram bot responds to commands
- [ ] Job scanning works
- [ ] Database operations work

**Server Testing:**
- [ ] Server has internet access
- [ ] Proxy configured (if in Pakistan)
- [ ] Environment variables set
- [ ] Bot runs as service
- [ ] Auto-restart configured
- [ ] Logs accessible

## 🚀 Quick Local Test Command

```bash
cd "/run/media/comradexbt/MY FILES/BUILDING/AUTO JOBS TOOL/job_bot"
source venv/bin/activate
HTTP_PROXY=http://your-proxy:port python main.py
```

**Recommendation: Use VPN for local testing, then deploy to Render (no proxy needed).**
