# SSH Commands Reference

Ready-to-use SSH commands for verifying and comparing code on the remote server.

## Connection

```bash
ssh ubuntu@
```

## Navigate to Project Directory

```bash
# Default location
cd ~/polymarket

# If project is in different location, find it:
find ~ -name "bet_monitor.py" -type f 2>/dev/null
find /opt -name "bet_monitor.py" -type f 2>/dev/null
find /home -name "bet_monitor.py" -type f 2>/dev/null
```

## Check File Existence

```bash
# Check all four critical files exist
ls -lh utils/http_client.py bet_monitor.py price_fetcher.py notify.py

# Check with detailed info
stat utils/http_client.py bet_monitor.py price_fetcher.py notify.py

# Check if files are readable
test -r utils/http_client.py && echo "✅ http_client.py readable" || echo "❌ http_client.py not readable"
test -r bet_monitor.py && echo "✅ bet_monitor.py readable" || echo "❌ bet_monitor.py not readable"
test -r price_fetcher.py && echo "✅ price_fetcher.py readable" || echo "❌ price_fetcher.py not readable"
test -r notify.py && echo "✅ notify.py readable" || echo "❌ notify.py not readable"
```

## View File Checksums

```bash
# Generate SHA256 checksums for all critical files
sha256sum utils/http_client.py bet_monitor.py price_fetcher.py notify.py

# Save to file
sha256sum utils/http_client.py bet_monitor.py price_fetcher.py notify.py > remote_checksums.txt
cat remote_checksums.txt
```

## View Specific Code Sections (Symbol-Based)

All commands use symbol-based extraction (function/class names) instead of line numbers, making them robust to code changes.

### utils/http_client.py

**View _mask_proxy_url() function:**
```bash
# Find function and show surrounding lines
line_num=$(grep -n "def _mask_proxy_url" utils/http_client.py | cut -d: -f1)
sed -n "$((line_num - 5)),$((line_num + 50))p" utils/http_client.py
```

**View function signature with verify parameter:**
```bash
# Find http_get function and show signature
line_num=$(grep -n "def http_get" utils/http_client.py | cut -d: -f1)
sed -n "$((line_num - 3)),$((line_num + 10))p" utils/http_client.py
```

**View masked logging usage:**
```bash
# Find where _mask_proxy_url is called
grep -n "_mask_proxy_url" utils/http_client.py
```

**Check verify parameter default:**
```bash
grep -n "verify.*True" utils/http_client.py | head -5
```

### bet_monitor.py

**View normalize_timestamp() function:**
```bash
# Find function and show surrounding lines
line_num=$(grep -n "def normalize_timestamp" bet_monitor.py | cut -d: -f1)
sed -n "$((line_num - 5)),$((line_num + 30))p" bet_monitor.py
```

**View MatchingBet dataclass with side field:**
```bash
# Find class and show definition
line_num=$(grep -n "class MatchingBet" bet_monitor.py | cut -d: -f1)
sed -n "$((line_num - 3)),$((line_num + 15))p" bet_monitor.py
```

**Check side field specifically:**
```bash
# Find MatchingBet class and grep for side field
line_num=$(grep -n "class MatchingBet" bet_monitor.py | cut -d: -f1)
sed -n "$((line_num - 3)),$((line_num + 15))p" bet_monitor.py | grep "side"
grep -n "side.*str" bet_monitor.py
```

**View retry logic in send_message():**
```bash
# Find send_message function and show retry logic
line_num=$(grep -n "async def send_message" bet_monitor.py | cut -d: -f1)
sed -n "$((line_num - 3)),$((line_num + 60))p" bet_monitor.py
```

**Check for 429 error handling:**
```bash
grep -n "429\|rate limit\|retry_after" bet_monitor.py
```

**Check session reuse:**
```bash
grep -n "ClientSession\|__aenter__\|__aexit__" bet_monitor.py
```

