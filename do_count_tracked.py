import os
import sys
sys.path.append('.')
from db import PolymarketDB

def load_env(path: str) -> dict:
    env = {}
    try:
        with open(path, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                k, v = line.split('=', 1)
                # strip inline comments
                if '#' in v:
                    v = v.split('#', 1)[0]
                env[k.strip()] = v.strip()
    except FileNotFoundError:
        pass
    return env

env = load_env('.env')
max_wallets = int(env.get('MAX_WALLETS', '2000'))
max_predictions = int(env.get('MAX_PREDICTIONS', '1000'))
db_path = env.get('DB_PATH', 'polymarket_notifier.db')

print('Using DB:', db_path)
print('MAX_WALLETS:', max_wallets, 'MAX_PREDICTIONS:', max_predictions)

db = PolymarketDB(db_path)
wallets = db.get_tracked_wallets(
    min_trades=6,
    max_trades=max_predictions,
    min_win_rate=0.75,
    max_win_rate=1.0,
    max_daily_freq=20.0,
    limit=max_wallets,
)
print('tracked_wallets_count:', len(wallets))
