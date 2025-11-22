# Code Synchronization Verification Guide

## Overview

This guide helps you verify that code changes deployed to your remote server match your local codebase. The verification scripts check all repository files (Python files, systemd service/timer files, and key configuration files) to ensure complete synchronization.

The implementation plan included security, correctness, and performance improvements to several critical files:

1. **`utils/http_client.py`** - Security fixes (proxy URL masking, TLS verification)
2. **`bet_monitor.py`** - Correctness fixes (timestamp normalization, bet side detection)
3. **`price_fetcher.py`** - Reliability improvements (retry logic, time budget)
4. **`notify.py`** - (Check if changes were made)

## Quick Verification Method: Using Checksums

This is the fastest way to verify code synchronization. The scripts automatically detect the available checksum tool (`shasum` on macOS, `sha256sum` on Linux) and verify all repository files.

### Step 1: Generate Local Checksums

Run the local verification script:

```bash
cd /Users/johnbravo/polymarket
chmod +x verify_local_code.sh
./verify_local_code.sh
```

This will:
- Auto-detect the checksum command (`shasum` or `sha256sum`)
- Compute SHA256 checksums for all repository files (`.py`, `.service`, `.timer`, `requirements.txt`, `env.example`)
- Display file sizes and line counts
- Save results to `local_checksums.txt`

### Step 2: Generate Remote Checksums

Upload the remote verification script to your server:

```bash
scp verify_remote_code.sh ubuntu@YOUR_SERVER_IP:~/polymarket/
```

SSH into your server and run it:

```bash
ssh ubuntu@YOUR_SERVER_IP
cd ~/polymarket
chmod +x verify_remote_code.sh
./verify_remote_code.sh
```

If your project is in a different location, specify it:

```bash
./verify_remote_code.sh /path/to/polymarket
```

### Step 3: Compare Checksums

Download the remote checksums file:

```bash
scp ubuntu@YOUR_SERVER_IP:~/polymarket/remote_checksums.txt ./
```

Compare the two files:

```bash
diff local_checksums.txt remote_checksums.txt
```

**If checksums match:** ✅ Code is synchronized  
**If checksums don't match:** See "Deployment Commands" section below

## Manual Verification Method: Direct File Comparison

If you prefer to verify specific changes manually, use these SSH commands to view key sections on the server.

### Connect to Server

```bash
ssh ubuntu@YOUR_SERVER_IP
cd ~/polymarket  # Adjust path if different
```

### Verify utils/http_client.py

**Check 1: _mask_proxy_url() function exists**

```bash
# Find the function and show surrounding lines
line_num=$(grep -n "def _mask_proxy_url" utils/http_client.py | cut -d: -f1)
sed -n "$((line_num - 5)),$((line_num + 50))p" utils/http_client.py
```

Expected: Function that masks username/password in proxy URLs.

**Check 2: verify=True default**

```bash
# Find http_get function and show signature
line_num=$(grep -n "def http_get" utils/http_client.py | cut -d: -f1)
sed -n "$((line_num - 3)),$((line_num + 10))p" utils/http_client.py | grep "verify"
```

Expected: `verify: bool = True` in function signature.

**Check 3: Masked logging**

```bash
# Find where _mask_proxy_url is called
grep -n "_mask_proxy_url" utils/http_client.py
```

Expected: `_mask_proxy_url()` called before logging proxy URL.

### Verify bet_monitor.py

**Check 1: normalize_timestamp() function**

```bash
# Find the function and show surrounding lines
line_num=$(grep -n "def normalize_timestamp" bet_monitor.py | cut -d: -f1)
sed -n "$((line_num - 5)),$((line_num + 30))p" bet_monitor.py
```

Expected: Function that handles both seconds and milliseconds timestamps.

**Check 2: MatchingBet side field**

```bash
# Find MatchingBet class and show side field
line_num=$(grep -n "class MatchingBet" bet_monitor.py | cut -d: -f1)
sed -n "$((line_num - 3)),$((line_num + 15))p" bet_monitor.py | grep "side"
```

Expected: `side: str  # 'buy' or 'sell'` field in dataclass.

**Check 3: Retry logic**

```bash
# Find send_message function and show retry logic
line_num=$(grep -n "async def send_message" bet_monitor.py | cut -d: -f1)
sed -n "$((line_num - 3)),$((line_num + 60))p" bet_monitor.py | head -30
```

Expected: Retry logic with 429 error handling and exponential backoff.

