import os
import random
import logging
import requests
from urllib.parse import urlparse

logger = logging.getLogger("proxy_manager")

class ProxyManager:
    """
    Manages Webshare proxies integrated directly via requests:
    - Tests connectivity using requests.get('https://ipv4.webshare.io/', proxies={...})
    - Automatically falls back to direct connection if Webshare proxy is unavailable or unpaid (402)
    """
    def __init__(self):
        self.failed_proxies = set()
        self.current_proxy = None
        # Integrated Webshare proxy endpoints
        self.webshare_proxies = [
            "http://befjoeuj:3zyfgk068k6r@31.59.20.176:6754/",
            "http://befjoeuj:3zyfgk068k6r@31.56.127.193:7684/",
            "http://befjoeuj:3zyfgk068k6r@45.38.107.97:6014/",
            "http://befjoeuj:3zyfgk068k6r@198.105.121.200:6462/",
            "http://befjoeuj:3zyfgk068k6r@64.137.96.74:6641/",
            "http://befjoeuj:3zyfgk068k6r@198.23.243.226:6361/",
            "http://befjoeuj:3zyfgk068k6r@38.154.185.97:6370/",
            "http://befjoeuj:3zyfgk068k6r@84.247.60.125:6095/",
            "http://befjoeuj:3zyfgk068k6r@142.111.67.146:5611/",
            "http://befjoeuj:3zyfgk068k6r@191.96.254.138:6185/"
        ]

    def to_playwright_dict(self, proxy_str):
        """Converts proxy URL to Playwright dictionary format"""
        if not proxy_str:
            return None
        proxy_str = proxy_str.strip()
        parsed = urlparse(proxy_str)
        scheme = parsed.scheme or "http"
        host = parsed.hostname
        port = parsed.port
        
        if parsed.username and parsed.password:
            return {
                "server": f"{scheme}://{host}:{port}",
                "username": parsed.username,
                "password": parsed.password
            }
        else:
            return {
                "server": f"{scheme}://{host}:{port}" if port else f"{scheme}://{host}"
            }

    def is_proxy_working(self, proxy_url, timeout=5):
        """
        Verify Webshare proxy connectivity using requests:
        requests.get("https://ipv4.webshare.io/", proxies={"http": proxy_url, "https": proxy_url})
        """
        if not proxy_url:
            return False
        try:
            proxies = {
                "http": proxy_url,
                "https": proxy_url
            }
            resp = requests.get("https://ipv4.webshare.io/", proxies=proxies, timeout=timeout)
            if resp.status_code == 200:
                verified_ip = resp.text.strip()
                logger.info(f"🌐 Webshare proxy verified (External IP: {verified_ip})")
                return True
            else:
                logger.warning(f"⚠️ Webshare check returned status {resp.status_code}")
                return False
        except Exception as e:
            masked = proxy_url.split("@")[-1] if "@" in proxy_url else proxy_url
            logger.warning(f"⚠️ Webshare proxy ({masked}) check failed: {e}")
            return False

    def get_working_proxy(self):
        """
        Tests Webshare proxies using requests.get('https://ipv4.webshare.io/').
        Returns working proxy string if healthy, or None (fallback to direct connection) if failing.
        """
        env_proxy = os.environ.get("PROXY_URL") or os.environ.get("HTTP_PROXY") or os.environ.get("HTTPS_PROXY")
        proxy_candidates = [env_proxy.strip()] if env_proxy else list(self.webshare_proxies)

        available = [p for p in proxy_candidates if p not in self.failed_proxies]
        if not available:
            self.failed_proxies.clear()
            available = list(proxy_candidates)

        random.shuffle(available)

        for p in available:
            masked = p.split("@")[-1] if "@" in p else p
            logger.info(f"🔍 Testing Webshare proxy {masked} with requests.get('https://ipv4.webshare.io/')...")
            if self.is_proxy_working(p):
                logger.info(f"✅ Webshare proxy active: {masked}")
                self.current_proxy = p
                return p
            else:
                self.failed_proxies.add(p)

        logger.warning("⚠️ All Webshare proxies failed health check (e.g., subscription expired or tunnel error). Falling back to direct connection.")
        self.current_proxy = None
        return None

    def get_working_proxy_dict(self):
        """Returns the working proxy in Playwright dictionary format or None for direct connection"""
        raw_proxy = self.get_working_proxy()
        if not raw_proxy:
            return None
        return self.to_playwright_dict(raw_proxy)

    def mark_failed(self, proxy_url=None):
        """Mark a proxy as failed so it's not reused immediately"""
        target = proxy_url or self.current_proxy
        if target:
            self.failed_proxies.add(target)
            masked = target.split("@")[-1] if "@" in target else target
            logger.warning(f"Proxy marked as failed: {masked}")


# Global singleton instance
proxy_manager = ProxyManager()
