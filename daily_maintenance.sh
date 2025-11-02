#!/bin/bash
# Daily wallet maintenance

cd /Users/johnbravo/polymarket
python3 maintain_wallets.py >> maintenance.log 2>&1

