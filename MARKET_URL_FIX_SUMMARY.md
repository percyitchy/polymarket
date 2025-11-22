# Market URL Fix Summary

## Problem
The bot was generating incorrect URLs for complex markets (markets with multiple sub-markets), pointing to event pages instead of specific markets:

- **Market 1 (Maduro)**: Wrong URL: `https://polymarket.com/event/maduro-out-by-november-30-2025`
- **Market 2 (Trump Epstein Bill)**: Wrong URL: `https://polymarket.com/event/will-trump-sign-the-epstein-disclosure-bill-on-november-19`

Both URLs should point to specific sub-markets using either:
- `https://polymarket.com/event/{event_slug}?tid={market_id}` format (preferred for complex markets)
- `https://polymarket.com/event/{event_slug}/{market_slug}` format (fallback)

## Root Cause
The bot was getting `event_slug` from the Gamma API but **NOT** getting `market_id` (tid) from the APIs. Without `market_id`, the code fell back to using just `event_slug`, which points to the event page instead of the specific market.

## Solution
Enhanced the `market_id` extraction logic to:

1. **Added Data API as fallback source**: Added `https://data-api.polymarket.com/condition/{condition_id}` as an additional fallback source for `market_id` when Gamma API and CLOB API don't provide it.

2. **Improved field name checking**: Enhanced the extraction logic to check multiple field names:
   - `id`
   - `marketId`
   - `tid`
   - `market_id`
   - `marketIdNum`

3. **Better string ID handling**: Improved parsing of string IDs by extracting numeric values using regex when the API returns string IDs.

4. **Enhanced logging**: Added better logging to help debug future issues:
   - Logs when `market_id` is found from each API source
   - Logs available fields when `market_id` is not found
   - Logs parsing errors with details

## Changes Made

### 1. `_get_event_slug_and_market_id()` function (lines ~1757-1820)
- Added Data API fallback after CLOB API fallback
- Improved CLOB API field name checking
- Enhanced string ID parsing logic

### 2. `send_consensus_alert()` function (lines ~207-281)
- Added Data API fallback after CLOB API fallback
- Improved field name checking consistency

### 3. `send_suppressed_alert_details()` function (lines ~1229-1303)
- Added Data API fallback after CLOB API fallback
- Maintained consistency with main alert function

## API Priority Order
The bot now tries to get `market_id` in this order:

1. **Gamma API** (from matching market object in event)
2. **CLOB API** (`https://clob.polymarket.com/markets/{condition_id}`)
3. **Data API** (`https://data-api.polymarket.com/condition/{condition_id}`) - **NEW**

## Testing Recommendations

To verify the fix works:

1. **Use the diagnostic script**:
   ```bash
   python3 debug_market_url.py <condition_id>
   ```
   This will show what data is available from each API.

2. **Check bot logs** for:
   - `[EVENT_SLUG] ✅ Got market_id={market_id} from ...` - indicates successful extraction
   - `[URL] ✅ Got market_id={market_id} from ...` - indicates successful URL construction
   - `[URL] ✅ Using event_slug?tid format` - indicates correct URL format

3. **Test with known complex markets**:
   - Markets with multiple sub-markets (e.g., Bitcoin price markets, election markets)
   - Markets that previously showed incorrect URLs

## Expected Behavior After Fix

- **Complex markets with `market_id`**: URLs will use `?tid={market_id}` format
- **Complex markets without `market_id` but with `market_slug`**: URLs will use `/{market_slug}` format
- **Simple markets**: URLs will continue to work as before

## Debugging

If URLs are still incorrect:

1. Check logs for `[EVENT_SLUG]` and `[URL]` prefixes
2. Look for warnings about missing `market_id`
3. Use `debug_market_url.py` to inspect API responses
4. Check if the market is actually a complex market (has multiple sub-markets)

## Related Files
- `notify.py` - Main notification logic with URL construction
- `debug_market_url.py` - Diagnostic script for debugging market URLs
- `gamma_client.py` - Gamma API client

