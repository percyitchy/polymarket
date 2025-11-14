# HashDive API Integration

## Current Status

**Bot Status**: ✅ Stopped  
**API Status**: ❌ Unavailable (502 Bad Gateway)  
**Last Tested**: October 26, 2025

## API Configuration

### Base URL
```
https://hashdive.com/api/
```

### API Key
```
2fcbbb010f3ff15f84dc47ebb0d92917d6fee90771407f56174423b9b28e5c3c
```

### Authentication
Use the `x-api-key` header:
```python
headers = {
    "x-api-key": "your-api-key-here"
}
```

## Available Endpoints

### 1. Get API Usage
**Endpoint**: `GET /get_api_usage`

Returns current usage metrics for the API key.

**No parameters required**

**Returns**: Remaining credits, usage counters

---

### 2. Get Trades
**Endpoint**: `GET /get_trades`

Returns trades for a given user, enriched with market metadata.

**Required Parameters**:
- `user_address`: Wallet address

**Optional Parameters**:
- `asset_id`: Filter by market token ID
- `timestamp_gte`: Start time (ISO format)
- `timestamp_lte`: End time (ISO format)
- `format`: Output format (`json` or `csv`)
- `page`: Page number
- `page_size`: Results per page (max 1000)

**Returns**: Trades with market metadata

---

### 3. Get Positions
**Endpoint**: `GET /get_positions`

Returns current positions for a given user, enriched with market metadata.

**Required Parameters**:
- `user_address`: Wallet address

**Optional Parameters**:
- `asset_id`: Filter by token ID
- `format`: Output format (`json` or `csv`)
- `page`: Page number
- `page_size`: Results per page (max 1000)

**Returns**: Current positions including amount, avgPrice, realizedPnl, etc.

**Note**: Position data for inactive users is archived periodically.

---

### 4. Get Last Price
**Endpoint**: `GET /get_last_price`

Returns the last price for a given asset.

**Required Parameters**:
- `asset_id`: Token ID

**Returns**: Last price, source (resolved/last_trade), and market metadata

---

### 5. Get OHLCV
**Endpoint**: `GET /get_ohlcv`

Returns OHLCV bars (Open, High, Low, Close, Volume) plus number of trades and total volume for a token over a given time resolution.

**Required Parameters**:
- `asset_id`: Token ID
- `resolution`: Time resolution (`1m`, `5m`, `15m`, `1h`, `4h`, `1d`)

**Optional Parameters**:
- `timestamp_gte`: Time range start (ISO format)
- `timestamp_lte`: Time range end (ISO format)
- `format`: Output format (`json` or `csv`)
- `page`: Page number
- `page_size`: Results per page (max 1000)

**Returns**: Aggregated OHLCV data sorted by timestamp

---

### 6. Search Markets
**Endpoint**: `GET /search_markets`

Search markets by question name and retrieve the associated `asset_id`.

**Required Parameters**:
- `query`: Free-text search string

**Optional Parameters**:
- `format`: Output format (`json` or `csv`)
- `page`: Page number
- `page_size`: Results per page (max 1000)

**Returns**: List of matching markets with metadata and outcome options

---

### 7. Get Latest Whale Trades
**Endpoint**: `GET /get_latest_whale_trades`

Returns recent trades above a certain USD threshold, enriched with metadata.

**Optional Parameters**:
- `min_usd`: Minimum USD value for trade (default: 10000)
- `limit`: Maximum number of trades to return (default: 100, max: 1000)
- `format`: Output format (`json` or `csv`)

**Returns**: Recent whale trades enriched with metadata

## Usage Example

```python
from hashdive_client import HashDiveClient

# Initialize client
API_KEY = "2fcbbb010f3ff15f84dc47ebb0d92917d6fee90771407f56174423b9b28e5c3c"
client = HashDiveClient(API_KEY)

# Check API usage
usage = client.get_api_usage()
print(f"Remaining credits: {usage['remaining_credits']}")

# Search for markets
markets = client.search_markets("election", page_size=10)
for market in markets['results']:
    print(f"Market: {market['question']}")

# Get whale trades
whale_trades = client.get_latest_whale_trades(min_usd=10000, limit=20)
print(f"Found {len(whale_trades['results'])} whale trades")

# Get trades for a specific wallet
wallet = "0x56687bf447db6ffa42ffe2204a05edaa20f55839"
trades = client.get_trades(user_address=wallet, page_size=50)
print(f"Found {len(trades['results'])} trades")
```

## API Limits

- **Current Status**: Beta
- **Monthly Credits**: 1000 (for PRO users)
- **Credit Cost**: 1 credit per API request
- **Data Update Frequency**: Every minute
- **Max Page Size**: 1000

**Note**: The API is currently in beta. Credit limits and access tiers may evolve over time.

## Current Issues

### Problem
The API is returning **502 Bad Gateway** errors, indicating that:
- Cloudflare is accessible
- The backend API server is not responding

### Possible Causes
1. **Temporary downtime**: API server may be temporarily unavailable
2. **IP whitelist**: Your IP address may need to be whitelisted
3. **API key issues**: The API key may need activation or verification
4. **Rate limiting**: Too many requests (unlikely for initial test)

### Solution Steps

1. **Contact HashDive Support**
   - Email: contact@hashdive.com
   - Provide your API key for verification
   - Ask about:
     - API availability status
     - IP whitelist requirements
     - When the API will be back online

2. **Check API Status**
   - Visit: https://hashdive.com/API_documentation
   - Look for status updates or announcements

3. **Retry Later**
   - 502 errors are often temporary
   - Wait a few hours and try again

## Files Created

- **`hashdive_client.py`**: Complete API client implementation
- **`test_hashdive_correct.py`**: Test script for API endpoints
- **`test_hashdive_api_detailed.py`**: Detailed API testing (cleanup)

## Next Steps

When the API becomes available:

1. Test the client:
   ```bash
   python3 hashdive_client.py
   ```

2. Integrate with your monitoring system:
   - Use `get_trades()` to track wallet activity
   - Use `search_markets()` to find relevant markets
   - Use `get_latest_whale_trades()` to monitor large trades

3. Monitor API usage:
   ```python
   usage = client.get_api_usage()
   print(f"Credits remaining: {usage['remaining_credits']}")
   ```

## Resources

- **API Documentation**: https://hashdive.com/API_documentation
- **Support Email**: contact@hashdive.com
- **Main Website**: https://hashdive.com

