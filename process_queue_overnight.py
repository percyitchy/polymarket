#!/usr/bin/env python3
"""
Process wallet analysis queue overnight
Runs workers to process all pending jobs
"""

import os
import sys
import time
import signal
import logging
from datetime import datetime, timezone
from dotenv import load_dotenv

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from wallet_analyzer import WalletAnalyzer, AnalysisConfig
from db import PolymarketDB

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('queue_process_overnight.log')
    ]
)
logger = logging.getLogger(__name__)

# Global flag for graceful shutdown
running = True

def signal_handler(sig, frame):
    """Handle SIGINT/SIGTERM gracefully"""
    global running
    logger.info("Received shutdown signal, stopping workers...")
    running = False

def main():
    """Process queue overnight"""
    global running
    
    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    db_path = os.getenv("DB_PATH", "polymarket_notifier.db")
    max_hours = int(os.getenv("QUEUE_PROCESS_MAX_HOURS", "12"))  # Default 12 hours
    
    logger.info("=" * 60)
    logger.info(f"🌙 Starting overnight queue processing")
    logger.info(f"   Max runtime: {max_hours} hours")
    logger.info("=" * 60)
    
    db = PolymarketDB(db_path)
    
    # Initialize analyzer with 7 workers for faster processing
    config = AnalysisConfig(
        api_max_workers=7,  # Use 7 workers as configured
        api_timeout_sec=20,
        api_retry_max=6,
        api_retry_base=1.2,
        analysis_ttl_min=180
    )
    
    analyzer = WalletAnalyzer(db, config)
    
    # Check initial queue status
    initial_status = analyzer.get_queue_status()
    logger.info(f"📊 Initial queue status: {initial_status}")
    
    pending_jobs = initial_status.get('pending_jobs', 0)
    if pending_jobs == 0:
        logger.info("No pending jobs to process")
        return
    
    # Start workers
    logger.info(f"🚀 Starting {config.api_max_workers} workers...")
    analyzer.start_workers()
    
    start_time = datetime.now(timezone.utc)
    last_status_time = start_time
    status_interval = 300  # Log status every 5 minutes
    max_seconds = max_hours * 3600
    
    try:
        while running:
            current_time = datetime.now(timezone.utc)
            elapsed = (current_time - start_time).total_seconds()
            
            # Check max time
            if elapsed > max_seconds:
                logger.info(f"⏰ Max runtime ({max_hours} hours) reached, stopping...")
                break
            
            # Get queue status
            status = analyzer.get_queue_status()
            pending = status.get('pending_jobs', 0)
            processing = status.get('processing_jobs', 0)
            completed = status.get('total_jobs', 0) - pending - processing
            
            # Log status periodically
            if (current_time - last_status_time).total_seconds() >= status_interval:
                elapsed_hours = elapsed / 3600
                rate = completed / elapsed if elapsed > 0 else 0
                eta_hours = pending / rate / 3600 if rate > 0 else 0
                
                logger.info(f"📊 Progress: {completed} completed, {pending} pending, {processing} processing")
                logger.info(f"   Elapsed: {elapsed_hours:.1f}h, Rate: {rate:.1f} jobs/h, ETA: {eta_hours:.1f}h")
                last_status_time = current_time
            
            # Check if queue is empty
            if pending == 0 and processing == 0:
                logger.info("✅ Queue is empty, all jobs completed!")
                break
            
            # Sleep before next check
            time.sleep(60)  # Check every minute
        
    except KeyboardInterrupt:
        logger.info("Received interrupt, stopping...")
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
    finally:
        # Stop workers
        logger.info("Stopping workers...")
        analyzer.stop_workers()
        
        # Final status
        final_status = analyzer.get_queue_status()
        elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
        elapsed_hours = elapsed / 3600
        
        logger.info("=" * 60)
        logger.info("📊 Final status:")
        logger.info(f"   Elapsed time: {elapsed_hours:.2f} hours")
        logger.info(f"   Final queue status: {final_status}")
        logger.info("=" * 60)


if __name__ == "__main__":
    main()
