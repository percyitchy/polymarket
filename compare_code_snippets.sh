#!/bin/bash
# Extract and display specific code snippets from modified files
# This helps verify key changes are present without comparing entire files
# Can be run both locally and on remote server
# Uses symbol-based extraction (function names) instead of line numbers for robustness

set -e

# Project root directory (can be overridden)
PROJECT_ROOT="${1:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"
cd "$PROJECT_ROOT"

echo "=========================================="
echo "Code Snippet Verification"
echo "=========================================="
echo "Project directory: $PROJECT_ROOT"
echo ""

# Function to extract code snippet by symbol (function/class name)
# Searches for the symbol and extracts surrounding lines
extract_snippet_by_symbol() {
    local file="$1"
    local symbol="$2"
    local context_before="${3:-5}"
    local context_after="${4:-30}"
    local description="$5"
    
    if [ ! -f "$file" ]; then
        echo "❌ File not found: $file"
        return 1
    fi
    
    # Find line number of symbol (function/class definition)
    local line_num=$(grep -n "^[[:space:]]*def ${symbol}\|^[[:space:]]*class ${symbol}\|^def ${symbol}\|^class ${symbol}" "$file" | head -1 | cut -d: -f1)
    
    if [ -z "$line_num" ]; then
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "📄 $file"
        echo "   $description"
        echo "   ⚠️  Symbol '${symbol}' not found"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo ""
        return 1
    fi
    
    local start_line=$((line_num - context_before))
    local end_line=$((line_num + context_after))
    
    # Ensure start_line is at least 1
    if [ $start_line -lt 1 ]; then
        start_line=1
    fi
    
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "📄 $file"
    echo "   $description"
    echo "   Symbol: ${symbol} (found at line $line_num, showing lines $start_line-$end_line)"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    sed -n "${start_line},${end_line}p" "$file" | cat -n | sed "s/^[[:space:]]*/   /"
    
    echo ""
}

# Function to extract snippet by pattern match (for non-function symbols)
extract_snippet_by_pattern() {
    local file="$1"
    local pattern="$2"
    local context_before="${3:-3}"
    local context_after="${4:-10}"
    local description="$5"
    
    if [ ! -f "$file" ]; then
        echo "❌ File not found: $file"
        return 1
    fi
    
    # Find line number of pattern
    local line_num=$(grep -n "$pattern" "$file" | head -1 | cut -d: -f1)
    
    if [ -z "$line_num" ]; then
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "📄 $file"
        echo "   $description"
        echo "   ⚠️  Pattern '${pattern}' not found"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo ""
        return 1
    fi
    
    local start_line=$((line_num - context_before))
    local end_line=$((line_num + context_after))
    
    if [ $start_line -lt 1 ]; then
        start_line=1
    fi
    
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "📄 $file"
    echo "   $description"
    echo "   Pattern: ${pattern} (found at line $line_num, showing lines $start_line-$end_line)"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    sed -n "${start_line},${end_line}p" "$file" | cat -n | sed "s/^[[:space:]]*/   /"
    
    echo ""
}

# 1. _mask_proxy_url() function from utils/http_client.py
extract_snippet_by_symbol "utils/http_client.py" "_mask_proxy_url" 5 50 "_mask_proxy_url() function - Security fix for masking proxy credentials"

# 2. verify parameter default from http_get() function
extract_snippet_by_pattern "utils/http_client.py" "def http_get" 3 10 "verify parameter default - TLS verification enabled by default"

# 3. normalize_timestamp() function from bet_monitor.py
extract_snippet_by_symbol "bet_monitor.py" "normalize_timestamp" 5 30 "normalize_timestamp() function - Correctness fix for timestamp handling"

# 4. MatchingBet dataclass with side field
extract_snippet_by_pattern "bet_monitor.py" "class MatchingBet" 3 15 "MatchingBet dataclass with side field - Correctness fix"

# 5. Retry logic in send_message() method
extract_snippet_by_pattern "bet_monitor.py" "async def send_message" 3 60 "send_message() retry logic - Performance improvement for Telegram rate limiting"

# 6. Configuration constants from price_fetcher.py
extract_snippet_by_pattern "price_fetcher.py" "REQUEST_TIMEOUT\|MAX_RETRIES\|OVERALL_TIME_BUDGET" 3 8 "Configuration constants - Retry logic and time budget"

echo "=========================================="
echo "✅ Code snippet verification complete"
echo "=========================================="
echo ""
echo "Verify that:"
echo "1. _mask_proxy_url() function exists and masks credentials"
echo "2. verify=True is the default parameter"
echo "3. normalize_timestamp() handles milliseconds correctly"
echo "4. MatchingBet has 'side' field"
echo "5. send_message() has retry logic for 429 errors"
echo "6. price_fetcher.py has retry/timeout configuration"

