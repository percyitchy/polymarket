#!/bin/bash
# Daily wallet collection and maintenance script
# 1. Collects new wallets from HashDive whales and leaderboards
# 2. Rechecks all wallets and removes those below 75% win rate

cd /Users/johnbravo/polymarket

# Log file
LOG_FILE="wallet_collection.log"
echo "========================================" >> "$LOG_FILE"
echo "$(date): Starting daily wallet maintenance..." >> "$LOG_FILE"

# Step 1: Recheck all wallets and remove underperformers (below 75% WR)
echo "$(date): Rechecking wallet win rates (removing <75%)..." >> "$LOG_FILE"
python3 maintain_wallets.py >> "$LOG_FILE" 2>&1

# Step 2: Find whales via HashDive
echo "$(date): Finding whale wallets via HashDive..." >> "$LOG_FILE"
python3 hashdive_whale_finder.py 5000 100 >> "$LOG_FILE" 2>&1

# Step 3: Wait a bit for queue processing
sleep 5

# Step 4: Check final count
echo "$(date): Checking final wallet count..." >> "$LOG_FILE"
CURRENT_COUNT=$(python3 -c "import sqlite3; conn = sqlite3.connect('polymarket_notifier.db'); c = conn.cursor(); c.execute('SELECT COUNT(*) FROM wallets WHERE win_rate >= 0.75'); print(c.fetchone()[0]); conn.close()")

echo "$(date): Final wallets (≥75% WR): $CURRENT_COUNT" >> "$LOG_FILE"
echo "$(date): Daily maintenance complete." >> "$LOG_FILE"

