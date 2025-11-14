Т#!/usr/bin/env python3
"""
HashDive Whale Finder
Uses HashDive API to find whale wallets and add them to our database
"""

import sys
import sqlite3
from hashdive_client import HashDiveClient
from db import PolymarketDB
from wallet_analyzer import WalletAnalyzer
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_KEY = "2fcbbb010f3ff15f84dc47ebb0d92917d6fee90771407f56174423b9b28e5c3c"

class WhaleFinder:
    def __init__(self):
        self.client = HashDiveClient(API_KEY)
        self.db = PolymarketDB()
        self.analyzer = WalletAnalyzer(self.db)
    
    def find_whale_wallets(self, min_usd: int = 10000, limit: int = 100):
        """Find wallets from whale trades"""
        logger.info(f"🐋 Finding whale wallets (min ${min_usd:,})...")
        
        try:
            # Get latest whale trades - returns list directly
            response = self.client.get_latest_whale_trades(
                min_usd=min_usd,
                limit=limit
            )
            
            # API returns list
            results = response if isinstance(response, list) else response.get('results', [])
            logger.info(f"✅ Found {len(results)} whale trades")
            
            # Extract unique wallets
            wallets = set()
            for trade in results:
                user = trade.get('user_address') or trade.get('user')
                if user:
                    wallets.add(user.lower())
            
            logger.info(f"📊 Unique whale wallets: {len(wallets)}")
            return list(wallets)
            
        except Exception as e:
            logger.error(f"❌ Error finding whales: {e}")
            return []
    
    def add_whales_to_queue(self, wallets: list):
        """Add whale wallets to analysis queue"""
        logger.info(f"➕ Adding {len(wallets)} whale wallets to analysis queue...")
        
        wallets_dict = {}
        for wallet in wallets:
            wallets_dict[wallet] = {
                'display': wallet,
                'source': 'hashdive_whale'
            }
        
        # Use existing analyzer to add to queue
        added = self.analyzer.add_wallets_to_queue(wallets_dict)
        logger.info(f"✅ Added {added} wallets to queue")
        
        return added
    
    def run(self, min_usd: int = 5000, limit: int = 200):
        """Main routine"""
        logger.info("🚀 Starting whale finder...")
        
        # Check API usage
        try:
            usage = self.client.get_api_usage()
            logger.info(f"📊 API Credits: {usage.get('credits_used', 'N/A')}")
        except:
            pass
        
        # Find whales
        whale_wallets = self.find_whale_wallets(min_usd=min_usd, limit=limit)
        
        if not whale_wallets:
            logger.warning("No whale wallets found")
            return
        
        # Filter out existing wallets
        with sqlite3.connect('polymarket_notifier.db') as conn:
            cursor = conn.cursor()
            existing = set()
            for wallet in whale_wallets:
                cursor.execute("SELECT 1 FROM wallets WHERE address = ?", (wallet,))
                if cursor.fetchone():
                    existing.add(wallet)
        
        new_wallets = [w for w in whale_wallets if w not in existing]
        logger.info(f"🆕 New wallets to add: {len(new_wallets)} (skipping {len(existing)} existing)")
        
        # Add to queue
        if new_wallets:
            self.add_whales_to_queue(new_wallets)
        
        logger.info("✅ Whale finder complete!")


if __name__ == "__main__":
    finder = WhaleFinder()
    
    # Configurable parameters
    min_usd = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 200
    
    finder.run(min_usd=min_usd, limit=limit)

