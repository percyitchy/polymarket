#!/usr/bin/env python3
"""
Daily report generator
Generates comprehensive daily statistics and sends alerts if issues detected
"""

import os
import sys
import logging
import argparse
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db import PolymarketDB
from notify import TelegramNotifier

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def get_daily_stats(db: PolymarketDB, date: datetime = None) -> dict:
    """Get statistics for a specific day"""
    if date is None:
        date = datetime.now(timezone.utc)
    
    # Start and end of day in UTC
    day_start = date.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)
    
    day_start_iso = day_start.isoformat()
    day_end_iso = day_end.isoformat()
    
    with db.get_connection() as conn:
        cursor = conn.cursor()
        
        stats = {}
        
        # Total wallets
        cursor.execute("SELECT COUNT(*) FROM wallets")
        stats['total_wallets'] = cursor.fetchone()[0]
        
        # Tracked wallets (meeting criteria)
        cursor.execute("""
            SELECT COUNT(*) FROM wallets 
            WHERE traded_total >= 6 
            AND traded_total <= 1200
            AND win_rate >= 0.70
            AND win_rate <= 1.0
            AND (daily_trading_frequency IS NULL OR daily_trading_frequency <= 25.0)
            AND last_trade_at IS NOT NULL
            AND datetime(last_trade_at) >= datetime('now', '-90 days')
        """)
        stats['tracked_wallets'] = cursor.fetchone()[0]
        
        # Wallets added today
        cursor.execute("""
            SELECT COUNT(*) FROM wallets 
            WHERE datetime(added_at) >= datetime(?)
            AND datetime(added_at) < datetime(?)
        """, (day_start_iso, day_end_iso))
        stats['wallets_added_today'] = cursor.fetchone()[0]
        
        # Wallets updated today
        cursor.execute("""
            SELECT COUNT(*) FROM wallets 
            WHERE datetime(updated_at) >= datetime(?)
            AND datetime(updated_at) < datetime(?)
        """, (day_start_iso, day_end_iso))
        stats['wallets_updated_today'] = cursor.fetchone()[0]
        
        # Queue statistics
        queue_stats = db.get_queue_stats()
        stats['queue_pending'] = queue_stats.get('pending_jobs', 0)
        stats['queue_processing'] = queue_stats.get('processing_jobs', 0)
        stats['queue_completed'] = queue_stats.get('completed_jobs', 0)
        stats['queue_failed'] = queue_stats.get('failed_jobs', 0)
        stats['queue_total'] = queue_stats.get('total_jobs', 0)
        
        # Jobs completed today
        cursor.execute("""
            SELECT COUNT(*) FROM wallet_analysis_jobs 
            WHERE status = 'completed'
            AND datetime(updated_at) >= datetime(?)
            AND datetime(updated_at) < datetime(?)
        """, (day_start_iso, day_end_iso))
        stats['jobs_completed_today'] = cursor.fetchone()[0]
        
        # Jobs failed today
        cursor.execute("""
            SELECT COUNT(*) FROM wallet_analysis_jobs 
            WHERE status = 'failed'
            AND datetime(updated_at) >= datetime(?)
            AND datetime(updated_at) < datetime(?)
        """, (day_start_iso, day_end_iso))
        stats['jobs_failed_today'] = cursor.fetchone()[0]
        
        # Failed rate
        if stats['jobs_completed_today'] + stats['jobs_failed_today'] > 0:
            stats['failed_rate'] = stats['jobs_failed_today'] / (stats['jobs_completed_today'] + stats['jobs_failed_today'])
        else:
            stats['failed_rate'] = 0.0
        
        # Average processing time (from completed jobs today)
        cursor.execute("""
            SELECT AVG(
                (julianday(updated_at) - julianday(created_at)) * 86400
            ) FROM wallet_analysis_jobs 
            WHERE status = 'completed'
            AND datetime(updated_at) >= datetime(?)
            AND datetime(updated_at) < datetime(?)
        """, (day_start_iso, day_end_iso))
        avg_time = cursor.fetchone()[0]
        stats['avg_processing_time_sec'] = avg_time if avg_time else 0
        
        # Processing speed (jobs per hour)
        if stats['jobs_completed_today'] > 0:
            stats['jobs_per_hour'] = stats['jobs_completed_today'] / 24.0
        else:
            stats['jobs_per_hour'] = 0.0
        
        # Estimated time to clear queue (hours)
        if stats['jobs_per_hour'] > 0 and stats['queue_pending'] > 0:
            stats['estimated_clear_time_hours'] = stats['queue_pending'] / stats['jobs_per_hour']
        else:
            stats['estimated_clear_time_hours'] = None
        
        # New wallets from different sources (if source tracking exists)
        cursor.execute("""
            SELECT source, COUNT(*) FROM wallets 
            WHERE datetime(added_at) >= datetime(?)
            AND datetime(added_at) < datetime(?)
            GROUP BY source
        """, (day_start_iso, day_end_iso))
        sources = dict(cursor.fetchall())
        stats['wallets_by_source'] = sources
        
        # Jobs by status (current state)
        cursor.execute("""
            SELECT status, COUNT(*) FROM wallet_analysis_jobs
            GROUP BY status
        """)
        job_statuses = dict(cursor.fetchall())
        stats['jobs_by_status'] = job_statuses
        
        # Alert configuration (from environment)
        stats['min_consensus'] = int(os.getenv("MIN_CONSENSUS", "3"))
        stats['alert_window_min'] = float(os.getenv("ALERT_WINDOW_MIN", "15.0"))
        stats['alert_cooldown_min'] = float(os.getenv("ALERT_COOLDOWN_MIN", "30.0"))
        
        return stats

