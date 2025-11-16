#!/usr/bin/env python3
"""
Daily Wallet Analysis Runner
Collects wallets from all sources and processes them through the analysis queue
Designed to run daily via systemd timer or cron
"""

import os
import sys
import asyncio
import logging
import argparse
from datetime import datetime, timezone
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db import PolymarketDB
from wallet_analyzer import WalletAnalyzer, AnalysisConfig
from notify import TelegramNotifier
from polymarket_notifier import PolymarketNotifier

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('daily_wallet_analysis.log')
    ]
)
logger = logging.getLogger(__name__)

async def collect_from_polymarket_analytics(notifier, limit: int = 2500):
    """Collect wallets from polymarketanalytics.com"""
    try:
        logger.info(f"Collecting wallets from polymarketanalytics.com (limit: {limit})...")
        wallets, stats = await notifier.collect_wallets_from_polymarket_analytics(limit=limit)
        if wallets:
            added = notifier.analyze_and_filter_wallets(wallets, analytics_stats=stats)
            logger.info(f"Added {added} wallets from polymarketanalytics.com to queue")
            return added
        return 0
    except Exception as e:
        logger.error(f"Error collecting from polymarketanalytics.com: {e}", exc_info=True)
        return 0

async def collect_from_leaderboards(notifier):
    """Collect wallets from Polymarket leaderboards"""
    try:
        logger.info("Collecting wallets from Polymarket leaderboards...")
        # Use default LEADERBOARD_URLS from fetch_leaderboards.py (includes volume and all-time)
        # This will scrape up to 30 pages per URL (as configured in fetch_leaderboards.py)
        from fetch_leaderboards import LEADERBOARD_URLS
        notifier.leaderboard_urls = [url for _, url in LEADERBOARD_URLS]
        logger.info(f"Using {len(notifier.leaderboard_urls)} leaderboard URLs (max 30 pages each)")
        
        wallets = await notifier.collect_wallets_from_leaderboards()
        if wallets:
            added = notifier.analyze_and_filter_wallets(wallets)
            logger.info(f"[Queue] Added {added} new wallets from leaderboards to analysis queue")
            return added
        return 0
    except Exception as e:
        logger.error(f"Error collecting from leaderboards: {e}", exc_info=True)
        return 0

