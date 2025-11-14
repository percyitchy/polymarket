#!/bin/bash
# Restart Polymarket services to reload .env configuration (including new proxies)
# Run this script on the Linux server with sudo

set -e

echo "🔄 Restarting Polymarket services to reload configuration..."

# Reload systemd daemon to pick up any service file changes
echo "Reloading systemd daemon..."
sudo systemctl daemon-reload

# Restart main bot service (if exists)
if systemctl list-units --type=service --all | grep -q "polymarket-bot.service"; then
    echo "Restarting polymarket-bot.service..."
    sudo systemctl restart polymarket-bot.service
    echo "✅ polymarket-bot.service restarted"
else
    echo "⚠️  polymarket-bot.service not found (may be running manually)"
fi

# Restart daily analysis timer (to reload .env for next run)
echo "Restarting polymarket-daily-analysis.timer..."
sudo systemctl restart polymarket-daily-analysis.timer
echo "✅ polymarket-daily-analysis.timer restarted"

# Restart daily report timer
if systemctl list-units --type=timer --all | grep -q "polymarket-daily-report.timer"; then
    echo "Restarting polymarket-daily-report.timer..."
    sudo systemctl restart polymarket-daily-report.timer
    echo "✅ polymarket-daily-report.timer restarted"
fi

# Restart daily refresh timer (if exists)
if systemctl list-units --type=timer --all | grep -q "polymarket-daily-refresh.timer"; then
    echo "Restarting polymarket-daily-refresh.timer..."
    sudo systemctl restart polymarket-daily-refresh.timer
    echo "✅ polymarket-daily-refresh.timer restarted"
fi

echo ""
echo "📊 Service Status:"
echo "=================="

# Show main bot status
if systemctl list-units --type=service --all | grep -q "polymarket-bot.service"; then
    echo ""
    echo "Main Bot:"
    sudo systemctl status polymarket-bot.service --no-pager -l | head -n 10
fi

# Show timer status
echo ""
echo "Timers:"
sudo systemctl list-timers polymarket-daily-*.timer --no-pager

echo ""
echo "✅ All services restarted successfully!"
echo ""
echo "💡 Note: Services will use new proxy configuration from .env on next run"
echo "💡 To check logs: journalctl -u polymarket-bot.service -f"
echo "💡 To check daily analysis logs: journalctl -u polymarket-daily-analysis.service -f"

