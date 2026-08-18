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
    - Rotates through 40 active Webshare proxies
    - Automatically falls back to direct connection if Webshare proxy is unavailable
    """
    def __init__(self):
        self.failed_proxies = set()
        self.current_proxy = None
        # 40 Active Webshare Proxies
        self.webshare_proxies = [
            "http://befjoeuj:3zyfgk068k6r@94.177.49.59:6075/",
            "http://befjoeuj:3zyfgk068k6r@140.233.166.18:7051/",
            "http://befjoeuj:3zyfgk068k6r@152.232.4.41:8212/",
            "http://befjoeuj:3zyfgk068k6r@185.72.242.229:5912/",
            "http://befjoeuj:3zyfgk068k6r@213.169.215.184:5324/",
            "http://befjoeuj:3zyfgk068k6r@107.175.55.44:6985/",
            "http://befjoeuj:3zyfgk068k6r@148.135.191.70:5629/",
            "http://befjoeuj:3zyfgk068k6r@173.211.8.250:6362/",
            "http://befjoeuj:3zyfgk068k6r@23.94.138.153:6427/",
            "http://befjoeuj:3zyfgk068k6r@46.202.227.253:8260/",
            "http://befjoeuj:3zyfgk068k6r@89.45.125.85:5811/",
            "http://befjoeuj:3zyfgk068k6r@104.143.244.174:6122/",
            "http://befjoeuj:3zyfgk068k6r@104.252.49.231:6167/",
            "http://befjoeuj:3zyfgk068k6r@206.206.71.7:5647/",
            "http://befjoeuj:3zyfgk068k6r@148.135.188.196:7228/",
            "http://befjoeuj:3zyfgk068k6r@166.88.169.128:6735/",
            "http://befjoeuj:3zyfgk068k6r@181.214.6.172:5357/",
            "http://befjoeuj:3zyfgk068k6r@193.187.115.153:5668/",
            "http://befjoeuj:3zyfgk068k6r@23.27.210.252:6622/",
            "http://befjoeuj:3zyfgk068k6r@45.38.94.206:6127/",
            "http://befjoeuj:3zyfgk068k6r@46.202.227.94:8101/",
            "http://befjoeuj:3zyfgk068k6r@104.239.107.44:5696/",
            "http://befjoeuj:3zyfgk068k6r@142.111.192.29:5625/",
            "http://befjoeuj:3zyfgk068k6r@82.29.224.80:7910/",
            "http://befjoeuj:3zyfgk068k6r@107.174.215.52:7993/",
            "http://befjoeuj:3zyfgk068k6r@209.242.204.12:5753/",
            "http://befjoeuj:3zyfgk068k6r@104.252.41.62:6999/",
            "http://befjoeuj:3zyfgk068k6r@64.137.121.134:6389/",
            "http://befjoeuj:3zyfgk068k6r@108.165.205.115:5352/",
            "http://befjoeuj:3zyfgk068k6r@173.0.9.53:5636/",
            "http://befjoeuj:3zyfgk068k6r@185.48.55.21:6497/",
            "http://befjoeuj:3zyfgk068k6r@31.57.42.239:6509/",
            "http://befjoeuj:3zyfgk068k6r@212.42.199.174:5913/",
            "http://befjoeuj:3zyfgk068k6r@23.27.78.162:5742/",
            "http://befjoeuj:3zyfgk068k6r@46.203.159.161:6762/",
            "http://befjoeuj:3zyfgk068k6r@82.26.212.12:5819/",
            "http://befjoeuj:3zyfgk068k6r@45.39.13.111:5548/",
            "http://befjoeuj:3zyfgk068k6r@172.120.112.39:5718/",
            "http://befjoeuj:3zyfgk068k6r@193.239.176.213:5619/",
            "http://befjoeuj:3zyfgk068k6r@104.239.44.173:6095/"
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