async def main():
    """Main daily analysis function"""
    load_dotenv()
    
    start_time = datetime.now(timezone.utc)
    logger.info("=" * 80)
    logger.info(f"Starting daily wallet analysis - {start_time.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    logger.info("=" * 80)
    
    # Initialize components
    db_path = os.getenv("DB_PATH", "polymarket_notifier.db")
    # Resolve absolute path to ensure consistency
    if not os.path.isabs(db_path):
        db_path = os.path.abspath(db_path)
    logger.info(f"[DB] Using database at {db_path}")
    db = PolymarketDB(db_path)
    notifier = PolymarketNotifier()
    
    # Initialize wallet analyzer with workers
    analysis_config = AnalysisConfig(
        api_max_workers=int(os.getenv("API_MAX_WORKERS", "4")),
        api_timeout_sec=int(os.getenv("API_TIMEOUT_SEC", "10"))
    )
    analyzer = WalletAnalyzer(db, analysis_config)
    
    # Start workers
    logger.info("Starting wallet analyzer workers...")
    analyzer.start_workers()
    
    try:
        # Get initial queue status
        initial_stats = analyzer.get_queue_status()
        logger.info(f"Initial queue status: {initial_stats}")
        
        # Step 1: Collect from polymarketanalytics.com
        analytics_count = await collect_from_polymarket_analytics(notifier, limit=2500)
        
        # Step 1.5: Collect from HashiDive whale trades (if enabled)
        hashdive_count = 0
        if os.getenv("ENABLE_HASHDIVE_WHALES", "false").strip().lower() in ("true", "1", "yes", "on"):
            try:
                logger.info("Collecting wallets from HashiDive whale trades...")
                hashdive_wallets = await notifier.collect_wallets_from_hashdive_whales(min_usd=5000, limit=200)
                if hashdive_wallets:
                    hashdive_count = notifier.analyze_and_filter_wallets(hashdive_wallets)
                    logger.info(f"[Queue] Added {hashdive_count} new wallets from HashiDive whales to analysis queue")
            except Exception as e:
                logger.error(f"Error collecting from HashiDive whales: {e}", exc_info=True)
        
        # Step 1.55: Collect from HashiDive Trader Explorer (if enabled)
        hashdive_explorer_count = 0
        if os.getenv("ENABLE_HASHDIVE_TRADER_EXPLORER", "false").strip().lower() in ("true", "1", "yes", "on"):
            try:
                logger.info("Collecting wallets from HashiDive Trader Explorer...")
                hashdive_explorer_wallets = await notifier.collect_wallets_from_hashdive_trader_explorer()
                if hashdive_explorer_wallets:
                    hashdive_explorer_count = notifier.analyze_and_filter_wallets(hashdive_explorer_wallets)
                    logger.info(f"[Queue] Added {hashdive_explorer_count} new wallets from HashiDive Trader Explorer to analysis queue")
            except Exception as e:
                logger.error(f"Error collecting from HashiDive Trader Explorer: {e}", exc_info=True)
        
        # Step 2: Collect from Polymarket leaderboards
        leaderboards_count = await collect_from_leaderboards(notifier)
        
        # Get final queue status
        final_stats = analyzer.get_queue_status()
        total_added = analytics_count + leaderboards_count + hashdive_count + hashdive_explorer_count
        
        # Wait a bit for workers to process some jobs
        logger.info("Waiting 10 seconds for workers to process initial jobs...")
        await asyncio.sleep(10)
        
        # Get actual wallet counts from database
        wallet_stats = db.get_wallet_stats()
        total_wallets_in_db = wallet_stats.get('total_wallets', 0)
        tracked_wallets_in_db = wallet_stats.get('tracked_wallets', 0)
        
        # Count wallets added today (approximate - wallets updated in last hour)
        from datetime import timedelta
        one_hour_ago = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) FROM wallets 
                WHERE datetime(updated_at) >= datetime(?)
            """, (one_hour_ago,))
            wallets_updated_recently = cursor.fetchone()[0]
        
        # Get activity statistics from analysis cache
        with db.get_connection() as conn:
            cursor = conn.cursor()
            # Wallets with last_trade_at
            cursor.execute("""
                SELECT COUNT(*) FROM wallet_analysis_cache 
                WHERE last_trade_at IS NOT NULL
            """)
            wallets_with_last_trade = cursor.fetchone()[0]
            
            # Wallets without last_trade_at
            cursor.execute("""
                SELECT COUNT(*) FROM wallet_analysis_cache 
                WHERE last_trade_at IS NULL
            """)
            wallets_without_last_trade = cursor.fetchone()[0]
            
            # Rejected inactive (only those with actual last_trade_at, not NULL)
            cursor.execute("""
                SELECT COUNT(*) FROM wallet_analysis_cache 
                WHERE analysis_result = 'rejected_inactive' 
                AND last_trade_at IS NOT NULL
            """)
            rejected_inactive = cursor.fetchone()[0]
        
        # Get filter breakdown statistics from analysis cache
        with db.get_connection() as conn:
            cursor = conn.cursor()
            # Total analyzed
            cursor.execute("SELECT COUNT(*) FROM wallet_analysis_cache")
            total_analyzed = cursor.fetchone()[0]
            
            # Count by analysis_result with mapping for legacy values
            filter_stats = {
                'accepted': 0,
                'rejected_low_trades': 0,
                'rejected_low_winrate': 0,
                'rejected_high_frequency': 0,
                'rejected_inactive': 0,
                'rejected_no_stats': 0,
                'rejected_api_error': 0,
                'rejected_invalid_data': 0,
                'rejected_low_markets': 0,
                'rejected_low_volume': 0,
                'rejected_low_roi': 0,
                'rejected_low_avg_pnl': 0,
                'rejected_low_avg_stake': 0,
                'rejected_legacy': 0,
                'rejected_other': 0  # Only for truly unexpected values
            }
            
            # Legacy value mapping - map old format values to new categories
            legacy_mapping = {
                'rejected': 'rejected_legacy',  # Old generic rejected
                'error': 'rejected_api_error',
                'failed': 'rejected_api_error',
                None: 'rejected_legacy',  # NULL values from old code
                '': 'rejected_legacy',  # Empty strings
            }
            
            cursor.execute("""
                SELECT analysis_result, COUNT(*) 
                FROM wallet_analysis_cache 
                GROUP BY analysis_result
            """)
            for result, count in cursor.fetchall():
                # Handle NULL values
                if result is None:
                    filter_stats['rejected_legacy'] += count
                    continue
                
                # Map legacy values
                if result in legacy_mapping:
                    mapped_result = legacy_mapping[result]
                    if mapped_result in filter_stats:
                        filter_stats[mapped_result] += count
                    else:
                        filter_stats['rejected_legacy'] += count
                # Map known new values
                elif result in filter_stats:
                    filter_stats[result] += count
                # Unknown values go to legacy
                else:
                    logger.warning(f"[Filters] Unknown analysis_result value: '{result}' (count: {count})")
                    filter_stats['rejected_legacy'] += count
        
        # Calculate summary
        end_time = datetime.now(timezone.utc)
        duration = (end_time - start_time).total_seconds()
        
        logger.info("=" * 80)
        logger.info("Daily wallet analysis summary:")
        logger.info(f"  Duration: {duration:.1f} seconds ({duration/60:.1f} minutes)")
        logger.info(f"  Wallets added from polymarketanalytics.com: {analytics_count}")
        logger.info(f"  Wallets added from leaderboards: {leaderboards_count}")
        logger.info(f"  Total new wallets added to queue: {total_added}")
        logger.info(f"  Final queue status: {final_stats}")
        logger.info("")
        logger.info(f"[TrackedSync] Database wallet counts:")
        logger.info(f"  Total wallets in DB: {total_wallets_in_db}")
        logger.info(f"  Tracked wallets (meeting criteria): {tracked_wallets_in_db}")
        logger.info(f"  Wallets updated in last hour: {wallets_updated_recently}")
        logger.info("")
        logger.info(f"[Activity] Activity statistics:")
        logger.info(f"  Wallets with last_trade_at: {wallets_with_last_trade}")
        logger.info(f"  Wallets without last_trade_at: {wallets_without_last_trade}")
        logger.info(f"  Rejected inactive (by date): {rejected_inactive}")
        logger.info("")
        logger.info(f"[Filters] Filter Breakdown:")
        logger.info(f"  Total analyzed: {total_analyzed}")
        logger.info(f"  Accepted: {filter_stats['accepted']}")
        logger.info(f"  Low trades: {filter_stats['rejected_low_trades']}")
        logger.info(f"  Low win rate: {filter_stats['rejected_low_winrate']}")
        logger.info(f"  High daily frequency: {filter_stats['rejected_high_frequency']}")
        logger.info(f"  Inactive (by date): {filter_stats['rejected_inactive']}")
        logger.info(f"  No stats: {filter_stats['rejected_no_stats']}")
        logger.info(f"  API errors: {filter_stats['rejected_api_error']}")
        logger.info(f"  Invalid data: {filter_stats['rejected_invalid_data']}")
        logger.info(f"  Low markets: {filter_stats['rejected_low_markets']}")
        logger.info(f"  Low volume: {filter_stats['rejected_low_volume']}")
        logger.info(f"  Low ROI: {filter_stats['rejected_low_roi']}")
        logger.info(f"  Low avg PnL: {filter_stats['rejected_low_avg_pnl']}")
        logger.info(f"  Low avg stake: {filter_stats['rejected_low_avg_stake']}")
        logger.info(f"  Legacy other: {filter_stats['rejected_legacy']}")
        if filter_stats['rejected_other'] > 0:
            logger.info(f"  Other (unexpected): {filter_stats['rejected_other']}")
        # Get source breakdown statistics
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            # Source breakdown from wallets table
            source_stats = {
                'analytics': {'total': 0, 'accepted': 0},
                'leaderboard': {'total': 0, 'accepted': 0},
                'api_trades': {'total': 0, 'accepted': 0},
                'hashdive_whale': {'total': 0, 'accepted': 0},
                'hashdive_trader_explorer': {'total': 0, 'accepted': 0},
            }
            
            # Count total wallets by source
            # Map various source values to standard categories
            cursor.execute("""
                SELECT source, COUNT(*) 
                FROM wallets 
                WHERE source IS NOT NULL
                GROUP BY source
            """)
            for source, count in cursor.fetchall():
                source_lower = source.lower() if source else None
                # Map to standard categories
                if source_lower in source_stats:
                    source_stats[source_lower]['total'] += count
                elif 'analytics' in source_lower or source_lower == 'polymarket_analytics':
                    source_stats['analytics']['total'] += count
                elif 'leaderboard' in source_lower or source_lower == 'leaderboards_html':
                    source_stats['leaderboard']['total'] += count
                elif 'trades' in source_lower or source_lower == 'api_trades':
                    source_stats['api_trades']['total'] += count
                elif 'hashdive' in source_lower:
                    if 'trader_explorer' in source_lower or 'explorer' in source_lower:
                        source_stats['hashdive_trader_explorer']['total'] += count
                    elif 'whale' in source_lower:
                        source_stats['hashdive_whale']['total'] += count
                    else:
                        # Generic hashdive source
                        source_stats['hashdive_whale']['total'] += count
                else:
                    # Unknown source - log for debugging
                    logger.debug(f"[Source] Unknown source value: '{source}' (count: {count})")
            
            # Count accepted wallets by source (from wallet_analysis_cache)
            cursor.execute("""
                SELECT source, COUNT(*) 
                FROM wallet_analysis_cache 
                WHERE analysis_result = 'accepted' AND source IS NOT NULL
                GROUP BY source
            """)
            for source, count in cursor.fetchall():
                source_lower = source.lower() if source else None
                # Map to standard categories
                if source_lower in source_stats:
                    source_stats[source_lower]['accepted'] += count
                elif 'analytics' in source_lower or source_lower == 'polymarket_analytics':
                    source_stats['analytics']['accepted'] += count
                elif 'leaderboard' in source_lower or source_lower == 'leaderboards_html':
                    source_stats['leaderboard']['accepted'] += count
                elif 'trades' in source_lower or source_lower == 'api_trades':
                    source_stats['api_trades']['accepted'] += count
                elif 'hashdive' in source_lower:
                    if 'trader_explorer' in source_lower or 'explorer' in source_lower:
                        source_stats['hashdive_trader_explorer']['accepted'] += count
                    elif 'whale' in source_lower:
                        source_stats['hashdive_whale']['accepted'] += count
                    else:
                        # Generic hashdive source
                        source_stats['hashdive_whale']['accepted'] += count
        
        logger.info("")
        logger.info(f"[Source] Source Breakdown:")
        logger.info(f"  Analytics: total {source_stats['analytics']['total']}, accepted {source_stats['analytics']['accepted']}")
        logger.info(f"  Leaderboards: total {source_stats['leaderboard']['total']}, accepted {source_stats['leaderboard']['accepted']}")
        logger.info(f"  API trades: total {source_stats['api_trades']['total']}, accepted {source_stats['api_trades']['accepted']}")
        logger.info(f"  HashiDive whales: total {source_stats['hashdive_whale']['total']}, accepted {source_stats['hashdive_whale']['accepted']}")
        logger.info(f"  HashiDive Trader Explorer: total {source_stats['hashdive_trader_explorer']['total']}, accepted {source_stats['hashdive_trader_explorer']['accepted']}")
        logger.info("=" * 80)
        
        # Send summary to Telegram
        try:
            telegram_notifier = TelegramNotifier()
            # Get alert configuration
            min_consensus = int(os.getenv("MIN_CONSENSUS", "3"))
            alert_window_min = float(os.getenv("ALERT_WINDOW_MIN", "15.0"))
            alert_cooldown_min = float(os.getenv("ALERT_COOLDOWN_MIN", "30.0"))
            
            summary_message = f"""📊 *Daily Wallet Analysis Complete*

