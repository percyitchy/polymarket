"""
HTTP Client with automatic proxy fallback
Ensures that proxy failures never block requests - automatically falls back to direct connection
"""

import logging
import requests
import urllib3
from typing import Optional, Dict, Any, Union
from urllib.parse import urlparse, urlunparse

# Note: SSL warnings are only disabled if verify=False is explicitly passed
# By default, TLS verification is enabled for security

logger = logging.getLogger(__name__)


def _mask_proxy_url(proxy_url: str) -> str:
    """
    Mask username and password in proxy URL for safe logging.
    
    Args:
        proxy_url: Proxy URL that may contain credentials
        
    Returns:
        str: Proxy URL with credentials masked (e.g., user:pass@host -> user:***@host)
    """
    try:
        parsed = urlparse(proxy_url)
        if parsed.username or parsed.password:
            # Reconstruct URL with masked password
            masked_netloc = parsed.netloc
            if parsed.username:
                if parsed.password:
                    # Replace password with ***
                    masked_netloc = f"{parsed.username}:***@{parsed.hostname}"
                    if parsed.port:
                        masked_netloc += f":{parsed.port}"
                else:
                    # Username only, no password
                    masked_netloc = f"{parsed.username}@{parsed.hostname}"
                    if parsed.port:
                        masked_netloc += f":{parsed.port}"
            
            return urlunparse((
                parsed.scheme,
                masked_netloc,
                parsed.path,
                parsed.params,
                parsed.query,
                parsed.fragment
            ))
        return proxy_url
    except Exception:
        # If parsing fails, return a safe version (just scheme://host:port)
        try:
            parsed = urlparse(proxy_url)
            safe_url = f"{parsed.scheme}://{parsed.hostname}"
            if parsed.port:
                safe_url += f":{parsed.port}"
            return safe_url
        except Exception:
            # Last resort: return a generic masked string
            return "***:***@***"


def http_get(
    url: str,
    params: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    proxy: Optional[Union[str, Dict[str, str]]] = None,
    timeout: int = 10,
    verify: bool = True
) -> Optional[requests.Response]:
    """
    Make HTTP GET request with automatic proxy fallback.
    
    If a proxy is provided and fails, automatically retries without proxy.
    This ensures that proxy failures never block price fetching.
    
    Args:
        url: Request URL
        params: Query parameters
        headers: HTTP headers
        proxy: Proxy configuration (string URL or dict like {"http": "...", "https": "..."})
        timeout: Request timeout in seconds (default: 10)
        verify: Whether to verify SSL certificates (default: True for security)
    
    Returns:
        Response object if successful, None if both proxy and direct attempts fail
    """
    # Normalize proxy format
    proxy_dict = None
    proxy_url = None
    
    if proxy:
        if isinstance(proxy, str):
            # Convert string proxy to dict format
            proxy_url = proxy
            proxy_dict = {
                "http": proxy,
                "https": proxy
            }
        elif isinstance(proxy, dict):
            # Use dict as-is
            proxy_dict = proxy
            # Extract URL for logging (prefer https, fallback to http)
            proxy_url = proxy.get("https") or proxy.get("http") or str(proxy)
        else:
            logger.warning(f"[HTTP] Invalid proxy type: {type(proxy)}, skipping proxy")
            proxy_dict = None
            proxy_url = None
    
    # Prepare headers
    request_headers = headers.copy() if headers else {}
    
    # Add proxy-specific headers if using proxy
    if proxy_dict:
        request_headers['Connection'] = 'close'
        request_headers['Proxy-Connection'] = 'close'
        # Mask credentials in proxy URL before logging
        safe_proxy_url = _mask_proxy_url(proxy_url) if proxy_url else "N/A"
        logger.info(f"[HTTP] Using proxy: {safe_proxy_url}")
    
    # Attempt 1: Try with proxy (if configured)
    if proxy_dict:
        try:
            response = requests.get(
                url,
                params=params,
                headers=request_headers,
                proxies=proxy_dict,
                timeout=timeout,
                verify=verify
            )
            
            # Check if response is successful
            if response.status_code == 200:
                logger.info(f"[HTTP] Proxy request successful")
                return response
            else:
                # Non-200 status - log but don't treat as proxy failure
                # This might be a valid API response (e.g., 404, 429)
                logger.debug(f"[HTTP] Proxy request returned status {response.status_code}")
                return response
                
        except (requests.exceptions.ProxyError,
                requests.exceptions.SSLError) as e:
            # Proxy connection errors (including SOCKS errors)
            error_msg = str(e)
            logger.warning(f"[HTTP] Proxy connection failed: {error_msg[:100]}")
            logger.info(f"[HTTP] Proxy failed, retrying without proxy...")
            
        except (requests.exceptions.ConnectionError,
                requests.exceptions.Timeout) as e:
            # Network errors that might be proxy-related
            # Check if error message suggests proxy issue
            error_msg = str(e).lower()
            if proxy_dict and ("socks" in error_msg or "proxy" in error_msg or "connection refused" in error_msg):
                logger.warning(f"[HTTP] Proxy connection failed: {str(e)[:100]}")
                logger.info(f"[HTTP] Proxy failed, retrying without proxy...")
            else:
                # Not clearly proxy-related, but we'll still try direct
                logger.warning(f"[HTTP] Connection error (may be proxy-related): {str(e)[:100]}")
                logger.info(f"[HTTP] Proxy failed, retrying without proxy...")
            
        except Exception as e:
            # Other unexpected errors - try direct fallback as safety measure
            error_msg = str(e)
            logger.warning(f"[HTTP] Proxy request error: {error_msg[:100]}")
            logger.info(f"[HTTP] Proxy failed, retrying without proxy...")
    
    # Attempt 2: Try without proxy (direct connection)
    # This runs if:
    # - No proxy was configured, OR
    # - Proxy attempt failed
    
    if not proxy_dict:
        logger.debug(f"[HTTP] No proxy configured, using direct connection")
    
    try:
        # Remove proxy-specific headers for direct connection
        direct_headers = headers.copy() if headers else {}
        if 'Proxy-Connection' in direct_headers:
            del direct_headers['Proxy-Connection']
        
        response = requests.get(
            url,
            params=params,
            headers=direct_headers,
            proxies=None,  # Explicitly no proxy
            timeout=timeout,
            verify=verify
        )
        
        if proxy_dict:
            # We fell back from proxy
            logger.info(f"[HTTP] Proxy failed, switched to direct — OK")
        else:
            # Direct connection was used from the start
            logger.debug(f"[HTTP] Direct connection successful")
        
        return response
        
    except Exception as e:
        # Direct connection also failed
        error_msg = str(e)
        if proxy_dict:
            logger.warning(f"[HTTP] Direct connection failed after proxy fallback: {error_msg[:100]}")
        else:
            logger.warning(f"[HTTP] Direct connection failed: {error_msg[:100]}")
        return None

