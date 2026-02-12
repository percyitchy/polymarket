#!/bin/bash

# Upload script for Polymarket Bot files to server
# Usage: ./upload.sh

SERVER=""
USER="ubuntu"
REMOTE_DIR="/opt/polymarket-bot"

echo "📤 Uploading Polymarket Bot files to server..."

# Files to upload
FILES=(
    "polymarket_notifier.py"
    "wallet_analyzer.py"
    "db.py"
    "notify.py"
    "api_scraper.py"
    "hashdive_client.py"
    "hashdive_whale_finder.py"
    "maintain_wallets.py"
    "daily_wallet_collection.sh"
    "requirements.txt"
    ".env"
    "deploy.sh"
)

# Upload each file
for file in "${FILES[@]}"; do
    if [ -f "$file" ]; then
        echo "📁 Uploading $file..."
        scp "$file" "$USER@$SERVER:$REMOTE_DIR/"
    else
        echo "⚠️  File $file not found, skipping..."
    fi
done

echo "✅ Upload complete!"
echo ""
echo "🔧 Next steps on server:"
echo "1. SSH to server: ssh -l ubuntu "
echo "2. Run deployment: cd /opt/polymarket-bot && chmod +x deploy.sh && ./deploy.sh"
echo "3. Start service: sudo systemctl start polymarket-bot"
echo "4. Check status: sudo systemctl status polymarket-bot"
