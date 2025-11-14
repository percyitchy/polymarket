#!/bin/bash

# Polymarket Notifier Bot - Server Deployment Script
# Run this script on your Ubuntu server to set up 24/7 monitoring

set -e

echo "🚀 Deploying Polymarket Notifier Bot to Server..."

# Update system packages
echo "📦 Updating system packages..."
sudo apt update && sudo apt upgrade -y

# Install Python 3.12 and pip
echo "🐍 Installing Python 3.12..."
sudo apt install -y python3 python3-venv python3-dev python3-pip

# Install system dependencies
echo "🔧 Installing system dependencies..."
sudo apt install -y curl wget git build-essential

# Create application directory
echo "📁 Creating application directory..."
sudo mkdir -p /opt/polymarket-bot
sudo chown ubuntu:ubuntu /opt/polymarket-bot
cd /opt/polymarket-bot

# Ensure files are uploaded (run upload.sh from local machine first)
echo "📋 Checking uploaded files..."
REQUIRED_FILES=(
    "polymarket_notifier.py"
    "wallet_analyzer.py"
    "db.py"
    "notify.py"
    "api_scraper.py"
    "hashdive_client.py"
    "requirements.txt"
    ".env"
)

for file in "${REQUIRED_FILES[@]}"; do
    if [ ! -f "$file" ]; then
        echo "⚠️  Warning: $file not found! Please upload it first."
    else
        echo "✅ Found: $file"
    fi
done

# Create Python virtual environment
echo "🔧 Creating Python virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
echo "📦 Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Create systemd service file
echo "⚙️ Creating systemd service..."
sudo tee /etc/systemd/system/polymarket-bot.service > /dev/null <<EOF
[Unit]
Description=Polymarket Notifier Bot
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/opt/polymarket-bot
Environment=PATH=/opt/polymarket-bot/venv/bin
ExecStart=/opt/polymarket-bot/venv/bin/python polymarket_notifier.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
# Environment variables
EnvironmentFile=/opt/polymarket-bot/.env

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd and enable service
echo "🔄 Enabling service..."
sudo systemctl daemon-reload
sudo systemctl enable polymarket-bot.service

# Create log rotation
echo "📝 Setting up log rotation..."
sudo tee /etc/logrotate.d/polymarket-bot > /dev/null <<EOF
/opt/polymarket-bot/*.log {
    daily
    missingok
    rotate 7
    compress
    notifempty
    create 644 ubuntu ubuntu
}
EOF

# Set up daily maintenance cron job
echo "📅 Setting up daily maintenance..."
if [ -f "daily_wallet_collection.sh" ]; then
    chmod +x daily_wallet_collection.sh
    (crontab -l 2>/dev/null | grep -v "daily_wallet_collection"; echo "0 2 * * * cd /opt/polymarket-bot && /bin/bash daily_wallet_collection.sh >> wallet_collection.log 2>&1") | crontab -
    echo "✅ Daily maintenance scheduled for 2:00 AM"
else
    echo "⚠️  daily_wallet_collection.sh not found, skipping cron setup"
fi

# Make scripts executable
chmod +x maintain_wallets.py hashdive_whale_finder.py 2>/dev/null || true

echo "✅ Deployment complete!"
echo ""
echo "📋 Next steps:"
echo "1. Upload your bot files to /opt/polymarket-bot/"
echo "2. Make sure .env file has your Telegram credentials"
echo "3. Start the service: sudo systemctl start polymarket-bot"
echo "4. Check status: sudo systemctl status polymarket-bot"
echo "5. View logs: sudo journalctl -u polymarket-bot -f"
echo ""
echo "🔧 Service management commands:"
echo "  Start:   sudo systemctl start polymarket-bot"
echo "  Stop:    sudo systemctl stop polymarket-bot"
echo "  Restart: sudo systemctl restart polymarket-bot"
echo "  Status:  sudo systemctl status polymarket-bot"
echo "  Logs:    sudo journalctl -u polymarket-bot -f"