### Verify price_fetcher.py

**Check 1: Configuration constants**

```bash
# Find constants and show surrounding lines
line_num=$(grep -n "REQUEST_TIMEOUT\|MAX_RETRIES\|OVERALL_TIME_BUDGET" price_fetcher.py | head -1 | cut -d: -f1)
sed -n "$((line_num - 3)),$((line_num + 8))p" price_fetcher.py
```

Expected: `REQUEST_TIMEOUT`, `MAX_RETRIES`, `OVERALL_TIME_BUDGET` constants.

**Check 2: Retry function exists**

```bash
grep -n "_retry_with_backoff\|retry.*backoff" price_fetcher.py | head -5
```

Expected: Retry function with exponential backoff.

### Verify notify.py

Check if file exists and has expected structure:

```bash
wc -l notify.py
head -20 notify.py
```

## Detailed Change Checklist

**Note:** This checklist uses symbol-based verification (function/class names) instead of line numbers, making it robust to code changes.

### utils/http_client.py

- [ ] **`_mask_proxy_url()` function** exists
  - Function takes proxy URL string
  - Masks password with `***`
  - Handles parsing errors gracefully
  - Verify: `grep -n "def _mask_proxy_url" utils/http_client.py`

- [ ] **`verify: bool = True` default parameter** in `http_get()` function
  - TLS verification enabled by default
  - Comment explains security benefit
  - Verify: `grep -n "def http_get" utils/http_client.py` then check function signature

- [ ] **Masked proxy URL in logging**
  - Uses `_mask_proxy_url()` before logging
  - Logs show `user:***@host` format
  - Verify: `grep -n "_mask_proxy_url" utils/http_client.py`

### bet_monitor.py

- [ ] **`normalize_timestamp()` function** exists
  - Handles int, float, and string timestamps
  - Detects milliseconds (values > 1e10)
  - Converts to UTC datetime
  - Verify: `grep -n "def normalize_timestamp" bet_monitor.py`

- [ ] **`side` field in `MatchingBet` dataclass**
  - Field type: `str`
  - Comment: `# 'buy' or 'sell' - actual trade direction`
  - Verify: `grep -n "class MatchingBet" bet_monitor.py` then check for `side` field

- [ ] **Retry logic in `send_message()` method**
  - Handles 429 rate limit errors
  - Reads `retry_after` from response
  - Exponential backoff for network errors
  - Max retries: 3
  - Verify: `grep -n "async def send_message" bet_monitor.py` then check for retry logic

- [ ] **Session reuse**
  - Shared `aiohttp.ClientSession`
  - Context manager (`__aenter__`, `__aexit__`)
  - Verify: `grep -n "ClientSession\|__aenter__\|__aexit__" bet_monitor.py`

- [ ] **Bet detection groups by side**
  - Groups bets by `side` field
  - Uses actual trade direction
  - Verify: `grep -n "groupby.*side\|side.*group" bet_monitor.py`

- [ ] **Alerts use actual trade side**
  - Alert message includes `side` field
  - Shows correct trade direction
  - Verify: Check alert generation code for `side` field usage

### price_fetcher.py

- [ ] **Configuration constants** exist
  - `REQUEST_TIMEOUT = 5`
  - `MAX_RETRIES = 2`
  - `OVERALL_TIME_BUDGET = 30`
  - Verify: `grep -n "REQUEST_TIMEOUT\|MAX_RETRIES\|OVERALL_TIME_BUDGET" price_fetcher.py`

- [ ] **Retry function with exponential backoff** exists
  - `_retry_with_backoff()` function exists
  - Implements exponential backoff
  - Respects time budget
  - Verify: `grep -n "_retry_with_backoff" price_fetcher.py`

- [ ] **Time budget enforcement**: Overall timeout respected
  - Checks elapsed time before retries
  - Fails fast if budget exceeded
  - Verify: `grep -n "OVERALL_TIME_BUDGET\|elapsed" price_fetcher.py`

### notify.py

- [ ] Check if file was modified in implementation plan
- [ ] Verify any changes match expected behavior

## SSH Commands Reference

### Connection

```bash
ssh ubuntu@YOUR_SERVER_IP
```

### Navigate to Project

```bash
cd ~/polymarket
# Or if different location:
cd /path/to/polymarket
```

### Check File Existence

```bash
ls -lh utils/http_client.py bet_monitor.py price_fetcher.py notify.py
```

### Generate Checksums on Server