*Duration:* {duration/60:.1f} minutes

*Wallets Added to Queue:*
• polymarketanalytics.com: {analytics_count}
• Leaderboards: {leaderboards_count}
• HashiDive whales: {hashdive_count}
• HashiDive Trader Explorer: {hashdive_explorer_count}
• Total: {total_added}

*Database Status:*
• Total wallets in DB: {total_wallets_in_db}
• Tracked wallets: {tracked_wallets_in_db}
• Updated in last hour: {wallets_updated_recently}

*Activity Statistics:*
• With last_trade_at: {wallets_with_last_trade}
• Without last_trade_at: {wallets_without_last_trade}
• Rejected inactive (by date): {rejected_inactive}

🔎 *Filter Breakdown:*
• Total analyzed: {total_analyzed}
• Accepted: {filter_stats['accepted']}
• Low trades: {filter_stats['rejected_low_trades']}
• Low win rate: {filter_stats['rejected_low_winrate']}
• High daily frequency: {filter_stats['rejected_high_frequency']}
• Inactive (by date): {filter_stats['rejected_inactive']}
• No stats: {filter_stats['rejected_no_stats']}
• API errors: {filter_stats['rejected_api_error']}
• Invalid data: {filter_stats['rejected_invalid_data']}
• Low markets: {filter_stats['rejected_low_markets']}
• Low volume: {filter_stats['rejected_low_volume']}
• Low ROI: {filter_stats['rejected_low_roi']}
• Low avg PnL: {filter_stats['rejected_low_avg_pnl']}
• Low avg stake: {filter_stats['rejected_low_avg_stake']}
• Legacy other: {filter_stats['rejected_legacy']}"""
            
            if filter_stats['rejected_other'] > 0:
                summary_message += f"\n• Other (unexpected): {filter_stats['rejected_other']}"
            
            summary_message += f"""

