#!/bin/bash

# HashDive Insiders Telegram Monitor - Server Deployment
# Run this on your Ubuntu server

set -e

echo "🚀 Deploying HashDive Telegram Monitor to Server..."

# Upload these files via scp or sftp to your server:
echo "📋 Files to upload to server:"
echo "  - hashdive_telegram_server.py"
echo "  - .env (with TELEGRAM_BOT_TOKEN and HASHDIVE_CHAT_ID)"
echo ""
echo "Run these commands from your LOCAL machine:"
echo ""
echo "# 1. Upload files:"
echo "scp hashdive_telegram_server.py ubuntu@YOUR_SERVER:/opt/polymarket-bot/"
echo "scp .env ubuntu@YOUR_SERVER:/opt/polymarket-bot/"
echo ""
echo "# 2. SSH to server:"
echo "ssh ubuntu@YOUR_SERVER"
echo ""
echo "# 3. On server, install dependencies:"
echo "cd /opt/polymarket-bot"
echo "source venv/bin/activate"
echo "pip install undetected-chromedriver"
echo ""
echo "# 4. First run (with visible browser to login):"
echo "python3 hashdive_telegram_server.py --no-headless"
echo ""
echo "# 5. After login, stop and run in headless:"
echo "# Press Ctrl+C, then:"
echo "python3 hashdive_telegram_server.py"
echo ""
echo "# 6. Or run in background with nohup:"
echo "nohup python3 hashdive_telegram_server.py > hashdive.log 2>&1 &"

cat << 'EOF'

📝 Server setup script (run on server after uploading files):

#!/bin/bash
set -e

# Activate venv
source /opt/polymarket-bot/venv/bin/activate

# Install undetected-chromedriver
pip install undetected-chromedriver

# Make executable
chmod +x hashdive_telegram_server.py

echo "✅ Done!"
echo ""
echo "Now run:"
echo "  python3 hashdive_telegram_server.py --no-headless  # First time to login"
echo "  # Login to HashDive, then Ctrl+C"
echo "  python3 hashdive_telegram_server.py               # Run in headless mode"
echo ""
echo "Or background:"
echo "  nohup python3 hashdive_telegram_server.py > hashdive.log 2>&1 &"

EOF

echo ""
echo "✅ Deployment instructions generated!"
echo ""
echo "📄 Also check: HASH41VE_TELEGRAM_INSTRUCTIONS.md"
echo "📄 And: HASH41VE_TELEGRAM_SERVER_DEPLOY.md"