```bash
sha256sum utils/http_client.py bet_monitor.py price_fetcher.py notify.py
```

### View File Sizes and Line Counts

```bash
wc -l utils/http_client.py bet_monitor.py price_fetcher.py notify.py
ls -lh utils/http_client.py bet_monitor.py price_fetcher.py notify.py
```

### View Specific Line Ranges

```bash
# _mask_proxy_url function
sed -n '18,64p' utils/http_client.py

# verify default
sed -n '73p' utils/http_client.py

# normalize_timestamp function
sed -n '16,43p' bet_monitor.py

# MatchingBet side field
sed -n '72p' bet_monitor.py

# Retry logic
sed -n '96,152p' bet_monitor.py
```

## Troubleshooting

### Issue: File Not Found on Server

**Solution:** Check project directory location:

```bash
ssh ubuntu@YOUR_SERVER_IP
find ~ -name "bet_monitor.py" -type f 2>/dev/null
```

Update `verify_remote_code.sh` with correct path or pass it as argument.

### Issue: Checksums Don't Match

**Possible causes:**
1. Files weren't deployed
2. Files were modified on server
3. Line ending differences (CRLF vs LF)

**Solution:** Deploy files using commands in "Deployment Commands" section.

### Issue: Script Permission Denied

**Solution:** Make script executable:

```bash
chmod +x verify_remote_code.sh
```

### Issue: sha256sum Command Not Found

**Solution:** The scripts now auto-detect the available checksum tool. If you see an error that neither `shasum` nor `sha256sum` is found, install one:

```bash
# On macOS (usually pre-installed)
# shasum should be available by default

# On Linux (usually pre-installed)
# sha256sum should be available by default

# If missing, install coreutils (Linux) or ensure system utilities are available
```

## Deployment Commands

If checksums don't match, deploy the correct files to the server.

### Upload Files via SCP

From your local machine:

```bash
# Upload utils/http_client.py
scp /Users/johnbravo/polymarket/utils/http_client.py ubuntu@YOUR_SERVER_IP:~/polymarket/utils/

# Upload bet_monitor.py
scp /Users/johnbravo/polymarket/bet_monitor.py ubuntu@YOUR_SERVER_IP:~/polymarket/

# Upload price_fetcher.py
scp /Users/johnbravo/polymarket/price_fetcher.py ubuntu@YOUR_SERVER_IP:~/polymarket/

# Upload notify.py (if modified)
scp /Users/johnbravo/polymarket/notify.py ubuntu@YOUR_SERVER_IP:~/polymarket/
```

### Restart Services

After uploading files, restart services to load changes:

```bash
ssh ubuntu@YOUR_SERVER_IP 'cd ~/polymarket && ./restart_services.sh'
```

Or manually restart:

```bash
ssh ubuntu@YOUR_SERVER_IP
cd ~/polymarket
sudo systemctl daemon-reload
sudo systemctl restart polymarket-bot.service  # If exists
sudo systemctl restart polymarket-daily-analysis.timer
```

### Verify Deployment

After restarting, run verification again:

```bash
ssh ubuntu@YOUR_SERVER_IP 'cd ~/polymarket && ./verify_remote_code.sh'
```

Compare checksums again to confirm synchronization.

## Alternative: Using compare_code_snippets.sh

For quick visual verification, use the snippet comparison script:

**Locally:**
```bash
./compare_code_snippets.sh
```

**On Server:**
```bash
# Upload script first
scp compare_code_snippets.sh ubuntu@YOUR_SERVER_IP:~/polymarket/

# Then run on server
ssh ubuntu@YOUR_SERVER_IP 'cd ~/polymarket && chmod +x compare_code_snippets.sh && ./compare_code_snippets.sh'
```

Compare the output from both runs to verify key changes are present.

## Summary

1. **Quickest method**: Use checksum scripts (`verify_local_code.sh` and `verify_remote_code.sh`)
   - Automatically detects checksum tool (`shasum` or `sha256sum`)
   - Verifies all repository files (`.py`, `.service`, `.timer`, config files)
   - OS-agnostic and robust to environment differences
2. **Most thorough**: Use manual verification with SSH commands (symbol-based, not line-number-based)
3. **Visual check**: Use `compare_code_snippets.sh` to see key code sections
   - Uses symbol-based extraction (function names) instead of line numbers
   - Robust to code changes and shifts
4. **If mismatch**: Deploy files using SCP commands and restart services

For more SSH command examples, see `SSH_COMMANDS.md`.