def check_alerts(stats: dict) -> list:
    """Check for alert conditions and return list of alerts"""
    alerts = []
    
    # Alert 1: High failed rate (>5%)
    FAILED_RATE_THRESHOLD = float(os.getenv("ALERT_FAILED_RATE_THRESHOLD", "0.05"))  # 5% default
    if stats['failed_rate'] > FAILED_RATE_THRESHOLD:
        alerts.append({
            'type': 'high_failed_rate',
            'severity': 'warning',
            'message': f"⚠️ High failed rate: {stats['failed_rate']:.1%} ({stats['jobs_failed_today']} failed / {stats['jobs_completed_today'] + stats['jobs_failed_today']} total)"
        })
    
    # Alert 2: Queue not processing (pending > 1000 and no completed today)
    QUEUE_STUCK_THRESHOLD = int(os.getenv("ALERT_QUEUE_STUCK_THRESHOLD", "1000"))
    if stats['queue_pending'] > QUEUE_STUCK_THRESHOLD and stats['jobs_completed_today'] == 0:
        alerts.append({
            'type': 'queue_stuck',
            'severity': 'critical',
            'message': f"🚨 Queue appears stuck: {stats['queue_pending']} pending, 0 completed today"
        })
    
    # Alert 3: Queue not keeping up (pending growing faster than processing)
    # If pending > threshold and completion rate < min_jobs_per_hour, alert
    QUEUE_SLOW_THRESHOLD = int(os.getenv("ALERT_QUEUE_SLOW_THRESHOLD", "500"))
    MIN_JOBS_PER_HOUR = float(os.getenv("ALERT_MIN_JOBS_PER_HOUR", "20.0"))
    if stats['queue_pending'] > QUEUE_SLOW_THRESHOLD:
        jobs_per_hour = stats['jobs_completed_today'] / 24.0  # Approximate hourly rate
        if jobs_per_hour < MIN_JOBS_PER_HOUR:
            alerts.append({
                'type': 'queue_slow',
                'severity': 'warning',
                'message': f"⚠️ Queue processing slowly: {stats['queue_pending']} pending, ~{jobs_per_hour:.1f} jobs/hour (need ~{stats['queue_pending'] / MIN_JOBS_PER_HOUR:.1f} hours to clear)"
            })
    
    # Alert 4: Very low completion rate (<10 jobs/day with pending jobs)
    if stats['jobs_completed_today'] < 10 and stats['queue_pending'] > 0:
        alerts.append({
            'type': 'low_processing_rate',
            'severity': 'warning',
            'message': f"⚠️ Low processing rate: only {stats['jobs_completed_today']} jobs completed today with {stats['queue_pending']} pending"
        })
    
    # Alert 5: Database growth (too many wallets)
    if stats['total_wallets'] > 5000:
        alerts.append({
            'type': 'database_large',
            'severity': 'info',
            'message': f"ℹ️ Database growing large: {stats['total_wallets']} total wallets"
        })
    
    # Alert 6: No new wallets added (informational, not critical)
    if stats['wallets_added_today'] == 0:
        alerts.append({
            'type': 'no_new_wallets',
            'severity': 'info',
            'message': "ℹ️ No new wallets added today (may be normal if all wallets already tracked)"
        })
    
    return alerts

