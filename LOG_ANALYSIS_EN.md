# Logging Analysis and Slug Issues

## Question 1: Are you seeing the new logging output in your console/server logs when alerts are sent?

### Answer: **Yes, but partially**

I can see `logger.info()` outputs in the logs, but **not** `logger.debug()` outputs.

### Sample log entry for a sports market (FIFA Brazil-Tunisia):

From the server logs (line 146, timestamp 22:14:37 UTC):

```
[SPORTS_DETECT] event_id=None, slug=None, market_slug=fif-bra-tun-2025-11-18-tun, is_sports=True, category=None, tags=None
```

This is the only `logger.info()` output from the `_detect_sports_event()` function (line 1982 in `notify.py`).

### What is NOT visible (because it uses `logger.debug()`):

**Detailed logging from `gamma_client.py` (lines 237-263):**
- `[GAMMA] [DEBUG] Event structure:`
- `[GAMMA] [DEBUG]   - Event keys: [...]`
- `[GAMMA] [DEBUG]   - Event category: ...`
- `[GAMMA] [DEBUG]   - Event type: ...`
- `[GAMMA] [DEBUG]   - Event groupType: ...`
- `[GAMMA] [DEBUG]   - Event tags: ...`
- `[GAMMA] [DEBUG]   - Matching market keys: [...]`
- `[GAMMA] [DEBUG]   - Matching market slug: ...`
- `[GAMMA] [DEBUG]   - URL-related fields in market: {...}`
- `[GAMMA] [DEBUG]   - Sample event object (first 1500 chars): ...`

**Detailed logging from `notify.py` (lines 1904-1910):**
- `[SPORTS_DETECT]   - event_id: ...`
- `[SPORTS_DETECT]   - category: ...`
- `[SPORTS_DETECT]   - groupType: ...`
- `[SPORTS_DETECT]   - type: ...`
- `[SPORTS_DETECT]   - eventType: ...`
- `[SPORTS_DETECT]   - group: ...`
- `[SPORTS_DETECT]   - tags: ...`

### Why it's not visible:

The logging level on the server is likely set to `INFO`, not `DEBUG`. Therefore, all `logger.debug()` calls are filtered out and don't appear in the logs.

### Solution:

To see detailed event structure logging, you have two options:

1. **Change logging level to DEBUG** in `.env`:
   ```env
   TASKMASTER_LOG_LEVEL=DEBUG
   ```
   Then restart the service:
   ```bash
   sudo systemctl restart polymarket-bot
   ```

2. **Change critical `logger.debug()` calls to `logger.info()`** in the code:
   - In `gamma_client.py`: Change lines 238-253 from `logger.debug()` to `logger.info()`
   - In `notify.py`: Change lines 1904-1910 from `logger.debug()` to `logger.info()`

---

## Question 2: For the slug issue (Solomon example): Has the malformed slug with numbers appeared in recent alerts, or was it a one-off?

### Answer: **Not found in recent logs**

In the provided server logs (from 22:00:00 to 23:00:00 UTC on 2025-11-18), I did **not** find any malformed slugs with numbers. All slugs found follow the correct format:

### Examples of correct slugs found:
- `fif-bra-tun-2025-11-18-tun` ✅ (date in YYYY-MM-DD format)
- `uef-aut-bih-2025-11-18-aut` ✅ (correct format)
- `nhl-nyi-dal-2025-11-18` ✅ (correct format)
- `btc-updown-15m-1763500500` ✅ (timestamp format, acceptable)

### What would indicate a problem:
- `solomon-123456789` ❌ (numbers without date pattern)
- `solomon-islands-2025-11-18-123456` ❌ (extra numbers at the end)
- `solomon-2025-11-18-999999` ❌ (long number sequence)

### To check for malformed slugs on the server:

```bash
# Search for slugs with long number sequences (6+ digits)
sudo journalctl -u polymarket-bot -n 5000 | grep 'market_slug=' | grep -E '[0-9]{6,}'

# Search for all slugs to analyze patterns
sudo journalctl -u polymarket-bot -n 5000 | grep 'market_slug=' | tail -50

# Search for slugs with numbers at the end (after date)
sudo journalctl -u polymarket-bot -n 5000 | grep 'market_slug=' | grep -E '[0-9]{4}-[0-9]{2}-[0-9]{2}-[0-9]{3,}'
```

### Conclusion:

Based on the recent logs analyzed, **the malformed slug issue appears to be a one-off** or has been resolved. All recent sports market slugs follow the expected pattern with dates in `YYYY-MM-DD` format.

If you want to monitor for this issue going forward, you can set up a log filter or add validation in the code to detect and log malformed slugs.


