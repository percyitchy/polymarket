# 🚀 Polymarket Bot - 24/7 Server Deployment Guide

## 📋 Prerequisites
- Ubuntu server with SSH access
- Your Telegram bot token and chat ID
- All bot files ready locally

## 🔧 Step-by-Step Deployment

### 1. Upload Files to Server
```bash
# Make upload script executable and run it
chmod +x upload.sh
./upload.sh
```

### 2. Connect to Server
```bash
ssh -l ubuntu YOUR_SERVER_IP
```

### 3. Run Deployment Script
```bash
cd /opt/polymarket-bot
chmod +x deploy.sh
./deploy.sh
```

### 4. Start the Bot Service
```bash
sudo systemctl start polymarket-bot
sudo systemctl status polymarket-bot
```

## ⚙️ Service Management Commands

| Command | Description |
|---------|-------------|
| `sudo systemctl start polymarket-bot` | Start the bot |
| `sudo systemctl stop polymarket-bot` | Stop the bot |
| `sudo systemctl restart polymarket-bot` | Restart the bot |
| `sudo systemctl status polymarket-bot` | Check bot status |
| `sudo journalctl -u polymarket-bot -f` | View live logs |

## 📊 Monitoring & Logs

### View Real-time Logs
```bash
sudo journalctl -u polymarket-bot -f
```

### Check Bot Status
```bash
sudo systemctl status polymarket-bot
```

### View Log Files
```bash
tail -f /opt/polymarket-bot/polymarket_notifier.log
```

## 🔧 Configuration

### Bot Settings (in .env file)
- `ALERT_WINDOW_MIN=15` - 15-minute consensus window
- `MIN_CONSENSUS=3` - Alert when 3+ wallets agree (minimum)
- `POLL_INTERVAL_SEC=7` - Check every 7 seconds
- `TELEGRAM_BOT_TOKEN` - Your Telegram bot token
- `TELEGRAM_CHAT_ID` - Your Telegram chat ID

### Update Configuration
1. Edit `/opt/polymarket-bot/.env`
2. Restart service: `sudo systemctl restart polymarket-bot`

## 🚨 Alert Behavior

The bot will send Telegram notifications when:
- Gains **3 or more** tracked wallets buy the same market outcome
- Within a **15-minute rolling window**
- Wallets have **75%+ win rate** and **10+ trades**
- Only first entry per wallet per market direction

## 🔄 Auto-Restart

The service is configured to:
- ✅ Auto-restart if it crashes
- ✅ Restart after 10 seconds
- ✅ Start automatically on server boot
- ✅ Log all output to systemd journal

## 📝 Log Rotation

Logs are automatically rotated:
- Daily rotation
- Keep 7 days of logs
- Compressed old logs

## 🛠️ Troubleshooting

### Bot Not Starting
```bash
sudo journalctl -u polymarket-bot --no-pager
```

### Check File Permissions
```bash
ls -la /opt/polymarket-bot/
```

### Test Telegram Connection
```bash
cd /opt/polymarket-bot
source venv/bin/activate
python -c "from notify import TelegramNotifier; TelegramNotifier().test_connection()"
```

## 📱 Telegram Setup

Make sure your `.env` file contains:
```
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
```

## ✅ Verification

After deployment, verify:
1. Service is running: `sudo systemctl status polymarket-bot`
2. No errors in logs: `sudo journalctl -u polymarket-bot`
3. Bot scraped wallets successfully
4. Telegram test message received

---

**🎯 Your Polymarket Bot is now running 24/7 and will alert you when 2+ wallets make the same prediction within 15 minutes!**