**Check bet grouping by side:**
```bash
grep -n "groupby.*side\|side.*group" bet_monitor.py
```

### price_fetcher.py

**View configuration constants:**
```bash
# Find constants and show surrounding lines
line_num=$(grep -n "REQUEST_TIMEOUT\|MAX_RETRIES\|OVERALL_TIME_BUDGET" price_fetcher.py | head -1 | cut -d: -f1)
sed -n "$((line_num - 3)),$((line_num + 8))p" price_fetcher.py
```

**Check retry function:**
```bash
grep -n "_retry_with_backoff\|retry.*backoff" price_fetcher.py | head -10
```

**View retry function implementation:**
```bash
# Find function and show implementation
line_num=$(grep -n "def _retry_with_backoff" price_fetcher.py | cut -d: -f1)
sed -n "$line_num,$((line_num + 30))p" price_fetcher.py
```

**Check time budget enforcement:**
```bash
grep -n "OVERALL_TIME_BUDGET\|time.*budget\|elapsed" price_fetcher.py
```

### notify.py

**View file header:**
```bash
head -30 notify.py
```

**Check file size:**
```bash
wc -l notify.py
```

## Compare File Sizes and Line Counts

```bash
# Line counts
wc -l utils/http_client.py bet_monitor.py price_fetcher.py notify.py

# File sizes in bytes
stat -c%s utils/http_client.py bet_monitor.py price_fetcher.py notify.py

# Human-readable sizes
ls -lh utils/http_client.py bet_monitor.py price_fetcher.py notify.py

# Combined view
for file in utils/http_client.py bet_monitor.py price_fetcher.py notify.py; do
    echo "=== $file ==="
    echo "Lines: $(wc -l < "$file")"
    echo "Size: $(stat -c%s "$file") bytes"
    echo ""
done
```

## Upload Files (if checksums don't match)

From your **local machine**, upload files to server:

```bash
# Upload utils/http_client.py
scp /Users/johnbravo/polymarket/utils/http_client.py ubuntu@:~/polymarket/utils/

# Upload bet_monitor.py
scp /Users/johnbravo/polymarket/bet_monitor.py ubuntu@:~/polymarket/

# Upload price_fetcher.py
scp /Users/johnbravo/polymarket/price_fetcher.py ubuntu@~/polymarket/

# Upload notify.py (if modified)
scp /Users/johnbravo/polymarket/notify.py ubuntu@:~/polymarket/

# Upload verification scripts
scp verify_remote_code.sh ubuntu@:~/polymarket/
scp compare_code_snippets.sh ubuntu@:~/polymarket/
```

## Upload and Run Verification Script

```bash
# From local machine - upload script
scp verify_remote_code.sh ubuntu@:~/polymarket/

# SSH and run
ssh ubuntu@ 'cd ~/polymarket && chmod +x verify_remote_code.sh && ./verify_remote_code.sh'

# Download results
scp ubuntu@:~/polymarket/remote_checksums.txt ./
```

## Restart Services

After deploying files, restart services to load changes:

### Using restart_services.sh

```bash
ssh ubuntu@ 'cd ~/polymarket && ./restart_services.sh'
```

### Manual Restart Commands

```bash
ssh ubuntu@
cd ~/polymarket

# Reload systemd daemon
sudo systemctl daemon-reload

# Restart main bot service (if exists)
sudo systemctl restart polymarket-bot.service

# Restart timers
sudo systemctl restart polymarket-daily-analysis.timer
sudo systemctl restart polymarket-daily-report.timer
sudo systemctl restart polymarket-daily-refresh.timer

# Check status
sudo systemctl status polymarket-bot.service --no-pager -l | head -20
sudo systemctl list-timers polymarket-daily-*.timer --no-pager
```

### One-liner Restart

```bash
ssh ubuntu@] 'cd ~/polymarket && sudo systemctl daemon-reload && sudo systemctl restart polymarket-bot.service polymarket-daily-analysis.timer polymarket-daily-report.timer polymarket-daily-refresh.timer 2>/dev/null; echo "Services restarted"'
```

