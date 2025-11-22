"""
SQLite Database Helper Functions for Polymarket Notifier
Handles all database operations for wallets, trades, and alerts
"""

import sqlite3
import json
import hashlib
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional, Tuple, Any
from contextlib import contextmanager

logger = logging.getLogger(__name__)

class PolymarketDB:
    def __init__(self, db_path: str = "polymarket_notifier.db"):
        self.db_path = db_path
        # Log absolute path to ensure we're using the correct database
        import os
        abs_path = os.path.abspath(self.db_path)
        logger.info(f"Database initialized with path: {abs_path} (relative: {db_path})")
        self._init_database()
    
    def _init_database(self):
        """Initialize database tables if they don't exist"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Enable WAL mode for better concurrency
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA cache_size=10000")
            cursor.execute("PRAGMA temp_store=MEMORY")
            
            # Wallets table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS wallets(
                    address TEXT PRIMARY KEY,
                    display TEXT,
                    traded_total INTEGER,
                    win_rate REAL,
                    realized_pnl_total REAL,
                    daily_trading_frequency REAL,
                    source TEXT,
                    added_at TEXT,
                    updated_at TEXT
                )
            """)
            
            # Add insider detection columns if they don't exist
            for alter in (
                "ALTER TABLE wallets ADD COLUMN total_markets_traded INTEGER",
                "ALTER TABLE wallets ADD COLUMN is_insider_candidate BOOLEAN DEFAULT 0",
                "ALTER TABLE wallets ADD COLUMN insider_detection_reason TEXT",
                "ALTER TABLE wallets ADD COLUMN insider_detected_at TEXT",
            ):
                try:
                    cursor.execute(alter)
                except sqlite3.OperationalError:
                    pass
            
            # Add quality metrics columns if they don't exist (for strict filtering criteria)
            for alter in (
                "ALTER TABLE wallets ADD COLUMN total_volume REAL",
                "ALTER TABLE wallets ADD COLUMN roi REAL",
                "ALTER TABLE wallets ADD COLUMN avg_pnl_per_market REAL",
                "ALTER TABLE wallets ADD COLUMN avg_stake REAL",
            ):
                try:
                    cursor.execute(alter)
                except sqlite3.OperationalError:
                    pass
            
            # Last trades tracking
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS last_trades(
                    address TEXT PRIMARY KEY,
                    last_seen_trade_id TEXT,
                    updated_at TEXT
                )
            """)
            
            # Alerts sent (for deduplication)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS alerts_sent(
                    alert_key TEXT PRIMARY KEY,
                    sent_at TEXT,
                    condition_id TEXT,
                    outcome_index INTEGER,
                    wallet_count INTEGER,
                    side TEXT,
                    price REAL,
                    wallets_csv TEXT
                )
            """)
            
            # Add new columns if they don't exist (for existing databases)
            for alter in (
                "ALTER TABLE alerts_sent ADD COLUMN condition_id TEXT",
                "ALTER TABLE alerts_sent ADD COLUMN outcome_index INTEGER",
                "ALTER TABLE alerts_sent ADD COLUMN wallet_count INTEGER",
                "ALTER TABLE alerts_sent ADD COLUMN side TEXT",
                "ALTER TABLE alerts_sent ADD COLUMN price REAL",
                "ALTER TABLE alerts_sent ADD COLUMN wallets_csv TEXT",
                "ALTER TABLE alerts_sent ADD COLUMN wallet_details_json TEXT",
                "ALTER TABLE alerts_sent ADD COLUMN first_total_usd REAL",
                "ALTER TABLE wallets ADD COLUMN last_trade_at TEXT",
                "ALTER TABLE wallets ADD COLUMN source TEXT",  # Ensure source column exists
            ):
                try:
                    cursor.execute(alter)
                except sqlite3.OperationalError:
                    pass
            
            # Rolling buys window
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS rolling_buys(
                    k TEXT PRIMARY KEY,
                    data TEXT,
                    updated_at TEXT
                )
            """)
            
            # Track first entry per wallet per market direction
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS market_trades(
                    wallet TEXT,
                    condition_id TEXT,
                    side TEXT,
                    first_trade_id TEXT,
                    first_ts REAL,
                    PRIMARY KEY (wallet, condition_id, side)
                )
            """)
            
            # Wallet analysis jobs queue
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS wallet_analysis_jobs(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    address TEXT NOT NULL,
                    display TEXT,
                    source TEXT,
                    status TEXT DEFAULT 'pending',
                    retry_count INTEGER DEFAULT 0,
                    max_retries INTEGER DEFAULT 6,
                    next_retry_at TEXT,
                    created_at TEXT,
                    updated_at TEXT,
                    error_message TEXT,
                    UNIQUE(address)
                )
            """)
            
            # Wallet analysis cache - stores analysis results to avoid re-analyzing
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS wallet_analysis_cache(
                    address TEXT PRIMARY KEY,
                    traded_total INTEGER,
                    win_rate REAL,
                    realized_pnl_total REAL,
                    daily_trading_frequency REAL,
                    analysis_result TEXT,
                    analyzed_at TEXT,
                    expires_at TEXT,
                    last_trade_at TEXT,
                    source TEXT
                )
            """)
            
            # Wallet category statistics - stores per-category metrics for each wallet
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS wallet_category_stats(
                    wallet_address TEXT NOT NULL,
                    category TEXT NOT NULL,
                    markets INTEGER DEFAULT 0,
                    volume REAL DEFAULT 0.0,
                    pnl REAL DEFAULT 0.0,
                    winrate REAL DEFAULT 0.0,
                    roi REAL DEFAULT 0.0,
                    avg_pnl REAL DEFAULT 0.0,
                    is_a_list_trader BOOLEAN DEFAULT 0,
                    updated_at TEXT,
                    PRIMARY KEY (wallet_address, category)
                )
            """)
            
            # Raw collected wallets - tracks all wallets collected from different sources
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS raw_collected_wallets(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    address TEXT NOT NULL,
                    source TEXT NOT NULL,
                    collected_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Add new columns if they don't exist (for existing databases)
            for alter in (
                "ALTER TABLE wallet_analysis_cache ADD COLUMN last_trade_at TEXT",
                "ALTER TABLE wallet_analysis_cache ADD COLUMN source TEXT",
                "ALTER TABLE wallet_analysis_cache ADD COLUMN created_at TEXT",  # For legacy cleanup operations
                "ALTER TABLE wallet_analysis_cache ADD COLUMN is_insider_candidate BOOLEAN DEFAULT 0",
                "ALTER TABLE wallet_analysis_cache ADD COLUMN insider_detection_reason TEXT",
                "ALTER TABLE wallet_analysis_cache ADD COLUMN total_markets_traded INTEGER",
            ):
                try:
                    cursor.execute(alter)
                except sqlite3.OperationalError:
                    pass
            
            # Backfill created_at for existing records (use analyzed_at if created_at is NULL)
            try:
                cursor.execute("""
                    UPDATE wallet_analysis_cache 
                    SET created_at = analyzed_at 
                    WHERE created_at IS NULL AND analyzed_at IS NOT NULL
                """)
            except sqlite3.OperationalError:
                pass  # Column might not exist yet
            
            # Create indexes for better performance
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_wallets_traded ON wallets(traded_total)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_wallets_winrate ON wallets(win_rate)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_wallets_pnl ON wallets(realized_pnl_total)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_alerts_condition ON alerts_sent(condition_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_alerts_sent_at ON alerts_sent(sent_at)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status ON wallet_analysis_jobs(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_next_retry ON wallet_analysis_jobs(next_retry_at)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_address ON wallet_analysis_jobs(address)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_cache_address ON wallet_analysis_cache(address)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_cache_expires ON wallet_analysis_cache(expires_at)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_raw_collected_address ON raw_collected_wallets(address)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_raw_collected_source ON raw_collected_wallets(source)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_raw_collected_at ON raw_collected_wallets(collected_at)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_category_wallet ON wallet_category_stats(wallet_address)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_category_category ON wallet_category_stats(category)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_category_a_list ON wallet_category_stats(is_a_list_trader)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_wallets_insider ON wallets(is_insider_candidate, insider_detected_at)")
            
            # Open interest history table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS open_interest_history(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    condition_id TEXT NOT NULL,
                    open_interest REAL,
                    timestamp TEXT,
                    created_at TEXT
                )
            """)
            
            # Whale positions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS whale_positions(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_address TEXT NOT NULL,
                    condition_id TEXT NOT NULL,
                    outcome_index INTEGER,
                    position_size_usd REAL,
                    position_type TEXT,
                    detected_at TEXT,
                    alerted BOOLEAN DEFAULT 0
                )
            """)
            
            # Create indexes for open interest history
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_oi_condition_timestamp ON open_interest_history(condition_id, timestamp)")
            
            # Create indexes for whale positions
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_whale_user_condition ON whale_positions(user_address, condition_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_whale_alerted_detected ON whale_positions(alerted, detected_at)")
            
            # Order flow metrics table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS order_flow_metrics(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    condition_id TEXT NOT NULL,
                    outcome_index INTEGER,
                    window_start TEXT,
                    window_end TEXT,
                    buy_count INTEGER DEFAULT 0,
                    sell_count INTEGER DEFAULT 0,
                    buy_volume REAL DEFAULT 0.0,
                    sell_volume REAL DEFAULT 0.0,
                    buy_sell_ratio REAL,
                    is_imbalanced BOOLEAN DEFAULT 0,
                    imbalance_direction TEXT,
                    detected_at TEXT,
                    alerted BOOLEAN DEFAULT 0
                )
            """)
            
            # Create indexes for order flow metrics
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_order_flow_condition_window ON order_flow_metrics(condition_id, window_end)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_order_flow_alerted_detected ON order_flow_metrics(alerted, detected_at)")
            
            conn.commit()
            logger.info("Database initialized successfully")
    
    @contextmanager
    def get_connection(self):
        """Context manager for database connections with improved concurrency settings"""
        conn = sqlite3.connect(
            self.db_path, 
            check_same_thread=False,
            timeout=5.0  # Wait up to 5 seconds for lock
        )
        conn.row_factory = sqlite3.Row  # Enable dict-like access
        
        # Set pragmas for better concurrency
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")  # Wait 5 seconds on lock
        
        try:
            yield conn
        finally:
            conn.close()
    
    def now_iso(self) -> str:
        """Get current UTC timestamp in ISO format"""
        return datetime.now(timezone.utc).isoformat()
    
    def sha(self, s: str) -> str:
        """Generate SHA256 hash of string"""
        return hashlib.sha256(s.encode("utf-8")).hexdigest()
    
    # Wallet operations
    def upsert_wallet(self, address: str, display: str, traded: int, win_rate: float, 
                     pnl_total: float, daily_freq: float, source: str, last_trade_at: Optional[str] = None,
                     total_markets_traded: Optional[int] = None, is_insider_candidate: Optional[bool] = None,
                     insider_detection_reason: Optional[str] = None,
                     total_volume: Optional[float] = None, roi: Optional[float] = None,
                     avg_pnl_per_market: Optional[float] = None, avg_stake: Optional[float] = None) -> bool:
        """Insert or update wallet information"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                now = self.now_iso()
                
                # Build dynamic UPDATE clause for insider fields
                update_fields = [
                    "display=excluded.display",
                    "traded_total=excluded.traded_total",
                    "win_rate=excluded.win_rate",
                    "realized_pnl_total=excluded.realized_pnl_total",
                    "daily_trading_frequency=excluded.daily_trading_frequency",
                    "source=excluded.source",
                    "updated_at=excluded.updated_at",
                    "last_trade_at=excluded.last_trade_at"
                ]
                
                # Add insider fields if provided
                if total_markets_traded is not None:
                    update_fields.append("total_markets_traded=excluded.total_markets_traded")
                if is_insider_candidate is not None:
                    update_fields.append("is_insider_candidate=excluded.is_insider_candidate")
                    if is_insider_candidate:
                        update_fields.append("insider_detection_reason=excluded.insider_detection_reason")
                        update_fields.append("insider_detected_at=excluded.insider_detected_at")
                    else:
                        update_fields.append("insider_detection_reason=NULL")
                        update_fields.append("insider_detected_at=NULL")
                
                # Add quality metrics fields if provided
                if total_volume is not None:
                    update_fields.append("total_volume=excluded.total_volume")
                if roi is not None:
                    update_fields.append("roi=excluded.roi")
                if avg_pnl_per_market is not None:
                    update_fields.append("avg_pnl_per_market=excluded.avg_pnl_per_market")
                if avg_stake is not None:
                    update_fields.append("avg_stake=excluded.avg_stake")
                
                update_clause = ", ".join(update_fields)
                
                # Build VALUES clause
                values = [
                    address.lower(), display, traded, win_rate, pnl_total, 
                    daily_freq, source, now, now, last_trade_at
                ]
                
                # Add insider fields to VALUES if provided
                if total_markets_traded is not None:
                    values.append(total_markets_traded)
                if is_insider_candidate is not None:
                    values.append(1 if is_insider_candidate else 0)
                    if is_insider_candidate:
                        values.append(insider_detection_reason)
                        values.append(now)
                    else:
                        values.append(None)
                        values.append(None)
                
                # Add quality metrics fields to VALUES if provided
                if total_volume is not None:
                    values.append(total_volume)
                if roi is not None:
                    values.append(roi)
                if avg_pnl_per_market is not None:
                    values.append(avg_pnl_per_market)
                if avg_stake is not None:
                    values.append(avg_stake)
                
                # Build INSERT clause
                insert_fields = [
                    "address", "display", "traded_total", "win_rate",
                    "realized_pnl_total", "daily_trading_frequency",
                    "source", "added_at", "updated_at", "last_trade_at"
                ]
                
                if total_markets_traded is not None:
                    insert_fields.append("total_markets_traded")
                if is_insider_candidate is not None:
                    insert_fields.append("is_insider_candidate")
                    if is_insider_candidate:
                        insert_fields.append("insider_detection_reason")
                        insert_fields.append("insider_detected_at")
                
                # Add quality metrics fields to INSERT if provided
                if total_volume is not None:
                    insert_fields.append("total_volume")
                if roi is not None:
                    insert_fields.append("roi")
                if avg_pnl_per_market is not None:
                    insert_fields.append("avg_pnl_per_market")
                if avg_stake is not None:
                    insert_fields.append("avg_stake")
                
                placeholders = ",".join(["?"] * len(values))
                insert_clause = ",".join(insert_fields)
                
                query = f"""
                    INSERT INTO wallets({insert_clause})
                    VALUES({placeholders})
                    ON CONFLICT(address) DO UPDATE SET
                        {update_clause}
                """
                
                cursor.execute(query, tuple(values))
                
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error upserting wallet {address}: {e}")
            return False
    
    def get_wallet(self, address: str) -> Optional[Dict[str, Any]]:
        """Get wallet information by address"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM wallets WHERE address = ?", (address.lower(),))
                row = cursor.fetchone()
                return dict(row) if row else None
        except Exception as e:
            logger.error(f"Error getting wallet {address}: {e}")
            return None
    
    def get_tracked_wallets(self, min_trades: int = 6, max_trades: int = 1500,
                          min_win_rate: float = 0.65, max_win_rate: float = 1.0,
                          max_daily_freq: float = 35.0, limit: int = 200,
                          use_strict_criteria: bool = True) -> List[str]:
        """Get wallets that meet tracking criteria.
        
        Activity filter logic (matching wallet_analyzer.py):
        - If last_trade_at IS NULL: include wallet (activity unknown, decide by other criteria)
        - If last_trade_at is not NULL: only include if last_trade_at >= 90 days ago
        
        If use_strict_criteria=True, applies all strict quality filters:
        - MINIMUM_MARKETS (12)
        - MINIMUM_VOLUME ($25,000)
        - MINIMUM_ROI (0.25%)
        - MINIMUM_AVG_PNL ($50)
        - MINIMUM_AVG_STAKE ($100)
        """
        try:
            # Import strict criteria constants
            from wallet_analyzer import (
                MINIMUM_MARKETS, MINIMUM_VOLUME, MINIMUM_ROI,
                MINIMUM_AVG_PNL, MINIMUM_AVG_STAKE
            )
            
            with self.get_connection() as conn:
                cursor = conn.cursor()
                # Calculate 3 months ago threshold
                three_months_ago = (datetime.now(timezone.utc) - timedelta(days=90)).isoformat()
                
                if use_strict_criteria:
                    # Use strict criteria - check all quality metrics
                    cursor.execute("""
                        SELECT address FROM wallets
                        WHERE traded_total >= ? AND traded_total <= ?
                        AND win_rate >= ? AND win_rate <= ?
                        AND (daily_trading_frequency IS NULL OR daily_trading_frequency <= ?)
                        AND (last_trade_at IS NULL OR last_trade_at >= ?)
                        AND (total_markets_traded IS NULL OR total_markets_traded >= ?)
                        AND (total_volume IS NULL OR total_volume >= ?)
                        AND (roi IS NULL OR roi >= ?)
                        AND (avg_pnl_per_market IS NULL OR avg_pnl_per_market >= ?)
                        AND (avg_stake IS NULL OR avg_stake >= ?)
                        ORDER BY realized_pnl_total DESC, traded_total DESC
                        LIMIT ?
                    """, (min_trades, max_trades, min_win_rate, max_win_rate, 
                         max_daily_freq, three_months_ago,
                         MINIMUM_MARKETS, MINIMUM_VOLUME, MINIMUM_ROI,
                         MINIMUM_AVG_PNL, MINIMUM_AVG_STAKE, limit))
                else:
                    # Use relaxed criteria (for new wallets without data)
                    cursor.execute("""
                        SELECT address FROM wallets
                        WHERE traded_total >= ? AND traded_total <= ?
                        AND win_rate >= ? AND win_rate <= ?
                        AND (daily_trading_frequency IS NULL OR daily_trading_frequency <= ?)
                        AND (last_trade_at IS NULL OR last_trade_at >= ?)
                        ORDER BY realized_pnl_total DESC, traded_total DESC
                        LIMIT ?
                    """, (min_trades, max_trades, min_win_rate, max_win_rate, 
                         max_daily_freq, three_months_ago, limit))
                
                return [row[0] for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error getting tracked wallets: {e}")
            return []
    
    def get_wallet_stats(self) -> Dict[str, int]:
        """Get database statistics"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                stats = {}
                
                # Total wallets
                cursor.execute("SELECT COUNT(*) FROM wallets")
                stats['total_wallets'] = cursor.fetchone()[0]
                
                # Wallets meeting STRICT tracking criteria (for statistics display)
                # This matches get_tracked_wallets() with use_strict_criteria=True
                # Import strict criteria constants
                from wallet_analyzer import (
                    MIN_TRADES, WIN_RATE_THRESHOLD, MAX_DAILY_FREQUENCY,
                    MINIMUM_MARKETS, MINIMUM_VOLUME, MINIMUM_ROI,
                    MINIMUM_AVG_PNL, MINIMUM_AVG_STAKE
                )
                
                three_months_ago = (datetime.now(timezone.utc) - timedelta(days=90)).isoformat()
                # Use STRICT filtering criteria: all quality metrics checked
                cursor.execute("""
                    SELECT COUNT(*) FROM wallets
                    WHERE traded_total >= ? AND traded_total <= 1500
                    AND win_rate >= ? AND win_rate <= 1.0
                    AND (daily_trading_frequency IS NULL OR daily_trading_frequency <= ?)
                    AND (last_trade_at IS NULL OR last_trade_at >= ?)
                    AND (total_markets_traded IS NULL OR total_markets_traded >= ?)
                    AND (total_volume IS NULL OR total_volume >= ?)
                    AND (roi IS NULL OR roi >= ?)
                    AND (avg_pnl_per_market IS NULL OR avg_pnl_per_market >= ?)
                    AND (avg_stake IS NULL OR avg_stake >= ?)
                """, (MIN_TRADES, WIN_RATE_THRESHOLD, MAX_DAILY_FREQUENCY, three_months_ago,
                     MINIMUM_MARKETS, MINIMUM_VOLUME, MINIMUM_ROI,
                     MINIMUM_AVG_PNL, MINIMUM_AVG_STAKE))
                stats['tracked_wallets'] = cursor.fetchone()[0]
                
                # Win rate distribution
                cursor.execute("""
                    SELECT 
                        COUNT(CASE WHEN win_rate >= 0.8 THEN 1 END) as high_winrate,
                        COUNT(CASE WHEN win_rate >= 0.7 AND win_rate < 0.8 THEN 1 END) as medium_winrate,
                        COUNT(CASE WHEN win_rate < 0.7 THEN 1 END) as low_winrate
                    FROM wallets
                """)
                row = cursor.fetchone()
                stats['high_winrate'] = row[0]
                stats['medium_winrate'] = row[1]
                stats['low_winrate'] = row[2]
                
                return stats
        except Exception as e:
            logger.error(f"Error getting wallet stats: {e}")
            return {}
    
    def cleanup_old_wallets(self, max_trades: int = 1500, max_wallets: int = 200):
        """Remove wallets that exceed limits"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Remove wallets with too many trades
                cursor.execute("DELETE FROM wallets WHERE traded_total > ?", (max_trades,))
                removed_trades = cursor.rowcount
                
                # Keep only top wallets by PnL
                cursor.execute("""
                    DELETE FROM wallets WHERE address NOT IN (
                        SELECT address FROM wallets
                        WHERE traded_total >= 30 AND traded_total <= ?
                        AND win_rate > 0.65 AND win_rate < 0.99
                        AND (daily_trading_frequency IS NULL OR daily_trading_frequency <= 35.0)
                        ORDER BY realized_pnl_total DESC, traded_total DESC
                        LIMIT ?
                    )
                """, (max_trades, max_wallets))
                removed_limit = cursor.rowcount
                
                conn.commit()
                
                if removed_trades > 0 or removed_limit > 0:
                    logger.info(f"Cleaned up {removed_trades + removed_limit} wallets")
                    
        except Exception as e:
            logger.error(f"Error cleaning up wallets: {e}")
    
    # Trade tracking operations
    def get_last_seen_trade_id(self, address: str) -> Optional[str]:
        """Get last seen trade ID for wallet"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT last_seen_trade_id FROM last_trades WHERE address = ?", 
                             (address.lower(),))
                row = cursor.fetchone()
                return row[0] if row and row[0] else None
        except Exception as e:
            logger.error(f"Error getting last trade ID for {address}: {e}")
            return None
    
    def set_last_seen_trade_id(self, address: str, trade_id: str) -> bool:
        """Set last seen trade ID for wallet"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                now = self.now_iso()
                
                cursor.execute("""
                    INSERT INTO last_trades(address, last_seen_trade_id, updated_at)
                    VALUES(?,?,?)
                    ON CONFLICT(address) DO UPDATE SET
                        last_seen_trade_id=excluded.last_seen_trade_id,
                        updated_at=excluded.updated_at
                """, (address.lower(), trade_id, now))
                
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error setting last trade ID for {address}: {e}")
            return False
    
    # Rolling window operations
    def update_rolling_window(self, condition_id: str, outcome_index: int, 
                            wallet: str, trade_id: str, timestamp: float,
                            window_minutes: float = 10.0, market_title: str = "", 
                            market_slug: str = "", price: float = 0, side: str = "BUY",
                            usd_amount: float = 0.0, quantity: float = 0.0) -> Tuple[str, Dict[str, Any]]:
        """Update rolling window for consensus detection grouped by side"""
        try:
            # Group by side (direction)
            key = self.sha(f"{condition_id}:{outcome_index}:{side}")
            window_start = timestamp - (window_minutes * 60)
            entry = {
                "wallet": wallet, 
                "trade_id": trade_id, 
                "ts": timestamp, 
                "price": price,
                "conditionId": condition_id,  # Сохраняем condition_id
                "outcomeIndex": outcome_index,  # Сохраняем outcome_index
                "side": side  # Сохраняем side
            }
            if market_title:
                entry["marketTitle"] = market_title
            if market_slug:
                entry["marketSlug"] = market_slug
            # Store USD amount and quantity for position size calculation
            if usd_amount and usd_amount > 0:
                entry["usd"] = float(usd_amount)
            if quantity and quantity > 0:
                entry["quantity"] = float(quantity)
            
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT data FROM rolling_buys WHERE k = ?", (key,))
                row = cursor.fetchone()
                
                if not row:
                    obj = {"events": [entry], "first_ts": timestamp, "last_ts": timestamp}
                else:
                    obj = json.loads(row[0])
                    # Add new event first
                    obj["events"].append(entry)
                    # Deduplicate wallets (keep latest per wallet) before filtering
                    obj["events"] = self._dedupe_wallets(obj["events"])
                    
                    # CRITICAL FIX: Filter events based on the LATEST event timestamp, not the new event
                    # This ensures the window is calculated from the most recent event in the window
                    if obj["events"]:
                        latest_ts = max(e["ts"] for e in obj["events"])
                        window_start_ts = latest_ts - (window_minutes * 60)
                        # Remove stale events (events outside the window from the latest event)
                        obj["events"] = [e for e in obj["events"] if e["ts"] >= window_start_ts]
                    
                    # Update timestamps
                    if obj["events"]:
                        obj["first_ts"] = min(e["ts"] for e in obj["events"])
                        obj["last_ts"] = max(e["ts"] for e in obj["events"])
                
                updated_at_iso = self.now_iso()
                data_json = json.dumps(obj)
                cursor.execute("""
                    INSERT INTO rolling_buys(k, data, updated_at)
                    VALUES(?,?,?)
                    ON CONFLICT(k) DO UPDATE SET 
                        data=excluded.data, 
                        updated_at=excluded.updated_at
                """, (key, data_json, updated_at_iso))
                
                try:
                    conn.commit()
                    # Verify the commit worked by checking if row exists
                    cursor.execute("SELECT updated_at FROM rolling_buys WHERE k = ?", (key,))
                    verify_row = cursor.fetchone()
                    events_count = len(obj.get('events', []))
                    wallets_count = len({e.get('wallet') for e in obj.get('events', [])})
                    if verify_row:
                        logger.info(f"[DB] ✅ Updated rolling_buys: key={key[:20]}... updated_at={updated_at_iso} events={events_count} wallets={wallets_count} VERIFIED")
                    else:
                        logger.error(f"[DB] ❌ Commit failed - row not found after commit: key={key[:20]}...")
                except Exception as commit_error:
                    logger.error(f"[DB] ❌ Commit error: {commit_error} for key={key[:20]}...")
                    conn.rollback()
                    raise
                return key, obj
                
        except Exception as e:
            logger.error(f"Error updating rolling window: {e}")
            return "", {}
    
    def _dedupe_wallets(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Keep latest event per wallet"""
        by_wallet = {}
        for e in events:
            w = e["wallet"]
            if w not in by_wallet or e["ts"] > by_wallet[w]["ts"]:
                by_wallet[w] = e
        return list(by_wallet.values())
    
    # Alert operations
    def has_traded_market(self, wallet: str, condition_id: str, side: str) -> bool:
        """Check if wallet has already traded this market in this direction"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT 1 FROM market_trades 
                    WHERE wallet = ? AND condition_id = ? AND side = ?
                """, (wallet, condition_id, side))
                return cursor.fetchone() is not None
        except Exception as e:
            logger.error(f"Error checking market trade: {e}")
            return False
    
    def mark_market_traded(self, wallet: str, condition_id: str, side: str, timestamp: float):
        """Mark wallet as having traded this market in this direction"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO market_trades(wallet, condition_id, side, first_ts)
                    VALUES(?, ?, ?, ?)
                """, (wallet, condition_id, side, timestamp))
                conn.commit()
        except Exception as e:
            logger.error(f"Error marking market trade: {e}")
    
    def is_alert_sent(self, condition_id: str, outcome_index: int, 
                     first_ts: float, last_ts: float, alert_key: str = "") -> bool:
        """Check if alert was already sent for this consensus"""
        try:
            if alert_key:
                key = self.sha(f"ALERT:{alert_key}:{int(first_ts)}:{int(last_ts)}")
            else:
                key = self.sha(f"ALERT:{condition_id}:{outcome_index}:{int(first_ts)}:{int(last_ts)}")
            
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1 FROM alerts_sent WHERE alert_key = ?", (key,))
                return cursor.fetchone() is not None
                
        except Exception as e:
            logger.error(f"Error checking alert status: {e}")
            return False
    
    def is_suppressed_alert_sent(self, condition_id: str, outcome_index: int, 
                                 side: str, reason: str, 
                                 window_minutes: float = 30.0) -> bool:
        """
        Check if suppressed alert was already sent for this market/outcome/side/reason
        within the last window_minutes minutes
        
        Args:
            condition_id: Market condition ID
            outcome_index: Outcome index
            side: Trade side (BUY/SELL)
            reason: Suppression reason (e.g., "price_none", "market_closed")
            window_minutes: Time window in minutes to check for recent suppressed alerts
        
        Returns:
            True if suppressed alert was sent recently, False otherwise
        """
        try:
            from datetime import datetime, timezone, timedelta
            
            # Calculate time threshold
            threshold_time = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
            threshold_iso = threshold_time.isoformat()
            
            with self.get_connection() as conn:
                cursor = conn.cursor()
                # Check if there's a suppressed alert for this market/outcome/side/reason
                # in the last window_minutes minutes
                # We'll use a simple key based on condition_id, outcome_index, side, and reason
                suppressed_key = f"SUPPRESSED:{condition_id}:{outcome_index}:{side}:{reason}"
                
                # Check alerts_sent table for suppressed alerts
                # We'll look for alerts with a specific pattern in the alert_key
                cursor.execute("""
                    SELECT 1 FROM alerts_sent
                    WHERE condition_id = ? 
                    AND outcome_index = ?
                    AND sent_at >= ?
                    AND alert_key LIKE ?
                    LIMIT 1
                """, (condition_id, outcome_index, threshold_iso, f"%{suppressed_key}%"))
                
                return cursor.fetchone() is not None
                
        except Exception as e:
            logger.debug(f"Error checking suppressed alert status: {e}")
            return False
    
    def mark_suppressed_alert_sent(self, condition_id: str, outcome_index: int,
                                  side: str, reason: str, wallet_count: int = 0) -> bool:
        """
        Mark suppressed alert as sent
        
        Args:
            condition_id: Market condition ID
            outcome_index: Outcome index
            side: Trade side (BUY/SELL)
            reason: Suppression reason
            wallet_count: Number of wallets in consensus
        
        Returns:
            True if marked successfully, False otherwise
        """
        try:
            suppressed_key = f"SUPPRESSED:{condition_id}:{outcome_index}:{side}:{reason}"
            key_hash = self.sha(suppressed_key)
            
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO alerts_sent(
                        condition_id, outcome_index, alert_key, 
                        wallet_count, sent_at, side
                    )
                    VALUES(?, ?, ?, ?, ?, ?)
                    ON CONFLICT(alert_key) DO UPDATE SET
                        sent_at = excluded.sent_at,
                        wallet_count = excluded.wallet_count
                """, (
                    condition_id, outcome_index, key_hash,
                    wallet_count, self.now_iso(), side
                ))
                conn.commit()
                return True
                
        except Exception as e:
            logger.error(f"Error marking suppressed alert as sent: {e}")
            return False
    
    def mark_alert_sent(self, condition_id: str, outcome_index: int, 
                       wallet_count: int, first_ts: float, last_ts: float, alert_key: str = "", side: str = "BUY",
                       price: float = 0.0, wallets_csv: str = "", wallet_details_json: str = "", 
                       total_usd: float = 0.0, is_repeat: bool = False) -> bool:
        """Mark alert as sent
        
        Args:
            wallet_details_json: JSON string with wallet details: [{"wallet": "...", "usd_amount": 123.45, "price": 0.32}, ...]
            total_usd: Total USD position size for this alert
            is_repeat: If True, this is a repeat alert (position increased >2x), update first_total_usd
        """
        try:
            if alert_key:
                key = self.sha(f"ALERT:{alert_key}:{int(first_ts)}:{int(last_ts)}")
            else:
                key = self.sha(f"ALERT:{condition_id}:{outcome_index}:{int(first_ts)}:{int(last_ts)}")
            
            alert_id = key[:8]
            now_iso = self.now_iso()
            
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                if is_repeat:
                    # Update first_total_usd for the first alert of this (condition_id, outcome_index, side)
                    cursor.execute("""
                        UPDATE alerts_sent
                        SET first_total_usd = ?
                        WHERE condition_id = ? AND outcome_index = ? AND side = ?
                        AND first_total_usd IS NULL
                        ORDER BY sent_at ASC
                        LIMIT 1
                    """, (total_usd, condition_id, outcome_index, side))
                    logger.info(f"[Alerts] Updated first_total_usd to ${total_usd:.2f} for repeat alert")
                
                cursor.execute("""
                    INSERT INTO alerts_sent(alert_key, sent_at, condition_id, 
                                          outcome_index, wallet_count, side, price, wallets_csv, wallet_details_json, first_total_usd)
                    VALUES(?,?,?,?,?,?,?,?,?,?)
                """, (key, now_iso, condition_id, outcome_index, wallet_count, side, float(price or 0.0), wallets_csv, wallet_details_json, total_usd if not is_repeat else None))
                
                conn.commit()
                
                # Log successful save
                wallet_addresses = wallets_csv.split(",") if wallets_csv else []
                logger.info(
                    f"[Alerts] Stored alert {alert_id} for market={condition_id[:20]}..., "
                    f"outcome={outcome_index}, wallets={len(wallet_addresses)}, side={side}, price={price:.4f}, total_usd=${total_usd:.2f}"
                )
                
                return True
                
        except Exception as e:
            logger.error(f"Error marking alert as sent for {condition_id}:{outcome_index}: {e}", exc_info=True)
            return False
    
    def get_first_total_usd(self, condition_id: str, outcome_index: int, side: str) -> Optional[float]:
        """Get first total_usd for a given (condition_id, outcome_index, side) combination"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT first_total_usd FROM alerts_sent
                    WHERE condition_id = ? AND outcome_index = ? AND side = ?
                    AND first_total_usd IS NOT NULL
                    ORDER BY sent_at ASC
                    LIMIT 1
                """, (condition_id, outcome_index, side))
                row = cursor.fetchone()
                if row and row[0] is not None:
                    return float(row[0])
                return None
        except Exception as e:
            logger.error(f"Error getting first_total_usd: {e}")
            return None
    
    def has_alert_for_market(self, condition_id: str, outcome_index: int, side: str) -> bool:
        """Check if any alert was sent for this (condition_id, outcome_index, side) combination"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT 1 FROM alerts_sent
                    WHERE condition_id = ? AND outcome_index = ? AND side = ?
                    LIMIT 1
                """, (condition_id, outcome_index, side))
                return cursor.fetchone() is not None
        except Exception as e:
            logger.error(f"Error checking alert for market: {e}")
            return False

    def has_recent_alert(self, condition_id: str, outcome_index: int, side: str, cooldown_min: float) -> bool:
        """Check if a recent alert for the same market/side was sent within cooldown."""
        try:
            cutoff = (datetime.now(timezone.utc).timestamp() - cooldown_min * 60)
            cutoff_iso = datetime.fromtimestamp(cutoff, tz=timezone.utc).isoformat()
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT 1 FROM alerts_sent
                    WHERE condition_id = ? AND outcome_index = ? AND side = ? AND sent_at >= ?
                    LIMIT 1
                    """,
                    (condition_id, outcome_index, side, cutoff_iso)
                )
                return cursor.fetchone() is not None
        except Exception as e:
            logger.error(f"Error checking recent alert: {e}")
            return False

    def has_recent_opposite_alert(self, condition_id: str, outcome_index: int, side: str, window_min: float) -> bool:
        """Check if an alert for opposite side exists within a window (to avoid conflicts)."""
        opposite = "SELL" if side.upper() == "BUY" else "BUY"
        return self.has_recent_alert(condition_id, outcome_index, opposite, window_min)

    def get_recent_alerts(self, condition_id: str, outcome_index: int, limit: int = 3):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT sent_at, side, wallet_count, price, wallets_csv, outcome_index
                    FROM alerts_sent
                    WHERE condition_id = ? AND outcome_index = ?
                    ORDER BY sent_at DESC
                    LIMIT ?
                    """,
                    (condition_id, outcome_index, limit)
                )
                rows = cursor.fetchall()
                return [dict(sent_at=row[0], side=row[1], wallet_count=row[2], price=row[3], wallets_csv=row[4], outcome_index=row[5]) for row in rows]
        except Exception as e:
            logger.error(f"Error getting recent alerts: {e}")
            return []
    
    def get_recent_alerts_count(self, since: str = None) -> int:
        """Get count of alerts sent since a given timestamp (ISO format)"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                if since:
                    cursor.execute(
                        """
                        SELECT COUNT(*) FROM alerts_sent
                        WHERE datetime(sent_at) >= datetime(?)
                        """,
                        (since,)
                    )
                else:
                    cursor.execute("SELECT COUNT(*) FROM alerts_sent")
                return cursor.fetchone()[0]
        except Exception as e:
            logger.error(f"Error getting recent alerts count: {e}")
            return 0
    
    def cleanup_old_data(self, days_to_keep: int = 7):
        """Clean up old data to prevent database bloat"""
        try:
            cutoff_date = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
            cutoff_date = cutoff_date.replace(day=cutoff_date.day - days_to_keep)
            cutoff_iso = cutoff_date.isoformat()
            
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Clean old alerts
                cursor.execute("DELETE FROM alerts_sent WHERE sent_at < ?", (cutoff_iso,))
                alerts_removed = cursor.rowcount
                
                # Clean old rolling buys (keep only recent ones)
                cursor.execute("DELETE FROM rolling_buys WHERE updated_at < ?", (cutoff_iso,))
                rolling_removed = cursor.rowcount
                
                # Clean old order flow metrics
                cursor.execute("DELETE FROM order_flow_metrics WHERE detected_at < ?", (cutoff_iso,))
                order_flow_removed = cursor.rowcount
                
                conn.commit()
                
                if alerts_removed > 0 or rolling_removed > 0 or order_flow_removed > 0:
                    logger.info(f"Cleaned up {alerts_removed} old alerts, {rolling_removed} old rolling buys, and {order_flow_removed} old order flow metrics")
                    
        except Exception as e:
            logger.error(f"Error cleaning up old data: {e}")
    
    # Wallet analysis jobs queue operations
    def add_wallet_to_queue(self, address: str, display: str = None, source: str = None) -> bool:
        """Add wallet to analysis queue"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                now = self.now_iso()
                
                cursor.execute("""
                    INSERT OR IGNORE INTO wallet_analysis_jobs(
                        address, display, source, status, created_at, updated_at
                    )
                    VALUES(?,?,?,?,?,?)
                """, (address.lower(), display, source, 'pending', now, now))
                
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error adding wallet to queue {address}: {e}")
            return False
    
    def get_pending_jobs(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get pending jobs ready for processing"""
        try:
            with self.get_connection() as conn:
                # Ensure we can read uncommitted changes in WAL mode
                conn.execute("PRAGMA read_uncommitted = 1")
                cursor = conn.cursor()
                now = self.now_iso()
                
                logger.debug(f"get_pending_jobs(limit={limit}) called, now={now}")
                
                cursor.execute("""
                    SELECT * FROM wallet_analysis_jobs
                    WHERE status = 'pending' 
                    AND (next_retry_at IS NULL OR next_retry_at <= ?)
                    ORDER BY created_at ASC
                    LIMIT ?
                """, (now, limit))
                
                rows = cursor.fetchall()
                result = [dict(row) for row in rows]
                
                logger.debug(f"get_pending_jobs(limit={limit}) returned {len(result)} jobs")
                
                # Debug logging if no results but jobs exist
                if not result:
                    cursor.execute("SELECT COUNT(*) FROM wallet_analysis_jobs WHERE status = 'pending'")
                    total_pending = cursor.fetchone()[0]
                    if total_pending > 0:
                        cursor.execute("SELECT COUNT(*) FROM wallet_analysis_jobs WHERE status = 'pending' AND (next_retry_at IS NULL OR next_retry_at <= ?)", (now,))
                        ready_count = cursor.fetchone()[0]
                        # Log more details for debugging
                        cursor.execute("SELECT COUNT(*) FROM wallet_analysis_jobs WHERE status = 'pending' AND next_retry_at IS NOT NULL AND next_retry_at > ?", (now,))
                        delayed_count = cursor.fetchone()[0]
                        logger.warning(f"get_pending_jobs: total_pending={total_pending}, ready={ready_count}, delayed={delayed_count}, limit={limit}, now={now}")
                        # If we have ready jobs but query returned nothing, there might be a transaction issue
                        if ready_count > 0:
                            logger.error(f"get_pending_jobs: BUG DETECTED - {ready_count} ready jobs exist but query returned 0! This may indicate a transaction isolation issue.")
                else:
                    logger.debug(f"get_pending_jobs: returning {len(result)} jobs")
                
                return result
        except Exception as e:
            logger.error(f"Error getting pending jobs: {e}", exc_info=True)
            return []
    
    def claim_job(self, job_id: int) -> bool:
        """Atomically claim a job for processing"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                now = self.now_iso()
                
                # Try to claim the job by updating status to 'processing'
                cursor.execute("""
                    UPDATE wallet_analysis_jobs
                    SET status = 'processing', updated_at = ?
                    WHERE id = ? AND status = 'pending'
                """, (now, job_id))
                
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error claiming job {job_id}: {e}")
            return False
    
    def update_job_status(self, job_id: int, status: str, error_message: str = None, 
                         next_retry_at: str = None) -> bool:
        """Update job status"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                now = self.now_iso()
                
                cursor.execute("""
                    UPDATE wallet_analysis_jobs
                    SET status = ?, error_message = ?, next_retry_at = ?, updated_at = ?
                    WHERE id = ?
                """, (status, error_message, next_retry_at, now, job_id))
                
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error updating job status {job_id}: {e}")
            return False
    
    def get_job_by_id(self, job_id: int) -> Optional[Dict[str, Any]]:
        """Get job by ID"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM wallet_analysis_jobs WHERE id = ?", (job_id,))
                row = cursor.fetchone()
                if row:
                    return dict(row)
                return None
        except Exception as e:
            logger.error(f"Error getting job {job_id}: {e}")
            return None
    
    def increment_job_retry(self, job_id: int, next_retry_at: str, error_message: str = None) -> bool:
        """Increment retry count, set next retry time, and reset status to pending"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                now = self.now_iso()
                
                cursor.execute("""
                    UPDATE wallet_analysis_jobs
                    SET retry_count = retry_count + 1,
                        next_retry_at = ?,
                        error_message = ?,
                        status = 'pending',
                        updated_at = ?
                    WHERE id = ?
                """, (next_retry_at, error_message, now, job_id))
                
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error incrementing job retry {job_id}: {e}")
            return False
    
    def complete_job(self, job_id: int) -> bool:
        """Mark job as completed"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                now = self.now_iso()
                cursor.execute("""
                    UPDATE wallet_analysis_jobs
                    SET status = 'completed', updated_at = ?
                    WHERE id = ?
                """, (now, job_id))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error completing job {job_id}: {e}")
            return False
    
    def get_queue_stats(self) -> Dict[str, int]:
        """Get queue statistics"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                stats = {}
                
                # Clean up stuck processing jobs (older than 1 hour)
                now = self.now_iso()
                one_hour_ago = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
                cursor.execute("""
                    UPDATE wallet_analysis_jobs
                    SET status = 'pending', updated_at = ?
                    WHERE status = 'processing' AND updated_at < ?
                """, (now, one_hour_ago))
                stuck_reset = cursor.rowcount
                if stuck_reset > 0:
                    logger.warning(f"Reset {stuck_reset} stuck processing jobs back to pending")
                    conn.commit()
                
                # Count by status
                cursor.execute("""
                    SELECT status, COUNT(*) FROM wallet_analysis_jobs
                    GROUP BY status
                """)
                
                for row in cursor.fetchall():
                    stats[f"{row[0]}_jobs"] = row[1]
                
                # Total jobs
                cursor.execute("SELECT COUNT(*) FROM wallet_analysis_jobs")
                stats['total_jobs'] = cursor.fetchone()[0]
                
                # Jobs ready for retry
                cursor.execute("""
                    SELECT COUNT(*) FROM wallet_analysis_jobs
                    WHERE status = 'pending' 
                    AND (next_retry_at IS NULL OR next_retry_at <= ?)
                """, (now,))
                stats['ready_jobs'] = cursor.fetchone()[0]
                
                return stats
        except Exception as e:
            logger.error(f"Error getting queue stats: {e}")
            return {}
    
    def debug_queue(self):
        """Debug utility to check queue status"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Status counts
            cursor.execute("SELECT status, COUNT(*) FROM wallet_analysis_jobs GROUP BY status")
            status_counts = dict(cursor.fetchall())
            logger.info(f"Queue status counts: {status_counts}")
            
            # Ready jobs (pending with no retry delay or retry time passed)
            now = self.now_iso()
            cursor.execute("""
                SELECT COUNT(*) FROM wallet_analysis_jobs 
                WHERE status='pending' 
                AND (next_retry_at IS NULL OR next_retry_at <= ?)
            """, (now,))
            ready_count = cursor.fetchone()[0]
            logger.info(f"Ready jobs (can be processed now): {ready_count}")
            
            # Next retry range
            cursor.execute("""
                SELECT MIN(next_retry_at), MAX(next_retry_at) 
                FROM wallet_analysis_jobs 
                WHERE status='pending' AND next_retry_at IS NOT NULL
            """)
            retry_range = cursor.fetchone()
            if retry_range and retry_range[0]:
                logger.info(f"Next retry range: {retry_range[0]} to {retry_range[1]}")
                retry_range_dict = {'min': retry_range[0], 'max': retry_range[1]}
            else:
                logger.info("No jobs with next_retry_at set")
                retry_range_dict = None
            
            return {
                'status_counts': status_counts,
                'ready_jobs': ready_count,
                'retry_range': retry_range_dict
            }
    
    # Wallet analysis cache operations
    def get_cached_analysis(self, address: str) -> Optional[Dict[str, Any]]:
        """Get cached analysis result for wallet"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                now = self.now_iso()
                
                cursor.execute("""
                    SELECT * FROM wallet_analysis_cache
                    WHERE address = ? AND expires_at > ?
                """, (address.lower(), now))
                
                row = cursor.fetchone()
                return dict(row) if row else None
        except Exception as e:
            logger.error(f"Error getting cached analysis for {address}: {e}")
            return None
    
    def cache_analysis_result(self, address: str, traded_total: int, win_rate: float,
                             realized_pnl_total: float, daily_frequency: float,
                             analysis_result: str, ttl_hours: int = 24,
                             last_trade_at: Optional[str] = None, source: Optional[str] = None,
                             is_insider_candidate: Optional[bool] = None,
                             insider_detection_reason: Optional[str] = None,
                             total_markets_traded: Optional[int] = None) -> bool:
        """Cache analysis result for wallet"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                now = datetime.now(timezone.utc)
                expires_at = now + timedelta(hours=ttl_hours)
                
                # Check if created_at column exists
                cursor.execute("PRAGMA table_info(wallet_analysis_cache)")
                columns = [row[1] for row in cursor.fetchall()]
                has_created_at = 'created_at' in columns
                
                # Build dynamic INSERT and UPDATE clauses for insider fields
                insert_fields = [
                    "address", "traded_total", "win_rate", "realized_pnl_total",
                    "daily_trading_frequency", "analysis_result", "analyzed_at", "expires_at",
                    "last_trade_at", "source"
                ]
                insert_values = [
                    address.lower(), traded_total, win_rate, realized_pnl_total,
                    daily_frequency, analysis_result, now.isoformat(), expires_at.isoformat(),
                    last_trade_at, source
                ]
                
                update_fields = [
                    "traded_total = excluded.traded_total",
                    "win_rate = excluded.win_rate",
                    "realized_pnl_total = excluded.realized_pnl_total",
                    "daily_trading_frequency = excluded.daily_trading_frequency",
                    "analysis_result = excluded.analysis_result",
                    "analyzed_at = excluded.analyzed_at",
                    "expires_at = excluded.expires_at",
                    "last_trade_at = excluded.last_trade_at",
                    "source = excluded.source"
                ]
                
                # Add insider fields if provided
                if is_insider_candidate is not None:
                    insert_fields.append("is_insider_candidate")
                    insert_values.append(1 if is_insider_candidate else 0)
                    update_fields.append("is_insider_candidate = excluded.is_insider_candidate")
                
                if insider_detection_reason is not None:
                    insert_fields.append("insider_detection_reason")
                    insert_values.append(insider_detection_reason)
                    update_fields.append("insider_detection_reason = excluded.insider_detection_reason")
                
                if total_markets_traded is not None:
                    insert_fields.append("total_markets_traded")
                    insert_values.append(total_markets_traded)
                    update_fields.append("total_markets_traded = excluded.total_markets_traded")
                
                if has_created_at:
                    insert_fields.append("created_at")
                    insert_values.append(now.isoformat())
                    # created_at is preserved (not updated)
                
                placeholders = ",".join(["?"] * len(insert_values))
                insert_clause = ",".join(insert_fields)
                update_clause = ", ".join(update_fields)
                
                if has_created_at:
                    query = f"""
                        INSERT INTO wallet_analysis_cache({insert_clause})
                        VALUES({placeholders})
                        ON CONFLICT(address) DO UPDATE SET
                            {update_clause}
                            -- created_at is preserved (not updated)
                    """
                else:
                    query = f"""
                        INSERT OR REPLACE INTO wallet_analysis_cache({insert_clause})
                        VALUES({placeholders})
                    """
                
                cursor.execute(query, tuple(insert_values))
                
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error caching analysis result for {address}: {e}")
            return False
    
    def cleanup_expired_cache(self) -> int:
        """Remove expired cache entries"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                now = self.now_iso()
                
                cursor.execute("DELETE FROM wallet_analysis_cache WHERE expires_at <= ?", (now,))
                removed_count = cursor.rowcount
                
                conn.commit()
                
                if removed_count > 0:
                    logger.info(f"Cleaned up {removed_count} expired cache entries")
                
                return removed_count
        except Exception as e:
            logger.error(f"Error cleaning up expired cache: {e}")
            return 0
    
    def insert_raw_collected_wallet(self, address: str, source: str) -> None:
        """Insert a raw collected wallet address with its source"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                now = self.now_iso()
                
                cursor.execute(
                    """
                    INSERT INTO raw_collected_wallets (address, source, collected_at)
                    VALUES (?, ?, ?)
                    """,
                    (address.lower(), source, now)
                )
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to insert raw collected wallet {address} from {source}: {e}")
    
    # Wallet category statistics operations
    def upsert_wallet_category_stats(self, wallet_address: str, category: str, markets: int,
                                     volume: float, pnl: float, winrate: float, roi: float,
                                     avg_pnl: float, is_a_list_trader: bool) -> bool:
        """Insert or update wallet category statistics"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                now = self.now_iso()
                
                cursor.execute("""
                    INSERT INTO wallet_category_stats(
                        wallet_address, category, markets, volume, pnl, winrate, roi,
                        avg_pnl, is_a_list_trader, updated_at
                    )
                    VALUES(?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(wallet_address, category) DO UPDATE SET
                        markets=excluded.markets,
                        volume=excluded.volume,
                        pnl=excluded.pnl,
                        winrate=excluded.winrate,
                        roi=excluded.roi,
                        avg_pnl=excluded.avg_pnl,
                        is_a_list_trader=excluded.is_a_list_trader,
                        updated_at=excluded.updated_at
                """, (wallet_address.lower(), category, markets, volume, pnl, winrate, roi,
                     avg_pnl, 1 if is_a_list_trader else 0, now))
                
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error upserting wallet category stats for {wallet_address}/{category}: {e}")
            return False
    
    def get_wallet_category_stats(self, wallet_address: str, category: str) -> Optional[Dict[str, Any]]:
        """Get category statistics for a wallet"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM wallet_category_stats
                    WHERE wallet_address = ? AND category = ?
                """, (wallet_address.lower(), category))
                row = cursor.fetchone()
                return dict(row) if row else None
        except Exception as e:
            logger.error(f"Error getting wallet category stats for {wallet_address}/{category}: {e}")
            return None
    
    def is_wallet_a_list_in_category(self, wallet_address: str, category: str) -> bool:
        """Check if wallet is A List trader in a specific category"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT is_a_list_trader FROM wallet_category_stats
                    WHERE wallet_address = ? AND category = ?
                """, (wallet_address.lower(), category))
                row = cursor.fetchone()
                return bool(row[0]) if row and row[0] is not None else False
        except Exception as e:
            logger.debug(f"Error checking A List status for {wallet_address}/{category}: {e}")
            return False
    
    def get_wallets_with_a_list_in_category(self, category: str) -> List[str]:
        """Get list of wallet addresses that are A List traders in a specific category"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT wallet_address FROM wallet_category_stats
                    WHERE category = ? AND is_a_list_trader = 1
                """, (category,))
                return [row[0] for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error getting A List wallets for category {category}: {e}")
            return []
    
    def get_category_stats_summary(self) -> Dict[str, Any]:
        """Get summary statistics about categories"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Count wallets with at least one A List category
                cursor.execute("""
                    SELECT COUNT(DISTINCT wallet_address) FROM wallet_category_stats
                    WHERE is_a_list_trader = 1
                """)
                wallets_with_a_list = cursor.fetchone()[0]
                
                # Count by category
                cursor.execute("""
                    SELECT category, COUNT(*) as count, 
                           SUM(CASE WHEN is_a_list_trader = 1 THEN 1 ELSE 0 END) as a_list_count
                    FROM wallet_category_stats
                    GROUP BY category
                    ORDER BY count DESC
                """)
                category_counts = {}
                for row in cursor.fetchall():
                    category_counts[row[0]] = {
                        'total': row[1],
                        'a_list': row[2]
                    }
                
                return {
                    'wallets_with_a_list': wallets_with_a_list,
                    'category_counts': category_counts
                }
        except Exception as e:
            logger.error(f"Error getting category stats summary: {e}")
            return {}

# Example usage and testing
    def get_tracked_wallet_addresses(self) -> List[str]:
        """Get list of tracked wallet addresses"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT address FROM wallets ORDER BY realized_pnl_total DESC")
                addresses = [row[0] for row in cursor.fetchall()]
                return addresses
        except Exception as e:
            logger.error(f"Error getting tracked wallet addresses: {e}")
            return []
    
    def mark_wallet_as_insider_candidate(self, address: str, reason: str, total_markets_traded: Optional[int] = None) -> bool:
        """Mark wallet as insider candidate with reason"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                now = self.now_iso()
                
                update_fields = [
                    "is_insider_candidate=1",
                    "insider_detection_reason=?",
                    "insider_detected_at=?",
                    "updated_at=?"
                ]
                
                values = [reason, now, now]
                
                if total_markets_traded is not None:
                    update_fields.append("total_markets_traded=?")
                    values.append(total_markets_traded)
                
                values.append(address.lower())
                
                query = f"""
                    UPDATE wallets
                    SET {', '.join(update_fields)}
                    WHERE address = ?
                """
                
                cursor.execute(query, tuple(values))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error marking wallet as insider candidate {address}: {e}")
            return False
    
    def get_insider_candidates(self, limit: int = 100, min_position_size: Optional[float] = None) -> List[Dict[str, Any]]:
        """Get insider candidate wallets"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                query = """
                    SELECT * FROM wallets
                    WHERE is_insider_candidate = 1
                """
                params = []
                
                if min_position_size is not None:
                    # Note: position size is not stored directly, would need to calculate from trades
                    # For now, we'll just filter by insider flag
                    pass
                
                query += " ORDER BY insider_detected_at DESC LIMIT ?"
                params.append(limit)
                
                cursor.execute(query, tuple(params))
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Error getting insider candidates: {e}")
            return []
    
    def clear_insider_flag(self, address: str) -> bool:
        """Clear insider flag for a wallet"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                now = self.now_iso()
                
                cursor.execute("""
                    UPDATE wallets
                    SET is_insider_candidate = 0,
                        insider_detection_reason = NULL,
                        insider_detected_at = NULL,
                        updated_at = ?
                    WHERE address = ?
                """, (now, address.lower()))
                
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error clearing insider flag for {address}: {e}")
            return False
    
    # Open Interest operations
    def insert_open_interest(self, condition_id: str, open_interest: float, timestamp: str) -> bool:
        """Insert open interest data point"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                now = self.now_iso()
                
                cursor.execute("""
                    INSERT INTO open_interest_history(condition_id, open_interest, timestamp, created_at)
                    VALUES(?, ?, ?, ?)
                """, (condition_id, open_interest, timestamp, now))
                
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error inserting open interest for {condition_id}: {e}")
            return False
    
    def get_recent_open_interest(self, condition_id: str, minutes: int = 5) -> List[Dict[str, Any]]:
        """Get open interest history for last N minutes"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cutoff_time = (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()
                
                cursor.execute("""
                    SELECT * FROM open_interest_history
                    WHERE condition_id = ? AND timestamp >= ?
                    ORDER BY timestamp DESC
                """, (condition_id, cutoff_time))
                
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Error getting recent open interest for {condition_id}: {e}")
            return []
    
    def calculate_oi_spike(self, condition_id: str, threshold_percent: float = 20.0, max_minutes: Optional[float] = None) -> Optional[Dict[str, Any]]:
        """Calculate if open interest spiked above threshold within a time window
        
        Args:
            condition_id: Market condition ID
            threshold_percent: Minimum percentage increase to consider a spike
            max_minutes: Maximum time window in minutes between samples. If None, no time constraint is enforced.
                        If specified and time difference exceeds this window, returns None.
        
        Returns:
            Dict with spike details if spike detected within window, None otherwise
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Get the two most recent OI data points
                cursor.execute("""
                    SELECT open_interest, timestamp
                    FROM open_interest_history
                    WHERE condition_id = ?
                    ORDER BY timestamp DESC
                    LIMIT 2
                """, (condition_id,))
                
                rows = cursor.fetchall()
                if len(rows) < 2:
                    return None  # Need at least 2 data points to calculate spike
                
                new_oi = rows[0]['open_interest']
                old_oi = rows[1]['open_interest']
                new_timestamp_str = rows[0]['timestamp']
                old_timestamp_str = rows[1]['timestamp']
                
                if old_oi is None or old_oi == 0 or new_oi is None:
                    return None
                
                # Enforce time window if max_minutes is specified
                if max_minutes is not None:
                    try:
                        # Parse timestamps (assuming ISO format)
                        new_timestamp = datetime.fromisoformat(new_timestamp_str.replace('Z', '+00:00'))
                        old_timestamp = datetime.fromisoformat(old_timestamp_str.replace('Z', '+00:00'))
                        
                        # Ensure both timestamps are timezone-aware
                        if new_timestamp.tzinfo is None:
                            new_timestamp = new_timestamp.replace(tzinfo=timezone.utc)
                        if old_timestamp.tzinfo is None:
                            old_timestamp = old_timestamp.replace(tzinfo=timezone.utc)
                        
                        time_diff = (new_timestamp - old_timestamp).total_seconds() / 60.0  # Convert to minutes
                        
                        if time_diff > max_minutes:
                            logger.debug(f"OI spike check skipped: time difference {time_diff:.1f} min exceeds max window {max_minutes} min for {condition_id[:20]}...")
                            return None
                    except (ValueError, TypeError) as e:
                        logger.debug(f"Could not parse timestamps for OI spike check: {e}")
                        # Continue without time constraint if parsing fails
                
                spike_percent = ((new_oi - old_oi) / old_oi) * 100.0
                
                if spike_percent >= threshold_percent:
                    return {
                        'old_oi': old_oi,
                        'new_oi': new_oi,
                        'spike_percent': spike_percent,
                        'timestamp': rows[0]['timestamp']
                    }
                
                return None
        except Exception as e:
            logger.error(f"Error calculating OI spike for {condition_id}: {e}")
            return None
    
    def cleanup_old_oi_data(self, days_to_keep: int = 7) -> int:
        """Clean up old open interest history data"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cutoff_date = (datetime.now(timezone.utc) - timedelta(days=days_to_keep)).isoformat()
                
                cursor.execute("DELETE FROM open_interest_history WHERE created_at < ?", (cutoff_date,))
                removed_count = cursor.rowcount
                
                conn.commit()
                
                if removed_count > 0:
                    logger.info(f"Cleaned up {removed_count} old OI data points")
                
                return removed_count
        except Exception as e:
            logger.error(f"Error cleaning up old OI data: {e}")
            return 0
    
    # Whale position operations
    def insert_whale_position(self, user_address: str, condition_id: str, outcome_index: int,
                            position_size_usd: float, position_type: str) -> bool:
        """Insert whale position change"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                now = self.now_iso()
                
                cursor.execute("""
                    INSERT INTO whale_positions(user_address, condition_id, outcome_index, 
                                              position_size_usd, position_type, detected_at, alerted)
                    VALUES(?, ?, ?, ?, ?, ?, 0)
                """, (user_address.lower(), condition_id, outcome_index, position_size_usd, position_type, now))
                
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error inserting whale position for {user_address}: {e}")
            return False
    
    def get_pending_whale_alerts(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get whale positions that haven't been alerted yet"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT * FROM whale_positions
                    WHERE alerted = 0
                    ORDER BY detected_at DESC
                    LIMIT ?
                """, (limit,))
                
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Error getting pending whale alerts: {e}")
            return []
    
    def mark_whale_position_alerted(self, id: int) -> bool:
        """Mark whale position as alerted"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    UPDATE whale_positions
                    SET alerted = 1
                    WHERE id = ?
                """, (id,))
                
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error marking whale position as alerted {id}: {e}")
            return False
    
    def get_last_whale_position(self, user_address: str, condition_id: str) -> Optional[Dict[str, Any]]:
        """Get last known whale position for comparison"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT * FROM whale_positions
                    WHERE user_address = ? AND condition_id = ?
                    ORDER BY detected_at DESC
                    LIMIT 1
                """, (user_address.lower(), condition_id))
                
                row = cursor.fetchone()
                return dict(row) if row else None
        except Exception as e:
            logger.error(f"Error getting last whale position for {user_address}: {e}")
            return None
    
    def get_active_markets_from_rolling_buys(self, minutes: int = 30) -> List[str]:
        """Get list of active market condition_ids from recent rolling_buys
        
        Note: This method returns markets that have had recent consensus activity (rolling_buys),
        which is used to scope OI monitoring. This is a narrower scope than all tracked markets.
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cutoff_time = (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()
                
                cursor.execute("""
                    SELECT DISTINCT json_extract(data, '$.events[0].conditionId') as condition_id
                    FROM rolling_buys
                    WHERE updated_at >= ?
                    AND json_extract(data, '$.events[0].conditionId') IS NOT NULL
                """, (cutoff_time,))
                
                rows = cursor.fetchall()
                condition_ids = [row[0] for row in rows if row[0]]
                return condition_ids
        except Exception as e:
            logger.error(f"Error getting active markets from rolling_buys: {e}")
            return []
    
    def get_a_list_wallets(self) -> List[str]:
        """Get list of A-list wallet addresses (wallets with high win rate and PnL)"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Get wallets that are A-list traders in any category
                cursor.execute("""
                    SELECT DISTINCT wallet_address
                    FROM wallet_category_stats
                    WHERE is_a_list_trader = 1
                """)
                
                rows = cursor.fetchall()
                wallets = [row[0] for row in rows]
                
                # Also get wallets from main wallets table with high performance
                cursor.execute("""
                    SELECT address FROM wallets
                    WHERE win_rate >= 0.7 AND realized_pnl_total > 1000
                    ORDER BY realized_pnl_total DESC
                    LIMIT 100
                """)
                
                additional_wallets = [row[0] for row in cursor.fetchall()]
                
                # Combine and deduplicate
                all_wallets = list(set(wallets + additional_wallets))
                return all_wallets
        except Exception as e:
            logger.error(f"Error getting A-list wallets: {e}")
            return []
    
    # Order flow metrics operations
    def insert_order_flow_metric(self, condition_id: str, outcome_index: Optional[int], 
                                 window_start: str, window_end: str,
                                 buy_count: int, sell_count: int,
                                 buy_volume: float, sell_volume: float,
                                 buy_sell_ratio: float, is_imbalanced: bool,
                                 imbalance_direction: str) -> bool:
        """Insert order flow metric record"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                now = self.now_iso()
                
                cursor.execute("""
                    INSERT INTO order_flow_metrics(
                        condition_id, outcome_index, window_start, window_end,
                        buy_count, sell_count, buy_volume, sell_volume,
                        buy_sell_ratio, is_imbalanced, imbalance_direction, detected_at, alerted
                    )
                    VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                """, (
                    condition_id, outcome_index, window_start, window_end,
                    buy_count, sell_count, buy_volume, sell_volume,
                    buy_sell_ratio, 1 if is_imbalanced else 0, imbalance_direction, now
                ))
                
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error inserting order flow metric for {condition_id}: {e}")
            return False
    
    def get_latest_order_flow(self, condition_id: str, outcome_index: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """Get most recent order flow metric for a market"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                query = """
                    SELECT * FROM order_flow_metrics
                    WHERE condition_id = ?
                """
                params = [condition_id]
                
                if outcome_index is not None:
                    query += " AND outcome_index = ?"
                    params.append(outcome_index)
                
                query += " ORDER BY detected_at DESC LIMIT 1"
                
                cursor.execute(query, tuple(params))
                row = cursor.fetchone()
                return dict(row) if row else None
        except Exception as e:
            logger.error(f"Error getting latest order flow for {condition_id}: {e}")
            return None
    
    def get_pending_order_flow_alerts(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get order flow metrics where alerted=0 and is_imbalanced=1"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT * FROM order_flow_metrics
                    WHERE alerted = 0 AND is_imbalanced = 1
                    ORDER BY detected_at DESC
                    LIMIT ?
                """, (limit,))
                
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Error getting pending order flow alerts: {e}")
            return []
    
    def mark_order_flow_alerted(self, id: int) -> bool:
        """Mark order flow metric as alerted"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    UPDATE order_flow_metrics
                    SET alerted = 1
                    WHERE id = ?
                """, (id,))
                
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error marking order flow metric as alerted {id}: {e}")
            return False
    
    def cleanup_old_order_flow_metrics(self, days_to_keep: int = 7) -> int:
        """Delete order flow metrics older than specified days"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cutoff_date = (datetime.now(timezone.utc) - timedelta(days=days_to_keep)).isoformat()
                
                cursor.execute("DELETE FROM order_flow_metrics WHERE detected_at < ?", (cutoff_date,))
                removed_count = cursor.rowcount
                
                conn.commit()
                
                if removed_count > 0:
                    logger.info(f"Cleaned up {removed_count} old order flow metrics")
                
                return removed_count
        except Exception as e:
            logger.error(f"Error cleaning up old order flow metrics: {e}")
            return 0

if __name__ == "__main__":
    # Test database operations
    db = PolymarketDB("test_polymarket.db")
    
    # Test wallet operations
    db.upsert_wallet("0x123", "Test Wallet", 100, 0.75, 1000.0, 2.5, "test")
    wallet = db.get_wallet("0x123")
    print(f"Retrieved wallet: {wallet}")
    
    # Test stats
    stats = db.get_wallet_stats()
    print(f"Database stats: {stats}")
    
    # Cleanup
    import os
    os.remove("test_polymarket.db")
