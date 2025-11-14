import os
import sqlite3

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

DB = os.getenv("DB_PATH", "polymarket_notifier.db")
print("DB:", DB)
con = sqlite3.connect(DB)
cur = con.cursor()
cur.execute('SELECT name FROM sqlite_master WHERE type="table" ORDER BY 1')
tables = [r[0] for r in cur.fetchall()]
print("tables:", tables)
res = {}
for name, sql in [
    ("wallets_total", "SELECT COUNT(*) FROM wallets"),
    ("wallets_tracked", "SELECT COUNT(*) FROM wallets WHERE tracked=1"),
    ("tracked_wallets", "SELECT COUNT(*) FROM tracked_wallets"),
]:
    try:
        cur.execute(sql)
        res[name] = cur.fetchone()[0]
    except Exception as e:
        res[name] = str(e)
print(res)
