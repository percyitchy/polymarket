#!/usr/bin/env python3
"""
Proxy Manager for Polymarket API requests
Handles proxy rotation and health checking
"""

import os
import random
import logging
from typing import Optional, List, Dict
from urllib.parse import urlparse

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv not available, use system env vars only

logger = logging.getLogger(__name__)

class ProxyManager:
    """Manages proxy rotation for API requests"""
    
    def __init__(self):
        """Initialize proxy manager from environment variables"""
        self.proxies: List[Dict[str, str]] = []
        self.current_proxy_index = 0
        self.failed_proxies: set = set()
        self.proxy_enabled = False
        
        # Check global proxy enable flag (default: False - proxies disabled)
        enable_proxies = os.getenv("ENABLE_PROXIES", "false").lower() in ("true", "1", "yes")
        
        if not enable_proxies:
            logger.info("ℹ️ Proxies disabled by ENABLE_PROXIES=false, using direct connection")
            return
        
        # Load proxies from environment
        proxy_list = os.getenv("POLYMARKET_PROXIES", "")
        if proxy_list:
            self._load_proxies(proxy_list)
            self.proxy_enabled = len(self.proxies) > 0
            if self.proxy_enabled:
                logger.info(f"✅ Proxy manager initialized with {len(self.proxies)} proxies")
            else:
                logger.warning("⚠️ Proxy list is empty, using direct connection")
        else:
            logger.debug("ℹ️ No proxies configured, using direct connection")
    
    def _load_proxies(self, proxy_list: str):
        """Load proxies from comma-separated string"""
        # Format: "http://user:pass@host:port,http://user:pass@host:port,..."
        # or "socks5://user:pass@host:port,..."
        proxy_strings = [p.strip() for p in proxy_list.split(",") if p.strip()]
        
        for proxy_str in proxy_strings:
            try:
                parsed = urlparse(proxy_str)
                if parsed.scheme and parsed.hostname:
                    # For SOCKS5, we need to use different format
                    if parsed.scheme == "socks5":
                        # SOCKS5 proxies need special handling
                        self.proxies.append({
                            "http": proxy_str,
                            "https": proxy_str
                        })
                    else:
                        # HTTP/HTTPS proxies
                        self.proxies.append({
                            "http": proxy_str,
                            "https": proxy_str
                        })
                else:
                    logger.warning(f"Invalid proxy format: {proxy_str}")
            except Exception as e:
                logger.warning(f"Failed to parse proxy {proxy_str}: {e}")
    
    def get_proxy(self, rotate: bool = True) -> Optional[Dict[str, str]]:
        """
        Get next proxy in rotation
        
        Args:
            rotate: If True, advance to next proxy after returning current
            
        Returns:
            Proxy dict for requests library, or None if no proxies available
        """
        if not self.proxy_enabled or not self.proxies:
            return None
        
        # Filter out failed proxies
        available_proxies = [
            p for i, p in enumerate(self.proxies) 
            if i not in self.failed_proxies
        ]
        
        if not available_proxies:
            # Reset failed proxies if all are marked as failed
            logger.warning("All proxies marked as failed, resetting...")
            self.failed_proxies.clear()
            available_proxies = self.proxies
        
        if not available_proxies:
            return None
        
        # Get proxy (round-robin or random)
        if rotate:
            proxy = available_proxies[self.current_proxy_index % len(available_proxies)]
            self.current_proxy_index += 1
        else:
            proxy = random.choice(available_proxies)
        
        return proxy
    
    def mark_proxy_failed(self, proxy: Optional[Dict[str, str]]):
        """Mark a proxy as failed"""
        if not proxy or not self.proxies:
            return
        
        try:
            proxy_index = self.proxies.index(proxy)
            self.failed_proxies.add(proxy_index)
            logger.warning(f"Marked proxy {proxy_index} as failed")
        except ValueError:
            pass
    
    def reset_failed_proxies(self):
        """Reset all failed proxies"""
        self.failed_proxies.clear()
        logger.info("Reset all failed proxies")

