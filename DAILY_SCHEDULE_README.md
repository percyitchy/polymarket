# Daily Schedule Setup Guide

## Overview

This system provides automated daily wallet collection, analysis, and reporting for the Polymarket Notifier bot.

## Components

### 1. Daily Wallet Analysis (`daily_wallet_analysis.py`)

**Purpose:** Collects wallets from all sources and processes them through the analysis queue.

**What it does:**
- Collects wallets from `polymarketanalytics.com` (up to 2500)
- Collects wallets from Polymarket leaderboards (weekly/monthly, first 20 pages each)
- Adds all collected wallets to the analysis queue
- Starts workers to process the queue
- Sends summary to Telegram reports channel

**Schedule:** Runs daily at 03:00 UTC (configurable in timer file)

### 2. Daily Report (`daily_report.py`)

**Purpose:** Generates comprehensive daily statistics and sends alerts if issues detected.

**What it reports:**
- Total and tracked wallets
- Wallets added/updated today
- Queue statistics (pending, processing, completed, failed)
- Processing speed and estimated clear time
- Failed rate
- Source breakdown

**Alerts:**
- High failed rate (>5% by default)
- Queue stuck (pending > 1000, 0 completed)
- Queue processing slowly (pending > 500, <20 jobs/hour)
- Low processing rate (<10 jobs/day)
- Database growth warnings

**Schedule:** Runs daily at 23:00 UTC (end of day summary)

## Installation

### Option 1: Automated Setup (Recommended)

```bash
sudo ./setup_daily_schedule.sh
```

This script will:
1. Copy service and timer files to `/etc/systemd/system/`
2. Reload systemd daemon
3. Enable and start the timers
4. Show timer status

### Option 2: Manual Setup

1. Copy service files:
```bash
sudo cp polymarket-daily-analysis.service /etc/systemd/system/
sudo cp polymarket-daily-analysis.timer /etc/systemd/system/
sudo cp polymarket-daily-report.service /etc/systemd/system/
sudo cp polymarket-daily-report.timer /etc/systemd/system/
```

2. Reload systemd:
```bash
sudo systemctl daemon-reload
```

3. Enable timers:
```bash
sudo systemctl enable polymarket-daily-analysis.timer
sudo systemctl enable polymarket-daily-report.timer
```

4. Start timers:
```bash
sudo systemctl start polymarket-daily-analysis.timer
sudo systemctl start polymarket-daily-report.timer
```

## Configuration

### Timer Schedule

Edit the timer files to change schedule:

**`polymarket-daily-analysis.timer`:**
```ini
OnCalendar=*-*-* 03:00:00  # Change time here (HH:MM:SS UTC)
```

**`polymarket-daily-report.timer`:**
```ini
OnCalendar=*-*-* 23:00:00  # Change time here (HH:MM:SS UTC)
```

After editing, reload:
```bash
sudo systemctl daemon-reload
sudo systemctl restart polymarket-daily-analysis.timer
sudo systemctl restart polymarket-daily-report.timer
```

### Alert Thresholds

Configure in `.env` file:

```bash
ALERT_FAILED_RATE_THRESHOLD=0.05      # 5% - alert if failed rate exceeds this
ALERT_QUEUE_STUCK_THRESHOLD=1000      # Alert if pending > this and 0 completed today
ALERT_QUEUE_SLOW_THRESHOLD=500        # Alert if pending > this and processing too slow
ALERT_MIN_JOBS_PER_HOUR=20.0          # Minimum jobs/hour to avoid "slow queue" alert
```

## Monitoring

### Check Timer Status

```bash
# List all timers
systemctl list-timers polymarket-daily-*.timer

# Check specific timer
systemctl status polymarket-daily-analysis.timer
systemctl status polymarket-daily-report.timer
```

### View Logs

```bash
# Analysis service logs
journalctl -u polymarket-daily-analysis.service -f

# Report service logs
journalctl -u polymarket-daily-report.service -f

# Last 100 lines
journalctl -u polymarket-daily-analysis.service -n 100
journalctl -u polymarket-daily-report.service -n 100
```

### Manual Execution

```bash
# Run analysis manually
sudo systemctl start polymarket-daily-analysis.service

# Run report manually
sudo systemctl start polymarket-daily-report.service
```

## Troubleshooting

### Timer Not Running

1. Check if timer is enabled:
```bash
systemctl is-enabled polymarket-daily-analysis.timer
```

2. Check timer status:
```bash
systemctl status polymarket-daily-analysis.timer
```

3. Check for errors:
```bash
journalctl -u polymarket-daily-analysis.timer -n 50
```

### Service Fails

1. Check service logs:
```bash
journalctl -u polymarket-daily-analysis.service -n 100
```

2. Check if paths are correct in service file:
```bash
cat /etc/systemd/system/polymarket-daily-analysis.service
```

3. Test manual execution:
```bash
cd /opt/polymarket-bot
venv/bin/python3 daily_wallet_analysis.py
```

### No Telegram Notifications

1. Check `.env` file has correct Telegram credentials
2. Check service logs for Telegram errors
3. Test Telegram connection:
```bash
cd /opt/polymarket-bot
venv/bin/python3 -c "from notify import TelegramNotifier; n = TelegramNotifier(); n.send_message('Test message')"
```

## SQL Queries for Daily Statistics

### Get jobs completed today

```sql
SELECT COUNT(*) FROM wallet_analysis_jobs 
WHERE status = 'completed'
AND datetime(updated_at) >= datetime('now', 'start of day')
AND datetime(updated_at) < datetime('now', '+1 day', 'start of day');
```

### Get jobs failed today

```sql
SELECT COUNT(*) FROM wallet_analysis_jobs 
WHERE status = 'failed'
AND datetime(updated_at) >= datetime('now', 'start of day')
AND datetime(updated_at) < datetime('now', '+1 day', 'start of day');
```

### Get wallets added today

```sql
SELECT COUNT(*) FROM wallets 
WHERE datetime(added_at) >= datetime('now', 'start of day')
AND datetime(added_at) < datetime('now', '+1 day', 'start of day');
```

### Get wallets by source (today)

```sql
SELECT source, COUNT(*) FROM wallets 
WHERE datetime(added_at) >= datetime('now', 'start of day')
AND datetime(added_at) < datetime('now', '+1 day', 'start of day')
GROUP BY source;
```

### Get average processing time (today)

```sql
SELECT AVG(
    (julianday(updated_at) - julianday(created_at)) * 86400
) FROM wallet_analysis_jobs 
WHERE status = 'completed'
AND datetime(updated_at) >= datetime('now', 'start of day')
AND datetime(updated_at) < datetime('now', '+1 day', 'start of day');
```

## Files

- `daily_wallet_analysis.py` - Main daily analysis script
- `daily_report.py` - Daily report generator with alerts
- `get_daily_stats.py` - Utility to get daily statistics
- `polymarket-daily-analysis.service` - Systemd service for analysis
- `polymarket-daily-analysis.timer` - Systemd timer for analysis
- `polymarket-daily-report.service` - Systemd service for reporting
- `polymarket-daily-report.timer` - Systemd timer for reporting
- `setup_daily_schedule.sh` - Automated setup script

