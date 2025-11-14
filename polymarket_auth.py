#!/usr/bin/env python3
"""
Polymarket API Authentication Module
Handles authenticated requests using API keys (apiKey, secret, passphrase)
"""

import os
import time
import base64
import hmac
import hashlib
from typing import Optional, Dict, Any
from datetime import datetime
import logging

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv not available, use system env vars only

logger = logging.getLogger(__name__)

class PolymarketAuth:
    """Handle Polymarket API authentication"""
    
    def __init__(self, api_key: Optional[str] = None, secret: Optional[str] = None, passphrase: Optional[str] = None):
        """
        Initialize Polymarket authentication
        
        Args:
            api_key: API key from Polymarket
            secret: Secret key from Polymarket  
            passphrase: Passphrase from Polymarket
        """
        self.api_key = api_key or os.getenv("POLYMARKET_API_KEY")
        self.secret = secret or os.getenv("POLYMARKET_SECRET")
        self.passphrase = passphrase or os.getenv("POLYMARKET_PASSPHRASE")
        
        self.has_auth = bool(self.api_key and self.secret and self.passphrase)
        
        if self.has_auth:
            logger.info("✅ Polymarket API authentication enabled")
        else:
            logger.debug("ℹ️ Polymarket API authentication not configured (using public APIs)")
    
    def _create_signature(self, timestamp: str, method: str, request_path: str, body: str = "") -> str:
        """
        Create HMAC signature for authenticated requests
        
        Args:
            timestamp: Unix timestamp as string
            method: HTTP method (GET, POST, etc.)
            request_path: API endpoint path
            body: Request body (empty string for GET)
            
        Returns:
            Base64-encoded signature
        """
        if not self.secret:
            raise ValueError("Secret key not configured")
        
        # Create the message to sign
        message = timestamp + method + request_path + body
        
        # Try different secret formats (Polymarket builder API may use different formats)
        secret_bytes = None
        
        # Try 1: Base64 decode (most common for API keys)
        try:
            secret_bytes = base64.b64decode(self.secret)
        except Exception:
            pass
        
        # Try 2: Hex decode (if base64 failed)
        if secret_bytes is None:
            try:
                secret_bytes = bytes.fromhex(self.secret)
            except Exception:
                pass
        
        # Try 3: Use as raw UTF-8 string (fallback)
        if secret_bytes is None:
            secret_bytes = self.secret.encode('utf-8')
        
        # Create HMAC SHA256 signature
        signature = hmac.new(secret_bytes, message.encode('utf-8'), hashlib.sha256)
        
        # Return base64-encoded signature
        return base64.b64encode(signature.digest()).decode('utf-8')
    
    def get_auth_headers(self, method: str, request_path: str, body: str = "") -> Dict[str, str]:
        """
        Get authentication headers for Polymarket API request
        
        Args:
            method: HTTP method (GET, POST, etc.)
            request_path: API endpoint path (e.g., "/markets/0x123...")
            body: Request body (empty string for GET)
            
        Returns:
            Dictionary with authentication headers
        """
        if not self.has_auth:
            return {}
        
        # Get current timestamp
        timestamp = str(int(time.time()))
        
        # Create signature
        signature = self._create_signature(timestamp, method, request_path, body)
        
        return {
            "POLY_API_KEY": self.api_key,
            "POLY_SIGNATURE": signature,
            "POLY_PASSPHRASE": self.passphrase,
            "POLY_TIMESTAMP": timestamp,
            # Alternative header names (depending on API version)
            "X-API-KEY": self.api_key,
            "X-SIGNATURE": signature,
            "X-PASSPHRASE": self.passphrase,
            "X-TIMESTAMP": timestamp,
        }
    
    def add_auth_to_request(self, headers: Dict[str, str], method: str, url: str, body: str = "") -> Dict[str, str]:
        """
        Add authentication headers to existing headers dict
        
        Args:
            headers: Existing headers dictionary
            method: HTTP method
            url: Full URL or path
            body: Request body
            
        Returns:
            Updated headers with authentication
        """
        # Extract path from URL if full URL provided
        if url.startswith("http"):
            from urllib.parse import urlparse
            parsed = urlparse(url)
            request_path = parsed.path
            if parsed.query:
                request_path += "?" + parsed.query
        else:
            request_path = url
        
        auth_headers = self.get_auth_headers(method, request_path, body)
        headers.update(auth_headers)
        return headers

