# Polymarket Notifier Bot

A Python bot that monitors high-performing Polymarket wallets for consensus buy signals and sends Telegram alerts when multiple successful traders buy the same market outcome.

## Features

- **Comprehensive Leaderboard Scraping**: Uses Playwright to scrape ALL pages from Polymarket leaderboards
- **Smart Wallet Filtering**: Identifies wallets with 50+ trades, 65%+ win rate, and reasonable trading frequency
- **Real-time Monitoring**: Polls wallet trades every 7 seconds for new buy orders
- **Consensus Detection**: Alerts when 3+ tracked wallets buy the same market outcome within 10 minutes
- **Telegram Integration**: Sends formatted HTML alerts with wallet details and market links
- **SQLite Database**: Stores wallet data, trade history, and alert deduplication
- **Robust Error Handling**: Retry logic, logging, and graceful failure handling

## Quick Start

### 1. Python Version Compatibility

**Important:** This bot requires Python 3.11 or 3.12. Python 3.13 is not yet supported due to Playwright dependencies.

If you're using Python 3.13, see [PYTHON_COMPATIBILITY.md](PYTHON_COMPATIBILITY.md) for solutions.

### 2. Install Dependencies

```bash
pip install -r requirements.txt
playwright install chromium
```

### 3. Configure Telegram Bot

