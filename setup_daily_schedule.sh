#!/bin/bash
# Setup daily schedule for Polymarket wallet analysis and reporting
# This script installs systemd timers for daily execution

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_DIR="/etc/systemd/system"

echo "Setting up daily schedule for Polymarket wallet analysis..."

# Check if running as root or with sudo
if [ "$EUID" -ne 0 ]; then 
    echo "Please run as root or with sudo"
    exit 1
fi

# Copy service files
echo "Installing systemd service files..."
cp "$SCRIPT_DIR/polymarket-daily-analysis.service" "$SERVICE_DIR/"
cp "$SCRIPT_DIR/polymarket-daily-analysis.timer" "$SERVICE_DIR/"
cp "$SCRIPT_DIR/polymarket-daily-report.service" "$SERVICE_DIR/"
cp "$SCRIPT_DIR/polymarket-daily-report.timer" "$SERVICE_DIR/"

# Reload systemd
echo "Reloading systemd daemon..."
systemctl daemon-reload

# Enable and start timers
echo "Enabling timers..."
systemctl enable polymarket-daily-analysis.timer
systemctl enable polymarket-daily-report.timer

# Start timers
echo "Starting timers..."
systemctl start polymarket-daily-analysis.timer
systemctl start polymarket-daily-report.timer

# Show status
echo ""
echo "Timer status:"
systemctl list-timers polymarket-daily-*.timer --no-pager

echo ""
echo "✅ Daily schedule setup complete!"
echo ""
echo "Timers configured:"
echo "  - polymarket-daily-analysis.timer: Runs daily at 03:00 UTC"
echo "  - polymarket-daily-report.timer: Runs daily at 23:00 UTC"
echo ""
echo "To check timer status: systemctl list-timers polymarket-daily-*.timer"
echo "To check service logs: journalctl -u polymarket-daily-analysis.service"
echo "To check report logs: journalctl -u polymarket-daily-report.service"
