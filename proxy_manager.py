import os
import random
import logging
import urllib.request
import socket
import time

logger = logging.getLogger("proxy_manager")

class ProxyManager:
    """
    Manages proxies with automatic fallback:
    1. Custom proxy from environment (PROXY_URL)
    2. Custom proxies from proxies.txt
    3. Auto-fetched high-speed HTTP/HTTPS proxies
    """
    def __init__(self):
        self.cached_proxies = []
        self.last_fetch_time = 0
        self.fetch_cooldown = 600  # 10 minutes
        self.failed_proxies = set()
        socket.setdefaulttimeout(3)

    def get_custom_proxy(self):
        """Check for user-supplied proxy in env or proxies.txt"""
        env_proxy = os.environ.get("PROXY_URL") or os.environ.get("HTTP_PROXY") or os.environ.get("HTTPS_PROXY")
        if env_proxy:
            return env_proxy.strip()

        if os.path.exists("proxies.txt"):
            try:
                with open("proxies.txt", "r", encoding="utf-8") as f:
                    lines = [line.strip() for line in f if line.strip() and not line.startswith("#")]
                    valid_lines = [p for p in lines if p not in self.failed_proxies]
                    if not valid_lines and lines:
                        self.failed_proxies.clear()
                        valid_lines = lines
                    if valid_lines:
                        return random.choice(valid_lines)
            except Exception as e:
                logger.warning(f"Could not read proxies.txt: {e}")
        return None

    def fetch_public_proxies(self):
        """Fetch fresh list of live elite proxies from reliable public sources"""
        current_time = time.time()
        if self.cached_proxies and (current_time - self.last_fetch_time < self.fetch_cooldown):
            return self.cached_proxies

        sources = [
            "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=2500&ssl=yes&anonymity=elite",
            "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
            "https://raw.githubusercontent.com/TheSpeedX/SOCKS-List/master/http.txt"
        ]

        proxies = []
        for url in sources:
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=4) as response:
                    text = response.read().decode("utf-8", errors="ignore")
                    for line in text.splitlines():
                        line = line.strip()
                        if ":" in line and not line.startswith("#"):
                            if not line.startswith("http://") and not line.startswith("https://") and not line.startswith("socks5://"):
                                line = "http://" + line
                            proxies.append(line)
                if len(proxies) >= 30:
                    break
            except Exception as e:
                logger.debug(f"Source {url} fetch error: {e}")

        proxies = list(set(proxies))
        random.shuffle(proxies)
        self.cached_proxies = proxies
        self.last_fetch_time = current_time
        logger.info(f"Fetched {len(proxies)} public proxies for rotation")
        return proxies

    def is_proxy_working(self, proxy_url, timeout=3):
        """Test if proxy can establish HTTPS TLS tunnels to prevent NS_ERROR_NET_RESET"""
        try:
            handler = urllib.request.ProxyHandler({"http": proxy_url, "https": proxy_url})
            opener = urllib.request.build_opener(handler)
            req = urllib.request.Request("https://httpbin.org/ip", headers={"User-Agent": "Mozilla/5.0"})
            with opener.open(req, timeout=timeout) as resp:
                return resp.status in (200, 301, 302, 204)
        except Exception:
            return False

    def get_working_proxy(self, max_trials=8):
        """Returns a verified working proxy, or None if no healthy proxy is available"""
        # 1. Custom proxy check first (from env or proxies.txt)
        custom = self.get_custom_proxy()
        if custom:
            masked = custom.split("@")[-1] if "@" in custom else custom
            logger.info(f"🌐 Using custom proxy: {masked}")
            return custom

        # 2. Check public pool
        proxies = self.fetch_public_proxies()
        if not proxies:
            return None

        candidates = [p for p in proxies if p not in self.failed_proxies]
        if len(candidates) < 5:
            self.failed_proxies.clear()
            candidates = proxies

        trials = min(max_trials, len(candidates))
        test_batch = random.sample(candidates, trials)

        logger.info(f"Testing {len(test_batch)} public proxies for HTTPS connectivity...")
        for p in test_batch:
            if self.is_proxy_working(p, timeout=3):
                logger.info(f"✅ Found active HTTPS proxy: {p}")
                return p
            else:
                self.failed_proxies.add(p)

        logger.info("No public proxy passed HTTPS health check; running directly")
        return None

    def mark_failed(self, proxy_url):
        """Mark a proxy as failed so it's not reused immediately"""
        if proxy_url:
            self.failed_proxies.add(proxy_url)


# Global singleton instance
proxy_manager = ProxyManager()
