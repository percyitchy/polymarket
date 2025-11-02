import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "polymarket_notifier.db"
OUT_PATH = Path(__file__).parent / "wallets_export.xls"  # HTML table opened by Excel


def prune_wallets():
    """Remove wallets that do not meet current tracking criteria."""
    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()
    # Delete wallets with >1000 trades or not meeting quality thresholds
    cur.execute(
        """
        DELETE FROM wallets
        WHERE traded_total > 1000
           OR traded_total < 6
           OR win_rate < 0.75 OR win_rate > 1.0
           OR daily_trading_frequency > 20.0
        """
    )
    removed = cur.rowcount
    conn.commit()
    conn.close()
    return removed


def fetch_wallets():
    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()
    cur.execute(
        """
        SELECT address, traded_total, win_rate, realized_pnl_total
        FROM wallets
        WHERE traded_total <= 1000
        ORDER BY realized_pnl_total DESC, traded_total DESC
        """
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def to_html_table(rows):
    # Excel-compatible HTML table
    header = (
        "<tr>"
        "<th>Address</th>"
        "<th>Total Trades</th>"
        "<th>Winrate %</th>"
        "<th>Total Realized PnL</th>"
        "</tr>"
    )

    body_parts = []
    for address, traded_total, win_rate, realized_pnl_total in rows:
        # Format values
        total_trades = traded_total or 0
        winrate_pct = (win_rate or 0.0) * 100.0
        pnl = realized_pnl_total or 0.0
        short_addr = f"{address[:8]}...{address[-4:]}" if address else ""

        body_parts.append(
            "<tr>"
            f"<td>{address}</td>"
            f"<td>{total_trades}</td>"
            f"<td>{winrate_pct:.1f}</td>"
            f"<td>{pnl:.2f}</td>"
            "</tr>"
        )

    body = "\n".join(body_parts)
    html = (
        "<html>\n<head>\n<meta charset=\"UTF-8\">\n</head>\n<body>\n"
        "<table border=\"1\" cellspacing=\"0\" cellpadding=\"4\">\n"
        f"{header}\n{body}\n"
        "</table>\n</body>\n</html>\n"
    )
    return html


def main():
    # Prune DB according to current tracking rules (daily maintenance)
    try:
        removed = prune_wallets()
        if removed:
            print(f"Pruned {removed} wallets not meeting criteria")
    except Exception:
        pass

    rows = fetch_wallets()
    html = to_html_table(rows)
    OUT_PATH.write_text(html, encoding="utf-8")
    print(str(OUT_PATH))


if __name__ == "__main__":
    main()


