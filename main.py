import os
import sys
import logging
import asyncio
import random
import hashlib
from datetime import datetime
import sqlite3
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
from telegram import Bot
import time
import aiohttp
import json
import re
import tempfile

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Ensure a valid temp directory exists for Playwright when running main.py directly
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
SAFE_TMP = os.path.join(BASE_DIR, "playwright_tmp")

try:
    os.makedirs(SAFE_TMP, exist_ok=True)
    os.environ['TMP'] = SAFE_TMP
    os.environ['TEMP'] = SAFE_TMP
    os.environ['TMPDIR'] = SAFE_TMP
    # sanity check
    fd, test_tmp_path = tempfile.mkstemp(dir=SAFE_TMP)
    os.close(fd)
    os.remove(test_tmp_path)
    logger.info(f"Playwright temp dir set to: {SAFE_TMP}")
except Exception as env_err:
    logger.warning(f"Failed to initialize safe temp path in main.py: {env_err}")
class NaukriJobScraper:
    def __init__(self, telegram_token, channel_id):
        self.job_url = "https://www.naukri.com/it-jobs?src=gnbjobs_homepage_srch"
        self.telegram_token = telegram_token
        self.channel_id = channel_id
        self.db_path = "jobs.db"
        self.use_proxies = True
        self.proxies = []
        self.last_proxy_fetch_time = 0
        self.proxy_fetch_interval = 30 * 60  # 30 minutes
        self.setup_database()
        
    def setup_database(self):
        """Initialize SQLite database to store job information"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS jobs (
            job_id TEXT PRIMARY KEY,
            title TEXT,
            company TEXT,
            location TEXT,
            posted_date TEXT,
            apply_link TEXT,
            posted_to_telegram INTEGER DEFAULT 0,
            timestamp TEXT
        )
        ''')
        conn.commit()
        conn.close()
        logger.info("Database setup complete")
    
    def get_random_user_agent(self):
        """Return a random user agent from a list of common browsers"""
        user_agents = [
            # Chrome on Windows
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36',
            # Firefox on Windows
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/119.0',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:108.0) Gecko/20100101 Firefox/118.0',
            # Edge on Windows
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0',
            # Safari on macOS
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15',
            # Chrome on macOS
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            # Mobile User Agents
            'Mozilla/5.0 (iPhone; CPU iPhone OS 17_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
            'Mozilla/5.0 (Linux; Android 10; SM-G981B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.162 Mobile Safari/537.36'
        ]
        return random.choice(user_agents)
        
    class BrowserContextManager:
        """Context manager for browser context"""
        def __init__(self, scraper):
            self.scraper = scraper
            self.playwright = None
            self.browser = None
            self.context = None
            
        async def __aenter__(self):
            self.playwright = await async_playwright().start()
            
            # Get random user agent and viewport
            user_agent = self.scraper.get_random_user_agent()
            viewport = self.scraper.get_random_viewport()
            
            # Launch browser with enhanced stealth mode
            browser_args = [
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-infobars',
                '--disable-dev-shm-usage',
                '--disable-blink-features=AutomationControlled',
                '--disable-extensions',
                '--disable-features=IsolateOrigins,site-per-process',
                '--disable-site-isolation-trials',
                '--disable-web-security',
                '--disable-features=BlockInsecurePrivateNetworkRequests',
                '--disable-notifications',
                '--disable-popup-blocking',
                '--ignore-certificate-errors',
                '--window-size=1920,1080',
                '--disable-background-timer-throttling',
                '--disable-backgrounding-occluded-windows',
                '--disable-breakpad',
                '--disable-component-extensions-with-background-pages',
                '--disable-accelerated-2d-canvas',
                '--no-first-run',
                '--no-zygote',
                '--disable-gpu',
                '--hide-scrollbars',
                '--mute-audio',
                '--disable-http2'  # Force HTTP/1.1 so proxies don't break HTTP/2
            ]
            
            # Set headless mode to True for Linux/production (no display needed)
            headless_mode = True
            
            self.browser = await self.playwright.chromium.launch(
                headless=headless_mode,
                args=browser_args
            )
            
            # Configure context with enhanced stealth settings
            context_options = {
                'viewport': viewport,
                'user_agent': user_agent,
                'locale': 'en-US',
                'timezone_id': 'Asia/Kolkata',
                'color_scheme': 'no-preference',  # Use system default
                'geolocation': {'latitude': 12.9716, 'longitude': 77.5946},
                'permissions': ['geolocation'],
                'extra_http_headers': {
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Cache-Control': 'max-age=0',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1',
                    'Sec-Fetch-Dest': 'document',
                    'Sec-Fetch-Mode': 'navigate',
                    'Sec-Fetch-Site': 'none',
                    'Sec-Fetch-User': '?1',
                    'DNT': '1',
                    'Referer': 'https://www.google.com/',
                    'Sec-Ch-Ua': '"Chromium";v="116", "Not)A;Brand";v="24", "Google Chrome";v="116"',
                    'Sec-Ch-Ua-Mobile': '?0',
                    'Sec-Ch-Ua-Platform': '"Windows"'
                }
            }
            
            # Create browser context
            self.context = await self.browser.new_context(**context_options)
            
            # Add cookies to appear more like a real user
            await self.context.add_cookies([
                {
                    'name': 'visited_before',
                    'value': 'true',
                    'domain': '.naukri.com',
                    'path': '/',
                },
                {
                    'name': 'session_depth',
                    'value': str(random.randint(1, 5)),
                    'domain': '.naukri.com',
                    'path': '/',
                }
            ])
            
            # Add comprehensive stealth scripts
            await self.context.add_init_script("""
                // Override webdriver property with more properties
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => false,
                    enumerable: true,
                    configurable: true
                });
            """)
            
            return self.context
            
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
    
    def get_browser_context(self):
        """Return a context manager for browser context"""
        return self.BrowserContextManager(self)
    
    def get_random_viewport(self):
        """Return a random viewport size"""
        viewports = [
            {'width': 1920, 'height': 1080},  # Full HD
            {'width': 1366, 'height': 768},   # Common laptop
            {'width': 1536, 'height': 864},   # Common laptop
            {'width': 1440, 'height': 900},   # MacBook
            {'width': 1280, 'height': 720},   # HD
            {'width': 1680, 'height': 1050},  # Large monitor
        ]
        return random.choice(viewports)
        
    async def fetch_free_proxies(self):
        """Fetch a list of free proxies from public proxy lists"""
        if not self.use_proxies:
            return []
            
        current_time = time.time()
        # Only fetch new proxies if it's been more than the fetch interval
        if self.proxies and current_time - self.last_proxy_fetch_time < self.proxy_fetch_interval:
            logger.info(f"Using cached proxies, count: {len(self.proxies)}")
            return self.proxies
            
        logger.info("Fetching new proxy list")
        proxies = []
        
        # Try multiple proxy sources for redundancy
        sources = [
            "https://www.sslproxies.org/",
            "https://free-proxy-list.net/",
            "https://www.us-proxy.org/"
        ]
        
        try:
            async with aiohttp.ClientSession() as session:
                for source in sources:
                    try:
                        async with session.get(source, timeout=10) as response:
                            if response.status == 200:
                                html = await response.text()
                                soup = BeautifulSoup(html, 'html.parser')
                                table = soup.find('table', attrs={'class': 'table table-striped table-bordered'})
                                
                                if not table:
                                    continue
                                    
                                for row in table.find_all('tr'):
                                    cells = row.find_all('td')
                                    if len(cells) > 1:
                                        ip = cells[0].text.strip()
                                        port = cells[1].text.strip()
                                        https = cells[6].text.strip()
                                        
                                        # Only use HTTPS proxies
                                        if https.lower() == 'yes' and self.is_valid_ip(ip):
                                            proxy = f"http://{ip}:{port}"
                                            proxies.append(proxy)
                    except Exception as e:
                        logger.warning(f"Error fetching proxies from {source}: {str(e)}")
                        continue
        except Exception as e:
            logger.error(f"Error fetching proxies: {str(e)}")
        
        # Deduplicate and shuffle
        proxies = list(set(proxies))
        random.shuffle(proxies)
        
        # Update cache
        self.proxies = proxies
        self.last_proxy_fetch_time = current_time
        
        logger.info(f"Fetched {len(proxies)} proxies")
        return proxies
    
    def is_valid_ip(self, ip):
        """Check if the IP address is valid"""
        pattern = r'^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$'
        match = re.match(pattern, ip)
        if not match:
            return False
        for i in range(1, 5):
            if int(match.group(i)) > 255:
                return False
        return True
    
    async def get_working_proxy(self):
        """Test proxies and return a working one"""
        if not self.use_proxies:
            return None
            
        proxies = await self.fetch_free_proxies()
        if not proxies:
            logger.warning("No proxies available")
            return None
            
        # Test up to 5 random proxies
        test_proxies = random.sample(proxies, min(5, len(proxies)))
        
        for proxy in test_proxies:
            try:
                logger.info(f"Testing proxy: {proxy}")
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        "https://www.google.com", 
                        proxy=proxy,
                        timeout=5,
                        headers={'User-Agent': self.get_random_user_agent()}
                    ) as response:
                        if response.status == 200:
                            logger.info(f"Found working proxy: {proxy}")
                            return proxy
            except Exception:
                continue
                
        logger.warning("No working proxy found")
        return None
    
    async def simulate_human_behavior(self, page):
        """Simulate human-like behavior to avoid detection"""
        logger.info("Simulating human-like behavior")
        
        # Random mouse movements
        for _ in range(random.randint(3, 7)):
            x = random.randint(100, 800)
            y = random.randint(100, 600)
            await page.mouse.move(x, y, steps=random.randint(5, 10))
            await asyncio.sleep(random.uniform(0.1, 0.5))
        
        # Random scrolling
        for _ in range(random.randint(2, 5)):
            await page.evaluate(f'window.scrollBy(0, {random.randint(100, 300)})')
            await asyncio.sleep(random.uniform(0.5, 1.5))
            
        # Occasionally scroll back up
        if random.random() < 0.3:
            await page.evaluate(f'window.scrollBy(0, {random.randint(-200, -100)})')
            await asyncio.sleep(random.uniform(0.5, 1.0))
            
        # Random pauses
        await asyncio.sleep(random.uniform(1.0, 3.0))
    
    async def scrape_jobs(self, categories=None):
        """Scrape job listings from Naukri.com
        
        Args:
            categories (list): List of job categories to scrape. Defaults to IT jobs if None.
        """
        jobs = []
        
        # Define job categories if not provided
        if categories is None:
            categories = [
                {"name": "IT", "url": "https://www.naukri.com/it-jobs?src=gnbjobs_homepage_srch&sort=1"},
                {"name": "Software", "url": "https://www.naukri.com/software-developer-jobs?sort=1"},
                {"name": "Data Science", "url": "https://www.naukri.com/data-scientist-jobs?sort=1"}
            ]
        
        # Maximum retry attempts
        max_retries = 3
        
        try:
            # Try to get a working proxy
            proxy = await self.get_working_proxy() if self.use_proxies else None
            if proxy:
                logger.info(f"Using proxy: {proxy}")
            else:
                logger.info("No proxy available, proceeding without proxy")
                
            async with async_playwright() as p:
                # Get random user agent and viewport
                user_agent = self.get_random_user_agent()
                viewport = self.get_random_viewport()
                
                logger.info(f"Using user agent: {user_agent}")
                
                # Launch browser with enhanced stealth mode
                browser_args = [
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-infobars',
                    '--disable-dev-shm-usage',
                    '--disable-blink-features=AutomationControlled',
                    '--disable-extensions',
                    '--disable-features=IsolateOrigins,site-per-process',
                    '--disable-site-isolation-trials',
                    '--disable-web-security',
                    '--disable-features=BlockInsecurePrivateNetworkRequests',
                    '--disable-notifications',
                    '--disable-popup-blocking',
                    '--ignore-certificate-errors',
                    '--window-size=1920,1080',
                    '--disable-background-timer-throttling',
                    '--disable-backgrounding-occluded-windows',
                    '--disable-breakpad',
                    '--disable-component-extensions-with-background-pages',
                    '--disable-accelerated-2d-canvas',
                    '--no-first-run',
                    '--no-zygote',
                    '--disable-gpu',
                    '--hide-scrollbars',
                    '--mute-audio',
                    '--disable-http2'  # Force HTTP/1.1 so proxies don't break HTTP/2
                ]
                
                # Add proxy if available
                if proxy:
                    browser_args.append(f'--proxy-server={proxy}')
                
                # Set headless mode to True for Linux/production (no display needed)
                headless_mode = True
                
                browser = await p.chromium.launch(
                    headless=headless_mode,
                    args=browser_args
                )
                
                # Configure context with enhanced stealth settings
                context_options = {
                    'viewport': viewport,
                    'user_agent': user_agent,
                    'locale': 'en-US',
                    'timezone_id': 'Asia/Kolkata',
                    'color_scheme': 'no-preference',  # Use system default
                    'geolocation': {'latitude': 12.9716, 'longitude': 77.5946},
                    'permissions': ['geolocation'],
                    'extra_http_headers': {
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                        'Accept-Language': 'en-US,en;q=0.9',
                        'Cache-Control': 'max-age=0',
                        'Connection': 'keep-alive',
                        'Upgrade-Insecure-Requests': '1',
                        'Sec-Fetch-Dest': 'document',
                        'Sec-Fetch-Mode': 'navigate',
                        'Sec-Fetch-Site': 'none',
                        'Sec-Fetch-User': '?1',
                        'DNT': '1',
                        'Referer': 'https://www.google.com/',
                        'Sec-Ch-Ua': '"Chromium";v="116", "Not)A;Brand";v="24", "Google Chrome";v="116"',
                        'Sec-Ch-Ua-Mobile': '?0',
                        'Sec-Ch-Ua-Platform': '"Windows"'
                    }
                }
                
                # Create browser context
                context = await browser.new_context(**context_options)
                
                # Add cookies to appear more like a real user
                await context.add_cookies([
                    {
                        'name': 'visited_before',
                        'value': 'true',
                        'domain': '.naukri.com',
                        'path': '/',
                    },
                    {
                        'name': 'session_depth',
                        'value': str(random.randint(1, 5)),
                        'domain': '.naukri.com',
                        'path': '/',
                    }
                ])
                
                # Add comprehensive stealth scripts
                await context.add_init_script("""
                    // Override webdriver property with more properties
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => false,
                        enumerable: true,
                        configurable: true
                    });
                    
                    // Add Chrome runtime with more comprehensive properties
                    window.chrome = {
                        runtime: {
                            connect: function() {},
                            sendMessage: function() {},
                            onMessage: {
                                addListener: function() {},
                                removeListener: function() {}
                            }
                        },
                        loadTimes: function() { return { firstPaintTime: 0, firstPaintAfterLoadTime: 0 }; },
                        csi: function() { return { startE: 0, onloadT: 0, pageT: 0, tran: 0 }; },
                        app: { isInstalled: false },
                        webstore: { onInstallStageChanged: {}, onDownloadProgress: {} }
                    };
                    
                    // Add plugins
                    Object.defineProperty(navigator, 'plugins', {
                        get: () => {
                            return [
                                { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer', description: 'Portable Document Format' },
                                { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai', description: 'Portable Document Format' },
                                { name: 'Native Client', filename: 'internal-nacl-plugin', description: '' }
                            ];
                        }
                    });
                    
                    // Add languages
                    Object.defineProperty(navigator, 'languages', {
                        get: () => ['en-US', 'en']
                    });
                    
                    // Override permissions with more comprehensive approach
                    if (window.navigator.permissions) {
                        const originalQuery = window.navigator.permissions.query;
                        window.navigator.permissions.query = function(parameters) {
                            return parameters.name === 'notifications' || 
                                   parameters.name === 'clipboard-read' || 
                                   parameters.name === 'clipboard-write' || 
                                   parameters.name === 'camera' || 
                                   parameters.name === 'microphone' ?
                                Promise.resolve({ state: Notification.permission }) :
                                originalQuery(parameters);
                        };
                    }
                    
                    // Override toString methods to hide script modifications
                    const originalFunctionToString = Function.prototype.toString;
                    Function.prototype.toString = function() {
                        if (this === Function.prototype.toString) return originalFunctionToString.call(this);
                        if (this === window.navigator.permissions.query) {
                            return 'function query() { [native code] }';
                        }
                        return originalFunctionToString.call(this);
                    };
                    
                    // Prevent iframe detection
                    Object.defineProperty(window, 'frameElement', {
                        get: () => null
                    });
                    
                    // Spoof screen resolution
                    Object.defineProperty(window.screen, 'width', { get: () => 1920 });
                    Object.defineProperty(window.screen, 'height', { get: () => 1080 });
                    Object.defineProperty(window.screen, 'availWidth', { get: () => 1920 });
                    Object.defineProperty(window.screen, 'availHeight', { get: () => 1080 });
                    Object.defineProperty(window.screen, 'colorDepth', { get: () => 24 });
                    Object.defineProperty(window.screen, 'pixelDepth', { get: () => 24 });
                """)
                
                # Create new page
                page = await context.new_page()
                
                # Try a more direct approach - visit Naukri.com directly with proper referrer
                try:
                    logger.info("Visiting Naukri.com directly with referrer")
                    await page.set_extra_http_headers({
                        'Referer': 'https://www.google.com/search?q=naukri+jobs+india',
                        'User-Agent': user_agent
                    })
                    
                    # Visit Naukri homepage first
                    await page.goto('https://www.naukri.com/', wait_until='domcontentloaded', timeout=60000)
                    await asyncio.sleep(random.uniform(3, 5))
                    
                    # Check if we're on the homepage
                    if await page.title() and 'Naukri' in await page.title():
                        logger.info("Successfully loaded Naukri homepage")
                        
                        # Simulate human-like behavior - random mouse movements and scrolling
                        for _ in range(3):
                            await page.mouse.move(random.randint(100, 800), random.randint(100, 600))
                            await asyncio.sleep(random.uniform(0.5, 1.5))
                        
                        # Scroll down slowly
                        for _ in range(5):
                            await page.evaluate('window.scrollBy(0, 300)')
                            await asyncio.sleep(random.uniform(0.5, 1.0))
                            
                        # Take a screenshot for debugging
                        await page.screenshot(path="naukri_homepage.png")
                    else:
                        logger.warning("Failed to load Naukri homepage properly")
                except Exception as e:
                    logger.warning(f"Error visiting Naukri homepage: {str(e)}")
                    # Continue anyway - we'll try direct category URLs
                
                # Only process the first category
                if categories and len(categories) > 0:
                    category = categories[0]
                    category_name = category["name"]
                    job_url = category["url"]
                    
                    logger.info(f"Navigating to {category_name} jobs: {job_url}")
                    
                    # Implement retry mechanism for the category
                    retry_count = 0
                    success = False
                    
                    while retry_count < max_retries and not success:
                        try:
                            # If this is a retry, get a new user agent and refresh the page context
                            if retry_count > 0:
                                logger.info(f"Retry attempt {retry_count} for {category_name}")
                                # Get a new user agent
                                new_user_agent = self.get_random_user_agent()
                                await page.set_extra_http_headers({
                                    'User-Agent': new_user_agent,
                                    'Referer': 'https://www.google.com/search?q=naukri+jobs+india',
                                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                                    'Accept-Language': 'en-US,en;q=0.5',
                                    'Cache-Control': 'max-age=0',
                                    'Connection': 'keep-alive',
                                    'Upgrade-Insecure-Requests': '1',
                                    'DNT': '1'
                                })
                                # Add some delay between retries
                                await asyncio.sleep(random.uniform(5, 10))
                            
                            # Skip anti-bot evasion script for now as it's causing issues
                            logger.info(f"Navigating to {job_url} with enhanced headers")
                            
                            # Navigate to the job URL
                            await page.goto(job_url, wait_until='domcontentloaded', timeout=60000)
                            
                            # Wait for the page to load completely
                            await asyncio.sleep(10)
                            
                            # Break after first successful navigation
                            success = True
                        except Exception as e:
                            logger.error(f"Navigation error: {str(e)}")
                            retry_count += 1
                            await asyncio.sleep(random.uniform(5, 10))
                            continue
                    
                    # === JOB EXTRACTION — runs after successful navigation ===
                    if success:
                        try:
                            page_content = await page.content()
                            soup = BeautifulSoup(page_content, 'html.parser')
                            
                            # Modern Naukri.com selectors (2024-25)
                            job_cards = soup.select(
                                '.srp-jobtuple-wrapper, '
                                'article.jobTupleWrapper, '
                                '.jobTuple, '
                                '[class*="srp-jobtuple"], '
                                '[class*="NormalCard"], '
                                'div[data-job-id]'
                            )
                            logger.info(f"Found {len(job_cards)} job cards for {category_name}")
                            
                            category_jobs = []
                            for job_card in job_cards[:20]:
                                try:
                                    # Title
                                    title_el = job_card.select_one(
                                        '.title, .job-title, [class*="title"], h2, h3'
                                    )
                                    if not title_el:
                                        continue
                                    title = title_el.text.strip()
                                    
                                    # Company
                                    comp_el = job_card.select_one(
                                        '.companyName, .company, [class*="company"], '
                                        '.subTitle, [class*="subTitle"], .comp-name'
                                    )
                                    company = comp_el.text.strip() if comp_el else "Unknown Company"
                                    if "Reviews" in company:
                                        company = company.split("Reviews")[0].strip()
                                    import re as _re
                                    company = _re.sub(r'\d+\.?\d*$', '', company).strip()
                                    
                                    # Experience
                                    exp_el = job_card.select_one(
                                        '.expwdth, [class*="experience"], [class*="exp"]'
                                    )
                                    experience = exp_el.text.strip() if exp_el else "Not specified"
                                    
                                    # Location
                                    loc_el = job_card.select_one(
                                        '.locWdth, .location, [class*="location"], [class*="loc"]'
                                    )
                                    location = loc_el.text.strip() if loc_el else "Not specified"
                                    
                                    # Posted date
                                    date_el = job_card.select_one(
                                        '.job-post-day, .postedDate, .fleft.postedDate, [class*="day"]'
                                    )
                                    posted_date = date_el.text.strip() if date_el else "Just Now"
                                    
                                    # Job URL — look for job listing links
                                    apply_link = ""
                                    for link in job_card.find_all('a'):
                                        href = link.get('href', '')
                                        if any(p in href for p in ['/job-listings/', '/job-detail/', 'jobid=', 'jdUrl=']):
                                            apply_link = href if href.startswith('http') else 'https://www.naukri.com' + href
                                            break
                                    if not apply_link:
                                        for link in job_card.find_all('a'):
                                            href = link.get('href', '')
                                            if href and not href.startswith('#') and not href.startswith('javascript:'):
                                                apply_link = href if href.startswith('http') else 'https://www.naukri.com' + href
                                                break
                                    
                                    job_id = f"job_{hashlib.md5((title + company).encode()).hexdigest()}"
                                    job = {
                                        'job_id': job_id,
                                        'title': title,
                                        'company': company,
                                        'location': location,
                                        'experience': experience,
                                        'posted_date': posted_date,
                                        'apply_link': apply_link,
                                        'category': category_name,
                                        'timestamp': datetime.now().isoformat()
                                    }
                                    category_jobs.append(job)
                                    
                                except Exception as e:
                                    logger.error(f"Error extracting job card: {str(e)}")
                                    continue
                            
                            if category_jobs:
                                logger.info(f"Extracted {len(category_jobs)} jobs for {category_name}")
                                jobs.extend(category_jobs)
                            else:
                                logger.warning(f"No jobs extracted from {category_name} page")
                                
                        except Exception as e:
                            logger.error(f"Error during job extraction for {category_name}: {str(e)}")
                    else:
                        logger.error(f"Failed to scrape {category_name} jobs after {max_retries} retries")
                    
                    # Delay between categories
                    await asyncio.sleep(random.uniform(5, 10))
                
                await browser.close()
                
                if not jobs:
                    logger.warning("No jobs found across all categories")
                else:
                    logger.info(f"Found a total of {len(jobs)} jobs across all categories")
                
                return jobs

                
                # Get page content and parse with BeautifulSoup
                content = await page.content()
                soup = BeautifulSoup(content, 'html.parser')
                logger.info("Page content loaded and parsed with BeautifulSoup")
                
                # Find all job listings
                job_cards = soup.find_all('article', class_='jobTuple')
                
                for job_card in job_cards[:10]:  # Limit to 10 jobs for testing
                    try:
                        # Extract job details
                        title_elem = job_card.find('a', class_='title')
                        title = title_elem.text.strip() if title_elem else "N/A"
                        
                        company_elem = job_card.find('a', class_='subTitle')
                        company = company_elem.text.strip() if company_elem else "N/A"
                        
                        location_elem = job_card.find('li', class_='location')
                        location = location_elem.text.strip() if location_elem else "N/A"
                        
                        # Extract job link
                        job_link = title_elem['href'] if title_elem and 'href' in title_elem.attrs else ""
                        
                        # Extract posted date (may be in different formats)
                        posted_date_elem = job_card.find('span', {'class': ['fleft', 'postedDate']})
                        posted_date = posted_date_elem.text.strip() if posted_date_elem else "N/A"
                        
                        # Generate a unique job ID
                        job_id = f"job_{datetime.now().strftime('%Y%m%d%H%M%S')}_{len(jobs)}"
                        
                        # Add job to list
                        jobs.append({
                            'job_id': job_id,
                            'title': title,
                            'company': company,
                            'location': location,
                            'posted_date': posted_date,
                            'apply_link': job_link,
                            'timestamp': datetime.now().isoformat()
                        })
                        
                        logger.info(f"Found job: {title} at {company}")
                    except Exception as e:
                        logger.error(f"Error extracting job details: {str(e)}")
                        continue
                
                # Close browser
                await browser.close()
                
                if not jobs:
                    logger.warning("No jobs found")
                
                return jobs
                
        except Exception as e:
            logger.error(f"Failed to scrape jobs: {str(e)}")
            return []
    
    def save_jobs_to_db(self, jobs):
        """Save scraped jobs to database"""
        if not jobs:
            return 0
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        new_jobs_count = 0
        
        for job in jobs:
            # Check if job already exists (using apply_link as unique identifier)
            cursor.execute("SELECT * FROM jobs WHERE apply_link = ?", (job['apply_link'],))
            existing_job = cursor.fetchone()
            
            if not existing_job and job['apply_link']:  # Only add if job doesn't exist and has a valid link
                cursor.execute('''
                INSERT INTO jobs (job_id, title, company, location, posted_date, apply_link, posted_to_telegram, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    job['job_id'],
                    job['title'],
                    job['company'],
                    job['location'],
                    job['posted_date'],
                    job['apply_link'],
                    0,  # Not posted to Telegram yet
                    job['timestamp']
                ))
                new_jobs_count += 1
        
        conn.commit()
        conn.close()
        
        logger.info(f"Saved {new_jobs_count} new jobs to database")
        return new_jobs_count
    
    def get_unposted_jobs(self):
        """Get jobs that haven't been posted to Telegram yet"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # This enables column access by name
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM jobs WHERE posted_to_telegram = 0")
        jobs = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        
        logger.info(f"Found {len(jobs)} unposted jobs")
        return jobs
    
    def mark_job_as_posted(self, job_id):
        """Mark a job as posted to Telegram"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("UPDATE jobs SET posted_to_telegram = 1 WHERE job_id = ?", (job_id,))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Marked job {job_id} as posted")
    
    async def send_telegram_message(self, message_text, parse_mode=None):
        """Send a message to Telegram"""
        if not self.telegram_token or not self.channel_id:
            logger.warning("Telegram credentials not provided, skipping message")
            return False
        
        try:
            bot = Bot(token=self.telegram_token)
            kwargs = {
                'chat_id': self.channel_id,
                'text': message_text,
                'disable_web_page_preview': True
            }
            if parse_mode:  # Only add parse_mode if not None/empty
                kwargs['parse_mode'] = parse_mode
            message = await bot.send_message(**kwargs)
            logger.info("Sent message to Telegram")
            return True
        except Exception as e:
            logger.error(f"Error sending to Telegram: {str(e)}")
            return False
    
    def is_duplicate_job(self, job):
        """Check if a job with the same details has been posted before"""
        # Use a simple text file to store all job URLs that have been posted
        # This is the most reliable way to prevent duplicates
        posted_urls_file = "posted_job_urls.txt"
        
        # Create the file if it doesn't exist
        if not os.path.exists(posted_urls_file):
            with open(posted_urls_file, "w", encoding="utf-8") as f:
                f.write("# This file contains all job URLs that have been posted to Telegram\n")
        
        # Check if this job URL has been posted before
        job_url = job['apply_link']
        
        # Read all posted URLs
        with open(posted_urls_file, "r", encoding="utf-8") as f:
            posted_urls = f.read().splitlines()
        
        # If the URL is in the list, it's a duplicate
        if job_url in posted_urls:
            logger.info(f"Found duplicate job URL: {job_url}")
            return True
            
        # Also check for similar jobs by title, company, and location
        job_details_file = "job_details.json"
        posted_jobs = {}
        
        if os.path.exists(job_details_file):
            try:
                with open(job_details_file, "r", encoding="utf-8") as f:
                    posted_jobs = json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                posted_jobs = {}
        
        # Check all jobs in our records to find similar ones
        for key, stored_job in posted_jobs.items():
            # Check if title, company, and location match
            if (job['title'] == stored_job['title'] and 
                job['company'] == stored_job['company']):
                
                logger.info(f"Found duplicate job with same title and company: {job['title']} at {job['company']}")
                
                # Add this URL to the posted URLs file to prevent future duplicates
                with open(posted_urls_file, "a", encoding="utf-8") as f:
                    f.write(f"{job_url}\n")
                    
                return True
        
        # Not a duplicate, store it and return False
        self.store_job_details(job)
        
        # Add this URL to the posted URLs file
        with open(posted_urls_file, "a", encoding="utf-8") as f:
            f.write(f"{job_url}\n")
            
        return False
        
    def store_job_details(self, job):
        """Store job details in a JSON file for reference and duplicate checking"""
        job_details_file = "job_details.json"
        
        # Use the job URL as the unique key - this is the most reliable way to identify unique jobs
        job_key = job['apply_link']
        
        # Prepare job details with all available information
        job_details = {
            "title": job['title'],
            "company": job['company'],
            "location": job['location'],
            "experience": job.get('experience', 'Not specified'),
            "posted_date": job['posted_date'],
            "link": job['apply_link'],
            "job_id": job.get('job_id', ''),
            "timestamp": datetime.now().isoformat()
        }
        
        # Read existing data
        posted_jobs = {}
        if os.path.exists(job_details_file):
            try:
                with open(job_details_file, "r", encoding="utf-8") as f:
                    posted_jobs = json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                # If file is empty or invalid, start with empty dict
                posted_jobs = {}
        
        # Add new job
        posted_jobs[job_key] = job_details
        
        # Write back to file
        with open(job_details_file, "w", encoding="utf-8") as f:
            json.dump(posted_jobs, f, indent=2, ensure_ascii=False)
            
        logger.info(f"Stored job details for: {job['title']} at {job['company']}, {job['location']}")
        
    def encrypt_job_url(self, url):
        """Create a working encrypted URL for Naukri job listings"""
        import hashlib
        
        # Extract the job ID from the URL if possible
        import re
        # Updated regex pattern to match various Naukri job URL formats
        job_id_match = re.search(r'job-listings-.*?-(\d+)$', url)
        
        if job_id_match:
            # If we can extract the job ID, use it directly
            job_id = job_id_match.group(1)
            # Create a working URL format that Naukri supports
            return f"https://www.naukri.com/job-listings-{job_id}"
        else:
            # If we can't extract the job ID, return the original URL
            # This ensures the link will always work
            return url
        
    async def post_job_to_telegram(self, job):
        """Post a job to the Telegram channel"""
        # First check if this exact URL has been posted before
        posted_urls_file = "posted_job_urls.txt"
        
        # Counter file for tracking job posts for advertisement display
        counter_file = "job_post_counter.txt"
        
        # Create the files if they don't exist
        if not os.path.exists(posted_urls_file):
            with open(posted_urls_file, "w", encoding="utf-8") as f:
                f.write("# This file contains all job URLs that have been posted to Telegram\n")
                
        if not os.path.exists(counter_file):
            with open(counter_file, "w", encoding="utf-8") as f:
                f.write("0")
        
        # Read all posted URLs
        with open(posted_urls_file, "r", encoding="utf-8") as f:
            posted_urls = f.read().splitlines()
        
        # If the URL is in the list, it's a duplicate - skip it
        if job['apply_link'] in posted_urls:
            logger.info(f"Skipping duplicate job URL: {job['apply_link']}")
            return False
            
        # Also check for similar jobs using our improved method
        if self.is_duplicate_job(job):
            logger.info(f"Skipping duplicate job: {job['title']} at {job['company']}")
            return False
            
        # Encrypt the job URL
        encrypted_link = self.encrypt_job_url(job['apply_link'])
        logger.info(f"Original link: {job['apply_link']}")
        logger.info(f"Encrypted link: {encrypted_link}")
            
        # Format message to match the required format (plain text, no Markdown)
        import re as _re
        
        # Generate hashtags from job title
        title_words = _re.findall(r'[A-Za-z][a-zA-Z0-9]+', job['title'])
        hashtags = ' '.join([f"#{w}" for w in title_words if len(w) > 2])
        if not hashtags:
            hashtags = f"#{job.get('category', 'IT')}Jobs"
        
        experience = job.get('experience', 'Not specified')
        ctc = "NA"  # Not available from listing page
        
        message = (
            f"📌 {job['title']}\n\n"
            f"🏢 Company: {job['company']}\n"
            f"⏳ Experience: {experience}\n"
            f"📍 Location: {job['location']}\n"
            f"💰 CTC: {ctc}\n\n"
            f"{hashtags}\n\n"
            f"🔗 Apply Link: {encrypted_link}"
        )
        
        try:
            from advertisement import check_and_send_advertisement
            result = await self.send_telegram_message(message, parse_mode=None)
            if result:
                logger.info(f"Posted job to Telegram: {job['title']}")
                check_and_send_advertisement(self.telegram_token, self.channel_id)
            return result
        except Exception as e:
            logger.error(f"Error posting to Telegram: {str(e)}")
            return False
    
    def cleanup_job_files(self):
        """Clean up job storage files to prevent them from growing too large"""
        # Clean up posted_job_urls.txt if it gets too large
        posted_urls_file = "posted_job_urls.txt"
        if os.path.exists(posted_urls_file):
            with open(posted_urls_file, "r", encoding="utf-8") as f:
                urls = f.readlines()
            
            # If we have more than 1000 URLs, keep only the most recent 500
            if len(urls) > 1000:
                logger.info(f"Cleaning up {posted_urls_file} - keeping only the most recent 500 URLs")
                with open(posted_urls_file, "w", encoding="utf-8") as f:
                    f.write("# This file contains all job URLs that have been posted to Telegram\n")
                    f.writelines(urls[-500:])
        
        # Clean up job_details.json if it gets too large
        job_details_file = "job_details.json"
        if os.path.exists(job_details_file):
            try:
                with open(job_details_file, "r", encoding="utf-8") as f:
                    posted_jobs = json.load(f)
                
                # If we have more than 1000 jobs, keep only the most recent 500
                if len(posted_jobs) > 1000:
                    logger.info(f"Cleaning up {job_details_file} - keeping only the most recent 500 jobs")
                    # Sort jobs by timestamp (newest first)
                    sorted_jobs = sorted(posted_jobs.items(), 
                                        key=lambda x: x[1].get('timestamp', ''), 
                                        reverse=True)
                    
                    # Keep only the most recent 500 jobs
                    posted_jobs = dict(sorted_jobs[:500])
                    
                    # Write back to file
                    with open(job_details_file, "w", encoding="utf-8") as f:
                        json.dump(posted_jobs, f, indent=2, ensure_ascii=False)
            except (json.JSONDecodeError, FileNotFoundError):
                # If file is empty or invalid, ignore
                pass
    
    async def process_jobs(self):
        """Main process to scrape and post jobs"""
        try:
            # Clean up job files to prevent them from growing too large
            self.cleanup_job_files()
            # Scrape jobs
            logger.info("Starting job scraping")
            jobs = await self.scrape_jobs()
            
            # Save to database
            new_jobs_count = self.save_jobs_to_db(jobs)
            logger.info(f"Found {new_jobs_count} new jobs")
            
            # Get unposted jobs
            unposted_jobs = self.get_unposted_jobs()
            logger.info(f"Found {len(unposted_jobs)} unposted jobs")
            
            # Post only 1 job per run to avoid flooding the channel
            posted_count = 0
            for job in unposted_jobs:
                if posted_count >= 1:
                    break  # Only post 1 job per scheduled run
                success = await self.post_job_to_telegram(job)
                if success:
                    self.mark_job_as_posted(job['job_id'])
                    posted_count += 1
            
            logger.info(f"Job processing completed — posted {posted_count} job(s)")
        except Exception as e:
            logger.error(f"Error in process_jobs: {str(e)}")

async def main():
    """Main function to run the scraper"""
    # Configuration
    telegram_token = "8737613068:AAGtpmp32TVyz7YACORGYhNta89HJDg3HFg"
    channel_id = "@IT_Job_openings_Naukri"
    
    # Initialize scraper
    scraper = NaukriJobScraper(telegram_token, channel_id)
    
    try:
        # Run once
        await scraper.process_jobs()
        
        # Schedule to run every 1 minute
        while True:
            logger.info("Waiting for next scheduled run (1 minute)")
            await asyncio.sleep(60)  # 1 minute
            await scraper.process_jobs()
    except asyncio.CancelledError:
        logger.info("Task was cancelled")
    except Exception as e:
        logger.error(f"Error in main function: {str(e)}")
    finally:
        logger.info("Scraper shutdown complete")

if __name__ == "__main__":
    asyncio.run(main())