1. Message [@BotFather](https://t.me/BotFather) on Telegram
2. Create a new bot with `/newbot`
3. Get your bot token
4. Get your chat ID by messaging [@userinfobot](https://t.me/userinfobot)

### 4. Setup Environment

```bash
cp env.example .env
# Edit .env with your Telegram credentials
```

### 5. Run the Bot

```bash
python polymarket_notifier.py
```

### Alternative: Basic Version (Python 3.13)

If you're using Python 3.13, you can run the basic version:

```bash
pip install requests python-dotenv tenacity beautifulsoup4
python polymarket_notifier_basic.py
```

**Note:** The basic version only scrapes the first page of leaderboards.

## Configuration

Edit `.env` file to customize behavior:

```env
# Required
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here

# Optional (defaults shown)
POLL_INTERVAL_SEC=7          # Seconds between wallet checks
ALERT_WINDOW_MIN=10          # Minutes for consensus window  
MIN_CONSENSUS=3              # Minimum wallets for alert
MAX_WALLETS=200              # Maximum wallets to track
MAX_PREDICTIONS=1000         # Maximum trades per wallet
DB_PATH=polymarket_notifier.db
```

## How It Works

### 1. Wallet Collection
- Scrapes leaderboards from:
  - Daily profit leaderboard
  - Weekly profit leaderboard  
  - Monthly profit leaderboard
- Uses Playwright to handle React SPA pagination
- Extracts wallet addresses from profile links

### 2. Wallet Analysis
For each wallet, fetches data from Polymarket Data API:
- `/traded` → Total number of trades
- `/closed-positions` → Win rate and realized PnL
- Recent trades → Daily trading frequency

### 3. Filtering Criteria
Keeps wallets that meet ALL criteria:
- 50+ total trades
- 65%+ win rate (but <99% to avoid outliers)
- ≤10 trades per day (avoids bots)
- Top 200 by realized PnL

### 4. Monitoring & Alerts
- Polls `/trades?user=0x...&side=BUY` every 7 seconds
- Maintains rolling 10-minute window per market outcome
- Sends alert when 3+ wallets buy same outcome
- Deduplicates alerts to prevent spam

## File Structure

```
polymarket_notifier/
├── polymarket_notifier.py    # Main script
├── fetch_leaderboards.py     # Playwright scraper
├── db.py                     # SQLite helpers
├── notify.py                 # Telegram notifications
├── requirements.txt          # Dependencies
├── env.example              # Configuration template
├── README.md                # This file
└── polymarket_notifier.db   # SQLite database (created on first run)
```

## Alert Format

Telegram alerts include:
- Market condition ID and outcome index
- Number of wallets in consensus
- List of wallet addresses (first 10)
- Market link
- Timestamp and alert ID

Example:
```
🔥 Consensus Buy Signal

Market: 0x12345678...
Outcome: Index 0
Consensus: 5 wallets in 10m (min 3)
Strength: 📈 Moderate

👛 Top buyers:
• 0xabc123...
• 0xdef456...
• 0x789ghi...

🔗 Market: https://polymarket.com/market/0x12345678...

2024-01-15 14:30:25 UTC • alert id a1b2c3d4
```

## Database Schema

### wallets
- `address` (TEXT PRIMARY KEY)
- `display` (TEXT) - Display name
- `traded_total` (INTEGER) - Total trades
- `win_rate` (REAL) - Win percentage
- `realized_pnl_total` (REAL) - Total PnL
- `daily_trading_frequency` (REAL) - Trades per day
- `source` (TEXT) - Leaderboard URL
- `added_at` (TEXT) - Timestamp
- `updated_at` (TEXT) - Last update

### last_trades
- `address` (TEXT PRIMARY KEY)
- `last_seen_trade_id` (TEXT)
- `updated_at` (TEXT)

### alerts_sent
- `alert_key` (TEXT PRIMARY KEY)
- `sent_at` (TEXT)
- `condition_id` (TEXT)
- `outcome_index` (INTEGER)
- `wallet_count` (INTEGER)

### rolling_buys
- `k` (TEXT PRIMARY KEY) - Hash of conditionId:outcomeIndex
- `data` (TEXT) - JSON with events and timestamps
- `updated_at` (TEXT)

## Troubleshooting

### Common Issues

1. **"Telegram connection test failed"**
   - Check `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` in `.env`
   - Ensure bot token is valid and chat ID is correct

2. **"No wallets to monitor"**
   - Bot is still collecting wallets from leaderboards
   - Check logs for scraping progress
   - May take 5-10 minutes for initial collection

3. **"Playwright browser not found"**
   - Run `playwright install chromium`
   - Ensure Playwright is properly installed

4. **"Database locked"**
   - Stop other instances of the bot
   - Check file permissions on database

### Logs

Logs are written to:
- Console output (INFO level)
- `polymarket_notifier.log` file

### Performance

- Initial wallet collection: 5-10 minutes
- Memory usage: ~50-100MB
- CPU usage: Low (mostly I/O bound)
- Network: Moderate (API calls every 7 seconds)

## Advanced Usage

### Custom Leaderboards

Add custom leaderboard URLs in `polymarket_notifier.py`:

```python
self.leaderboard_urls = [
    "https://polymarket.com/leaderboard/overall/monthly/profit",
    "https://polymarket.com/leaderboard/custom/your-url",
]
```

### Adjusting Criteria

Modify filtering criteria in the `analyze_and_filter_wallets` method:

```python
criteria = {
    "min_trades": 100,        # Higher minimum
    "min_win_rate": 0.70,     # Higher win rate
    "max_daily_freq": 5.0     # Lower frequency
}
```

### Custom Alert Thresholds

Change consensus requirements:

```env
MIN_CONSENSUS=5              # Require 5+ wallets
ALERT_WINDOW_MIN=15          # 15-minute window
```

### Debug: All-Time Volume Leaderboard

For debugging the problematic `overall/all/volume` leaderboard page, there's a separate robust extraction script:

```bash
python3 robust_all_volume_leaderboard.py \
  --url "https://polymarket.com/leaderboard/overall/all/volume" \
  --proxy "quality.proxywing.com:8888" \
  --out-dir ./debug_all_volume_run
```

The script saves:
- `debug_all_volume.html` - Full page HTML
- `debug_all_volume.png` - Full page screenshot
- `addresses.txt` - Extracted wallet addresses

This script uses extended timeouts (90s), multiple retry attempts, scroll-based loading, and regex fallback extraction. It's designed as a standalone debugging tool and is not integrated into the main scraper.

## Security Notes

- Bot token should be kept secret
- Database file contains wallet addresses (sensitive)
- Consider running in isolated environment
- Monitor for unusual API usage

## Contributing

1. Fork the repository
2. Create feature branch
3. Make changes with tests
4. Submit pull request

## License

MIT License - see LICENSE file for details

## Support

For issues and questions:
- Check logs for error messages
- Verify configuration in `.env`
- Test Telegram bot manually
- Review Polymarket API documentation

---

**Disclaimer**: This bot is for educational purposes. Trading involves risk. Past performance doesn't guarantee future results. Use at your own risk.