## Check Service Logs

```bash
# Main bot logs
ssh ubuntu@ 'journalctl -u polymarket-bot.service -n 50 --no-pager'

# Daily analysis logs
ssh ubuntu@ 'journalctl -u polymarket-daily-analysis.service -n 50 --no-pager'

# Follow logs in real-time
ssh ubuntu@'journalctl -u polymarket-bot.service -f'

# Check for errors
ssh ubuntu@ 'journalctl -u polymarket-bot.service --since "1 hour ago" | grep -i error'
```

## Quick Verification Checklist

Run these commands on the server to quickly verify all changes:

```bash
# 1. Check files exist
ls -lh utils/http_client.py bet_monitor.py price_fetcher.py notify.py

# 2. Verify _mask_proxy_url exists
grep -q "_mask_proxy_url" utils/http_client.py && echo "✅ _mask_proxy_url found" || echo "❌ _mask_proxy_url missing"

# 3. Verify verify=True default
grep -q "verify.*=.*True" utils/http_client.py && echo "✅ verify=True found" || echo "❌ verify=True missing"

# 4. Verify normalize_timestamp exists
grep -q "def normalize_timestamp" bet_monitor.py && echo "✅ normalize_timestamp found" || echo "❌ normalize_timestamp missing"

# 5. Verify side field exists
grep -q "side.*str.*buy.*sell" bet_monitor.py && echo "✅ side field found" || echo "❌ side field missing"

# 6. Verify retry logic exists
grep -q "429\|retry_after" bet_monitor.py && echo "✅ retry logic found" || echo "❌ retry logic missing"

# 7. Verify price_fetcher constants
grep -q "OVERALL_TIME_BUDGET\|MAX_RETRIES" price_fetcher.py && echo "✅ price_fetcher config found" || echo "❌ price_fetcher config missing"
```

## Compare Local vs Remote Checksums

```bash
# Generate local checksums
cd /Users/johnbravo/polymarket
./verify_local_code.sh

# Generate remote checksums (on server)
ssh ubuntu 'cd ~/polymarket && ./verify_remote_code.sh'

# Download remote checksums
scp ubuntu@ ~/polymarket/remote_checksums.txt ./

# Compare
diff local_checksums.txt remote_checksums.txt

# Or use visual diff
vimdiff local_checksums.txt remote_checksums.txt
```

## Find Project Directory on Server

If you're not sure where the project is located:

```bash
# Search common locations
ssh ubuntu 'find ~ /opt /home -name "bet_monitor.py" -type f 2>/dev/null | head -5'

# Check for polymarket directory
ssh ubuntu 'find ~ -type d -name "polymarket" 2>/dev/null'

# Check running processes for hints
ssh ubuntu 'ps aux | grep -i polymarket | grep -v grep'
```

## Environment Check

```bash
# Check Python version
ssh ubuntu 'python3 --version'

# Check if virtual environment is used
ssh ubuntu 'cd ~/polymarket && test -d venv && echo "venv found" || echo "no venv"'

# Check file permissions
ssh ubuntu 'cd ~/polymarket && ls -la utils/http_client.py bet_monitor.py price_fetcher.py notify.py'
```

## Notes

- Replace `~/polymarket` with actual project path if different
- Some commands require `sudo` for systemd operations
- Use `-n` flag with `sed` to suppress default output
- Use `2>/dev/null` to suppress error messages when searching
- Commands can be chained with `&&` for conditional execution
- **Symbol-based extraction**: All code viewing commands use function/class names instead of line numbers, making them robust to code changes
- **Checksum auto-detection**: Verification scripts automatically detect `shasum` (macOS) or `sha256sum` (Linux)
- **Full repository verification**: Verification scripts check all `.py`, `.service`, `.timer`, and config files, not just critical files

For detailed verification steps, see `VERIFICATION_GUIDE.md`.