📊 Source Breakdown:
• Analytics: total {source_stats['analytics']['total']}, accepted {source_stats['analytics']['accepted']}
• Leaderboards: total {source_stats['leaderboard']['total']}, accepted {source_stats['leaderboard']['accepted']}
• API trades: total {source_stats['api_trades']['total']}, accepted {source_stats['api_trades']['accepted']}
• HashiDive whales: total {source_stats['hashdive_whale']['total']}, accepted {source_stats['hashdive_whale']['accepted']}
• HashiDive Trader Explorer: total {source_stats['hashdive_trader_explorer']['total']}, accepted {source_stats['hashdive_trader_explorer']['accepted']}
"""
            
            summary_message += """

*Queue Status:*
• Pending: {final_stats.get('pending_jobs', 0)}
• Processing: {final_stats.get('processing_jobs', 0)}
• Completed: {final_stats.get('completed_jobs', 0)}
• Failed: {final_stats.get('failed_jobs', 0)}
• Total: {final_stats.get('total_jobs', 0)}

*Workers:* {final_stats.get('active_workers', 0)} active

*🔔 Alert Configuration:*
• Min consensus: {min_consensus} wallets
• Alert window: {alert_window_min} minutes
• Cooldown: {alert_cooldown_min} minutes"""
            
            # Send daily report as plain text to avoid Markdown parsing errors
            # (special characters like underscores in variable names cause issues)
            telegram_notifier.send_message(
                summary_message,
                parse_mode=None,  # Plain text - no Markdown formatting
                chat_id=telegram_notifier.reports_chat_id
            )
            logger.info("[Telegram] Daily wallet analysis report sent successfully (plain text)")
        except Exception as e:
            logger.error(f"Failed to send Telegram summary: {e}")
        
    except Exception as e:
        logger.error(f"Error during daily wallet analysis: {e}", exc_info=True)
        # Send error notification
        try:
            telegram_notifier = TelegramNotifier()
            telegram_notifier.send_error_notification(
                "Daily Wallet Analysis Error",
                str(e)
            )
        except:
            pass
        raise
    finally:
        # Stop workers
        logger.info("Stopping wallet analyzer workers...")
        analyzer.stop_workers()
        logger.info("Daily wallet analysis complete")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Daily wallet analysis runner")
    parser.add_argument("--dry-run", action="store_true", help="Dry run mode (not implemented, kept for compatibility)")
    args = parser.parse_args()
    
    if args.dry_run:
        logger.warning("Dry-run mode requested but not implemented. Running normally.")
    
    asyncio.run(main())