def format_daily_report(stats: dict, alerts: list) -> str:
    """Format daily report message"""
    report_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    
    lines = [
        f"📊 *Daily Report - {report_date}*",
        "",
        "*📈 Wallet Statistics:*",
        f"• Total wallets: {stats['total_wallets']}",
        f"• Tracked wallets: {stats['tracked_wallets']}",
        f"• Added today: {stats['wallets_added_today']}",
        f"• Updated today: {stats['wallets_updated_today']}",
    ]
    
    # Add source breakdown if available
    if stats.get('wallets_by_source'):
        lines.append("• By source:")
        for source, count in stats['wallets_by_source'].items():
            lines.append(f"  - {source}: {count}")
    
    lines.extend([
        "",
        "*⚙️ Queue Statistics:*",
        f"• Pending: {stats['queue_pending']}",
        f"• Processing: {stats['queue_processing']}",
        f"• Completed today: {stats['jobs_completed_today']}",
        f"• Failed today: {stats['jobs_failed_today']}",
        f"• Failed rate: {stats['failed_rate']:.1%}",
        "",
        "*🔔 Alert Configuration:*",
        f"• Min consensus: {stats.get('min_consensus', 'N/A')} wallets",
        f"• Alert window: {stats.get('alert_window_min', 'N/A')} minutes",
        f"• Cooldown: {stats.get('alert_cooldown_min', 'N/A')} minutes",
    ])
    
    if stats['avg_processing_time_sec'] > 0:
        lines.append(f"• Avg processing time: {stats['avg_processing_time_sec']:.1f}s")
    
    if stats['jobs_per_hour'] > 0:
        lines.append(f"• Processing speed: ~{stats['jobs_per_hour']:.1f} jobs/hour")
    
    if stats.get('estimated_clear_time_hours') and stats['estimated_clear_time_hours']:
        hours = stats['estimated_clear_time_hours']
        if hours < 24:
            lines.append(f"• Est. time to clear queue: {hours:.1f} hours")
        else:
            days = hours / 24.0
            lines.append(f"• Est. time to clear queue: {days:.1f} days")
    
    # Add current job status breakdown
    if stats.get('jobs_by_status'):
        lines.append("")
        lines.append("*📋 Current Job Status:*")
        for status, count in sorted(stats['jobs_by_status'].items()):
            lines.append(f"• {status}: {count}")
    
    # Alerts section
    if alerts:
        lines.append("")
        # Separate alerts by severity
        critical_alerts = [a for a in alerts if a.get('severity') == 'critical']
        warning_alerts = [a for a in alerts if a.get('severity') == 'warning']
        info_alerts = [a for a in alerts if a.get('severity') == 'info']
        
        if critical_alerts:
            lines.append("*🚨 Critical Alerts:*")
            for alert in critical_alerts:
                lines.append(f"• {alert['message']}")
        
        if warning_alerts:
            lines.append("")
            lines.append("*⚠️ Warnings:*")
            for alert in warning_alerts:
                lines.append(f"• {alert['message']}")
        
        if info_alerts:
            lines.append("")
            lines.append("*ℹ️ Info:*")
            for alert in info_alerts:
                lines.append(f"• {alert['message']}")
    
    return "\n".join(lines)

def main():
    """Generate and send daily report"""
    parser = argparse.ArgumentParser(description="Generate daily report")
    parser.add_argument("--date", type=str, help="Date in YYYY-MM-DD format (default: today)", default=None)
    args = parser.parse_args()
    
    load_dotenv()
    
    # Parse date if provided
    report_date = None
    if args.date:
        if args.date.lower() == "today":
            report_date = datetime.now(timezone.utc)
        else:
            try:
                report_date = datetime.strptime(args.date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except ValueError:
                logger.error(f"Invalid date format: {args.date}. Use YYYY-MM-DD or 'today'")
                sys.exit(1)
    
    logger.info("=" * 80)
    logger.info(f"Generating daily report for {report_date.strftime('%Y-%m-%d') if report_date else 'today'}")
    logger.info("=" * 80)
    
    db_path = os.getenv("DB_PATH", "polymarket_notifier.db")
    db = PolymarketDB(db_path)
    
    # Get daily statistics
    stats = get_daily_stats(db, date=report_date)
    
    # Check for alerts
    alerts = check_alerts(stats)
    
    # Format report
    report = format_daily_report(stats, alerts)
    
    logger.info("Daily statistics:")
    logger.info(f"  Total wallets: {stats['total_wallets']}")
    logger.info(f"  Tracked wallets: {stats['tracked_wallets']}")
    logger.info(f"  Jobs completed today: {stats['jobs_completed_today']}")
    logger.info(f"  Jobs failed today: {stats['jobs_failed_today']}")
    logger.info(f"  Failed rate: {stats['failed_rate']:.1%}")
    
    if alerts:
        logger.warning(f"Alerts detected: {len(alerts)}")
        for alert in alerts:
            logger.warning(f"  - {alert['message']}")
    
    # Send to Telegram
    notifier = TelegramNotifier()
    # Use reports_channel_id for reports if configured, otherwise reports_chat_id, fallback to chat_id
    if hasattr(notifier, 'reports_channel_id') and notifier.reports_channel_id:
        target_chat = notifier.reports_channel_id
    elif hasattr(notifier, 'reports_chat_id') and notifier.reports_chat_id:
        target_chat = notifier.reports_chat_id
    else:
        target_chat = notifier.chat_id
    # Create a temporary notifier with target chat if needed
    if target_chat != notifier.chat_id:
        temp_notifier = TelegramNotifier(chat_id=target_chat)
        success = temp_notifier.send_message(report, parse_mode="Markdown")
    else:
        success = notifier.send_message(report, parse_mode="Markdown")
    
    if success:
        logger.info("Daily report sent to Telegram")
    else:
        logger.error("Failed to send daily report to Telegram")
    
    logger.info("=" * 80)
    logger.info("Daily report complete")
    logger.info("=" * 80)

if __name__ == "__main__":
    main()

