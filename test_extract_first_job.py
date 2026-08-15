import asyncio
import logging
import os
import json
import threading
import sys
import re
import time
from datetime import datetime
from main import NaukriJobScraper
from telegram import Bot
from telegram.error import TimedOut, NetworkError
from premium_bot import run_premium_bot, load_premium_users
from advertisement import check_and_send_advertisement, send_advertisement_to_channel
import tempfile

# Use the actual token from the file
TELEGRAM_TOKEN = "8737613068:AAGtpmp32TVyz7YACORGYhNta89HJDg3HFg"

# Premium bot (t.me/Premium_Naukri_bot) - separate dedicated bot for user subscriptions
PREMIUM_TOKEN = "8762043028:AAEtOD5gkXQVkf8BTk4HYgukBQfiEp5HoK8"

# Enable unbuffered stdout so nohup.out prints in real-time
try:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(line_buffering=True)
except Exception:
    pass

# Configure logging with automatic flushing
class FlushingStreamHandler(logging.StreamHandler):
    def emit(self, record):
        super().emit(record)
        self.flush()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        FlushingStreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger('test_extract_first_job')

# Ensure a valid temp directory exists for Playwright on servers with restricted user Temp paths
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
SAFE_TMP = os.path.join(BASE_DIR, "playwright_tmp")
SAFE_BROWSERS = os.path.join(BASE_DIR, "pw-browsers")

try:
    os.makedirs(SAFE_TMP, exist_ok=True)
    os.makedirs(SAFE_BROWSERS, exist_ok=True)
    # Only set TEMP-related envs to avoid triggering browser re-downloads
    os.environ['TMP'] = SAFE_TMP
    os.environ['TEMP'] = SAFE_TMP
    os.environ['TMPDIR'] = SAFE_TMP
    # quick sanity check to verify temp path works
    fd, test_tmp_path = tempfile.mkstemp(dir=SAFE_TMP)
    os.close(fd)
    os.remove(test_tmp_path)
    logger.info(f"Playwright temp dir set to: {SAFE_TMP}")
    # Skipping PLAYWRIGHT_BROWSERS_PATH override to use default installed browsers
except Exception as env_err:
    logger.warning(f"Failed to initialize safe temp/browsers paths: {env_err}")

async def send_job_to_matching_premium_users(job_title, message, telegram_token, job_experience=None, job_location=None, job_url=None):
    """
    Send job posts to premium users whose job title partially matches the post title,
    whose experience falls within the job post's experience range,
    and whose location preference matches the job location
    
    Args:
        job_title (str): The title of the job post
        message (str): The formatted job post message
        telegram_token (str): Telegram bot token
        job_experience (str, optional): The experience range from the job post (e.g., "4-9 Yrs")
        job_location (str, optional): The location of the job post
        job_url (str, optional): The URL of the job post
    """
    try:
        # Add detailed debug logs for the job post
        logger.info("="*50)
        logger.info(f"PROCESSING JOB POST FOR MATCHING")
        logger.info(f"Job Title: '{job_title}'")
        logger.info(f"Job Experience: '{job_experience}'")
        logger.info("="*50)
        
        # Load premium users
        premium_users = load_premium_users()
        if not premium_users:
            logger.info("No premium users found")
            return
        
        logger.info(f"Found {len(premium_users)} premium users to check for matching")
        
        # Create bot instance
        bot = Bot(token=telegram_token)
        
        # Convert job title to lowercase for case-insensitive matching
        job_title_lower = job_title.lower()
        logger.info(f"Job title (lowercase): '{job_title_lower}'")
        
        # Helper function to parse any experience string or range
        def parse_exp_range(exp_str):
            if not exp_str:
                return 0, 100
            try:
                cleaned = str(exp_str).lower().replace("yrs", "").replace("yr", "").replace("years", "").replace("year", "").strip()
                if "+" in cleaned:
                    base = float(cleaned.replace("+", "").strip())
                    return int(base), 30
                if "-" in cleaned:
                    parts = cleaned.split("-")
                    return int(float(parts[0].strip())), int(float(parts[1].split()[0].strip()))
                if "to" in cleaned:
                    parts = cleaned.split("to")
                    return int(float(parts[0].strip())), int(float(parts[1].split()[0].strip()))
                val = int(float(cleaned))
                return max(0, val - 1), val + 1
            except Exception:
                return 0, 100
        
        # Parse job experience range
        min_exp, max_exp = parse_exp_range(job_experience)
        logger.info(f"Final job experience range: {min_exp}-{max_exp} years (from '{job_experience}')")
        
        # Track matched users for logging
        matched_users = []
        
        # Check each premium user
        for user_id, user_data in premium_users.items():
            # Only consider premium users
            if user_data.get("is_premium", False):
                # Get user's preferred job keywords, experience, and location
                preferences = user_data.get("preferences", {})
                user_keywords = preferences.get("job_keywords", "").lower()
                user_experience = preferences.get("experience", "0")
                user_location = preferences.get("location", "").lower()
                
                # Skip if user hasn't set any keywords
                if not user_keywords:
                    continue
                
                # Parse user experience range
                user_min_exp, user_max_exp = parse_exp_range(user_experience)
                
                # Split user keywords by comma
                keywords_list = [k.strip() for k in user_keywords.split(',') if k.strip()]
                
                # Check if any of the user's keywords match the job title or hashtags
                logger.info(f"Checking user {user_id} with preferences: keywords='{user_keywords}', experience range={user_min_exp}-{user_max_exp} yrs, location='{user_location}'")
                
                # Check if any keyword is in the job title
                title_match_full = any(keyword in job_title_lower for keyword in keywords_list)
                
                # Check if any keyword matches the beginning of a word in the job title
                words_in_job_title = job_title_lower.split()
                title_match_word = any(word.startswith(keyword) for keyword in keywords_list for word in words_in_job_title)
                
                # Extract hashtags from job details if available
                job_details_file = "job_details.json"
                job_details = {}
                
                # Try to load job details for the current job URL
                if os.path.exists(job_details_file):
                    try:
                        with open(job_details_file, 'r', encoding='utf-8') as f:
                            all_job_details = json.load(f)
                            job_details = all_job_details.get(job_url, {})
                            if not job_details and job_title:
                                for url, details in all_job_details.items():
                                    if details.get("title") == job_title:
                                        job_details = details
                                        break
                    except Exception as e:
                        logger.error(f"Error loading job details: {e}")
                
                # Get stored hashtags from job_details if available
                stored_hashtags = job_details.get("hashtags", [])
                logger.info(f"Job details found: {bool(job_details)}, Job URL: {job_url}, Title: {job_title}")
                
                matching_hashtags = []
                hashtags_match = False
                
                # Only use stored hashtags from job_details.json for matching
                if stored_hashtags:
                    for keyword in keywords_list:
                        keyword = keyword.lower().strip()
                        for tag in stored_hashtags:
                            tag_clean = tag.lower().replace('#', '').strip()
                            if keyword in tag_clean or tag_clean in keyword:
                                hashtags_match = True
                                matching_hashtags.append(tag)
                # If no stored hashtags, generate from job title
                else:
                    logger.info(f"  - No stored hashtags found, generating from job title")
                    generated_hashtags = [word.lower() for word in words_in_job_title if len(word) > 2]
                    # Add skills commonly associated with job titles
                    if "developer" in job_title_lower or "engineer" in job_title_lower:
                        generated_hashtags.extend(["programming", "coding", "development", "software"])
                    if "full" in job_title_lower and "stack" in job_title_lower:
                        generated_hashtags.extend(["frontend", "backend", "fullstack", "javascript", "react", "node"])
                    if "devops" in job_title_lower:
                        generated_hashtags.extend(["aws", "kubernetes", "docker", "terraform", "ansible", "cicd"])
                    if "data" in job_title_lower:
                        generated_hashtags.extend(["analytics", "bigdata", "python", "sql", "database"])
                    
                    # Match against generated hashtags
                    for keyword in keywords_list:
                        keyword = keyword.lower().strip()
                        for tag in generated_hashtags:
                            if keyword in tag or tag in keyword:
                                hashtags_match = True
                                matching_hashtags.append(tag)
                
                logger.info(f"  - Words in job title: {words_in_job_title}")
                logger.info(f"  - Stored hashtags: {stored_hashtags}")
                logger.info(f"  - Matching hashtags: {matching_hashtags}")
                logger.info(f"  - Hashtag match: {hashtags_match}")
                
                # Use any matching method
                title_match = title_match_full or title_match_word or hashtags_match
                
                # Range overlap check: user experience range overlaps with job experience range
                experience_match = (user_min_exp <= max_exp) and (user_max_exp >= min_exp)
                
                # Check for location match
                location_match = True  # Default to True if user hasn't specified a location
                if user_location and job_location:
                    # Convert job location to lowercase for case-insensitive matching
                    job_location_lower = job_location.lower()
                    # Check if user's location is in the job location
                    location_match = (user_location in job_location_lower) or ("remote" in user_location) or ("any" in user_location)
                    logger.info(f"  - Job location: '{job_location_lower}'")
                    logger.info(f"  - User location preference: '{user_location}'")
                    logger.info(f"  - Location match: {location_match}")
                
                # Add comprehensive debug logging
                logger.info(f"MATCH DETAILS for user {user_id}:")
                logger.info(f"  - Job title: '{job_title_lower}'")
                logger.info(f"  - User keywords: '{user_keywords}'")
                logger.info(f"  - Title match: {title_match}")
                logger.info(f"  - User experience range: {user_min_exp}-{user_max_exp} years")
                logger.info(f"  - Job experience range: {min_exp}-{max_exp} years")
                logger.info(f"  - Experience overlap match: {experience_match}")
                logger.info(f"  - OVERALL MATCH: {title_match and experience_match and location_match}")
                
                if title_match and experience_match and location_match:
                    try:
                        # Send personalized VIP message to the user with interactive buttons
                        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
                        apply_target = job_url if (job_url and job_url.startswith('http')) else (f"https://www.naukri.com{job_url}" if job_url else "https://www.naukri.com")
                        dm_keyboard = InlineKeyboardMarkup([
                            [InlineKeyboardButton("⚡ Quick Apply", url=apply_target)],
                            [InlineKeyboardButton("⚙️ VIP Preferences", url="https://t.me/Premium_Naukri_bot")]
                        ])
                        
                        personalized_message = (
                            "🔔 <b>NEW MATCHING JOB ALERT</b>\n"
                            f"🎯 <code>{user_keywords}</code> • <code>{user_experience} Yrs</code>\n\n"
                            f"{message}"
                        )
                        await bot.send_message(
                            chat_id=user_id,
                            text=personalized_message,
                            parse_mode='HTML',
                            reply_markup=dm_keyboard,
                            disable_web_page_preview=True
                        )
                        matched_users.append(f"{user_data.get('username')} (keywords: {user_keywords}, exp: {user_experience} yrs)")
                        logger.info(f"Sent job alert to premium user {user_id} with matching keywords '{user_keywords}' and experience {user_experience} yrs")
                    except Exception as e:
                        logger.error(f"Failed to send job alert to user {user_id}: {str(e)}")
        
        if matched_users:
            logger.info(f"Job post '{job_title}' ({job_experience}) matched and sent to {len(matched_users)} premium users: {', '.join(matched_users)}")
        else:
            logger.info(f"No premium users with matching job titles and experience for '{job_title}' ({job_experience})")
            
    except Exception as e:
        logger.error(f"Error in send_job_to_matching_premium_users: {str(e)}")


async def ensure_sorted_by_date(page):
    logger.info("Attempting to sort results by Date")
    try:
        sorted_by_date = False

        # Step 1: open the sort dropdown
        # Try CSS selectors first (fast path — works on Windows)
        sort_button = None
        for _sbsel in ['#filter-sort', '[id*="sort"]', 'div[class*="sort"]',
                       'span[class*="sort"]', '.filter-sort', '.sortby', '.sort-by']:
            try:
                sort_button = await page.query_selector(_sbsel)
                if sort_button:
                    logger.info(f"Found sort button: {_sbsel}")
                    break
            except Exception:
                pass

        if sort_button:
            txt = await sort_button.inner_text()
            if "date" in txt.lower():
                logger.info("Already sorted by Date")
                sorted_by_date = True
            else:
                await sort_button.click()
                logger.info("Clicked sort button, waiting for dropdown...")
                await asyncio.sleep(2)

        # Step 2: click 'Date' option (via JS — works even when CSS selector misses)
        if not sorted_by_date:
            clicked = await page.evaluate("""
                () => {
                    // If dropdown not open yet, find and click the sort trigger
                    // Look for element containing 'Sort by:' or whose leaf text is 'Relevance'
                    const allEls = Array.from(document.querySelectorAll('*'));
                    for (const el of allEls) {
                        const t = el.textContent.trim();
                        if ((t.startsWith('Sort by:') || t === 'Relevance') &&
                             el.children.length <= 2) {
                            el.click();
                            break;
                        }
                    }
                    // Now click 'Date' option
                    // 1. by data-id attribute
                    let dateEl = document.querySelector('a[data-id="filter-sort-f"]');
                    if (dateEl) { dateEl.click(); return 'data-id'; }
                    // 2. by exact text content
                    for (const el of Array.from(document.querySelectorAll('a, li, span, button'))) {
                        if (el.textContent.trim() === 'Date') {
                            el.click();
                            return 'text-Date';
                        }
                    }
                    return null;
                }
            """)
            if clicked:
                logger.info(f"Clicked Date sort via JS ({clicked}), waiting for page to re-sort...")
                await asyncio.sleep(2)
                sorted_by_date = True
            else:
                logger.warning("Could not find Date sort option — continuing with current order")

        logger.info(f"Sort by date: {sorted_by_date}")

    except Exception as e:
        logger.error(f"Error sorting by date: {str(e)}")


async def extract_and_process_job(page, scraper):
    """Extracts top job card from page and posts to Telegram + VIP matching users"""
    try:
        page_content = await page.content()
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(page_content, 'html.parser')
        
        job_cards = soup.select(
            '.srp-jobtuple-wrapper, '
            'article.jobTupleWrapper, '
            '.jobTuple, '
            '.job-tuple, '
            '[class*="srp-jobtuple"], '
            '[class*="NormalCard"], '
            'div[data-job-id], '
            '.SRPstyle__NormalCardStyle-sc-1rnhgwh-0, '
            'article[class*="job"], '
            'li[class*="job"], '
            'div[class*="jobTuple"], '
            'div[class*="job-card"], '
            'div[class*="JobCard"]'
        )
        
        if not job_cards:
            logger.warning("No job cards found on page")
            return False
            
        target_job = job_cards[0]
        title_element = target_job.select_one(
            '.title, .job-title, [class*="title"], '
            '.jobTupleHeader .title, h2.jobTitle, '
            'h2, h3, .srpHdr, .list-job-title'
        )
        if not title_element:
            logger.warning("Could not extract title")
            return False
            
        title = title_element.text.strip()
        
        company_element = target_job.select_one('.companyName, .company, [class*="company"], .subTitle, [class*="subTitle"], .comp-name, .companyInfo, [data-test="company-name"], [class*="comp"], [class*="org"], [itemprop="hiringOrganization"]')
        if not company_element and target_job.parent:
            company_element = target_job.parent.select_one('.companyName, .company, [class*="company"], .subTitle, [class*="subTitle"], .comp-name, .companyInfo')
        company = company_element.text.strip() if company_element else "Top Tech Company"
        
        exp_element = target_job.select_one('.experience, .exp, [class*="experience"], [class*="exp"], .expwdth, [data-test="experience"], span[class*="exp"]')
        experience = exp_element.text.strip() if exp_element else "0-5 Yrs"
        
        loc_element = target_job.select_one('.location, .loc, [class*="location"], [class*="loc"], .locWdth, [data-test="location"], span[class*="loc"]')
        location = loc_element.text.strip() if loc_element else "Pan India / Remote"
        
        sal_element = target_job.select_one('.salary, .sal, [class*="salary"], [class*="sal"], .ni-job-tuple-icon-srp-rupee, span[class*="sal"]')
        salary = sal_element.text.strip() if sal_element else "Best in Industry / As per Norms"
        
        date_element = target_job.select_one('.date, [class*="date"], .postedDate, [class*="posted"], [data-test="posted-date"]')
        posted_date = date_element.text.strip() if date_element else "Just Now"
        
        job_link_element = target_job.select_one('a[href*="/job-listings"], a[href*="/job-detail"], a.title, a')
        job_url = job_link_element.get('href', '') if job_link_element else ''
        if job_url and not job_url.startswith('http'):
            job_url = 'https://www.naukri.com' + job_url
            
        # Clean text
        title_clean = re.sub(r'[\r\n\t]+', ' ', title).strip()
        company_clean = re.sub(r'[\r\n\t]+', ' ', company).strip()
        experience_clean = re.sub(r'[\r\n\t]+', ' ', experience).strip()
        location_clean = re.sub(r'[\r\n\t]+', ' ', location).strip()
        ctc_clean = re.sub(r'[\r\n\t]+', ' ', salary).strip()
        if not ctc_clean or ctc_clean.upper() == 'NA':
            ctc_clean = "Best in Industry / As per Norms"
            
        encrypted_link = scraper.encrypt_job_link(job_url) if job_url else "https://www.naukri.com"
        
        # Extract skills & generate hashtags (Max 3 hashtags)
        skill_tags = target_job.select('.tag-li, .tags-gt li, [class*="tag"], [class*="skill"], .dot-gt')
        extracted_skills = []
        for st in skill_tags:
            t = st.text.strip()
            if t and len(t) > 1 and len(t) < 30:
                extracted_skills.append(t)
        
        hashtag_list = []
        for s in extracted_skills:
            tag = re.sub(r'[^a-zA-Z0-9]', '', s)
            if tag:
                hashtag_list.append(f"#{tag}")
            if len(hashtag_list) >= 3:
                break
        
        if not hashtag_list:
            words = [w for w in re.split(r'[^a-zA-Z0-9]', title_clean) if len(w) > 2]
            for w in words:
                hashtag_list.append(f"#{w}")
                if len(hashtag_list) >= 3:
                    break
                
        hashtag_list = hashtag_list[:3]
        hashtag_str = " ".join(hashtag_list)
        
        message = (
            f"💼 <b>Role:</b> <b>{title_clean}</b>\n\n"
            f"🏢 <b>Company:</b> {company_clean}\n"
            f"⏳ <b>Experience:</b> <code>{experience_clean}</code>\n"
            f"📍 <b>Location:</b> <code>{location_clean}</code>\n"
            f"💰 <b>Salary / CTC:</b> <code>{ctc_clean}</code>\n"
        )
        if hashtag_str:
            message += f"\n🏷️ {hashtag_str}\n"
            
        message += f"\n🔗 <b>Apply Link:</b> {encrypted_link}\n"
        message += "\n💡 <i>Get instant matching alerts:</i> @Premium_Naukri_bot"
        
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        job_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("⚡ Quick Apply", url=encrypted_link)],
            [InlineKeyboardButton("💎 Custom Job Alerts", url="https://t.me/Premium_Naukri_bot")]
        ])
        
        # Check duplicate URL
        posted_urls_file = "posted_job_urls.txt"
        if not os.path.exists(posted_urls_file):
            with open(posted_urls_file, "w", encoding="utf-8") as f:
                f.write("# Posted URLs\n")
                
        with open(posted_urls_file, "r", encoding="utf-8") as f:
            posted_urls = f.read().splitlines()
            
        if job_url in posted_urls:
            logger.info(f"Duplicate job URL already posted: {job_url}")
            return False
            
        job_details_file = "job_details.json"
        try:
            with open(job_details_file, "r", encoding="utf-8") as f:
                job_details = json.load(f)
        except Exception:
            job_details = {}
            
        for key, details in job_details.items():
            if (details.get("title") == title_clean and 
                details.get("company") == company_clean and
                details.get("location") == location_clean and
                details.get("experience") == experience_clean):
                logger.info(f"Duplicate job details already posted: {title_clean} at {company_clean}")
                return False
                
        # Save to job_details.json
        job_details[job_url] = {
            "title": title_clean,
            "company": company_clean,
            "location": location_clean,
            "experience": experience_clean,
            "posted_date": posted_date,
            "hashtags": hashtag_list,
            "timestamp": datetime.now().isoformat()
        }
        with open(job_details_file, "w", encoding="utf-8") as f:
            json.dump(job_details, f, indent=2)
            
        # Post to Telegram channel
        if scraper.telegram_token and scraper.channel_id:
            logger.info("Posting new job to Telegram channel...")
            result = await scraper.send_telegram_message(message, parse_mode='HTML', reply_markup=job_keyboard)
            if result:
                logger.info(f"✅ Successfully posted job to Telegram: {title_clean}")
                with open(posted_urls_file, "a", encoding="utf-8") as f:
                    f.write(f"{job_url}\n")
                    
        # Send to matching premium VIP users
        await send_job_to_matching_premium_users(title_clean, message, scraper.telegram_token, experience_clean, location_clean, job_url)
        return True
    except Exception as e:
        logger.error(f"Error in extract_and_process_job: {e}")
        return False


async def run_single_scan(scraper, job_url):
    """
    Opens browser ONLY when scanning is triggered, sorts by date, extracts the latest job,
    posts to Telegram channel and matching VIP users, and immediately closes the browser completely.
    """
    logger.info("=" * 60)
    logger.info("🔍 [SCAN TRIGGERED] Opening browser for job extraction...")
    logger.info("=" * 60)
    
    browser_cm = scraper.get_browser_context()
    try:
        async with browser_cm as context:
            page = await context.new_page()
            
            # Abort heavy assets (images, fonts, media) to cut bandwidth while preserving scripts/APIs
            try:
                await page.route(
                    "**/*.{png,jpg,jpeg,gif,webp,svg,ico,mp4,mp3,avi,wav,flv,mkv}",
                    lambda route: route.abort()
                )
            except Exception as _r_err:
                logger.warning(f"Could not set route filter: {_r_err}")
            
            await page.set_viewport_size({"width": 1366, "height": 768})
            
            desktop_user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0"
            await page.set_extra_http_headers({
                'Referer': 'https://www.google.com/search?q=naukri+jobs+india',
                'User-Agent': desktop_user_agent
            })
            
            logger.info(f"Navigating to {job_url}...")
            await page.goto(job_url, wait_until='domcontentloaded', timeout=40000)
            
            # Wait for job card elements to appear
            card_selectors = (
                '.srp-jobtuple-wrapper, article.jobTupleWrapper, .jobTuple, '
                '[class*="srp-jobtuple"], [class*="NormalCard"], div[data-job-id], '
                'article[class*="job"], div[class*="jobTuple"]'
            )
            try:
                await page.wait_for_selector(card_selectors, timeout=20000)
                logger.info("Job card elements detected on page.")
            except Exception:
                logger.warning("Job cards not detected within 20s, proceeding with page content check...")
            
            # Sort by date on page load
            await ensure_sorted_by_date(page)
            
            # Extract and post latest job
            logger.info("Extracting latest job...")
            await extract_and_process_job(page, scraper)
            
    except Exception as e:
        logger.error(f"Error during scan: {e}")
    finally:
        logger.info("🔒 [SCAN COMPLETED] Browser closed and memory released.")


async def main_scheduler():
    telegram_token = TELEGRAM_TOKEN
    channel_id = "@IT_Job_openings_Naukri"
    scraper = NaukriJobScraper(telegram_token, channel_id)

    last_ad_time = time.time()
    
    # 1. Post initial advertisement
    try:
        logger.info("Posting initial advertisement...")
        send_advertisement_to_channel(telegram_token, channel_id)
    except Exception as e:
        logger.error(f"Startup advertisement failed: {e}")

    job_url = "https://www.naukri.com/it-jobs?src=gnbjobs_homepage_srch&forceDesktop=true"
    scan_interval = 60  # seconds between scans
    
    while True:
        try:
            # 1. Trigger scan - browser is opened ONLY for the duration of this call
            await run_single_scan(scraper, job_url)
            gc.collect()

            # 2. Check scheduled advertisement interval (every 60 mins)
            if time.time() - last_ad_time >= 3600:
                try:
                    logger.info("Posting scheduled advertisement to channel...")
                    send_advertisement_to_channel(telegram_token, channel_id)
                    last_ad_time = time.time()
                except Exception as e:
                    logger.error(f"Advertisement posting failed: {e}")

            # 3. Wait until next scanning trigger (browser is completely closed during this sleep)
            logger.info(f"⏳ Next scan in {scan_interval}s. Browser is closed (idle).")
            await asyncio.sleep(scan_interval)

        except asyncio.CancelledError:
            logger.info("Scraper scheduler stopped")
            break
        except Exception as e:
            logger.error(f"Scheduler cycle exception: {e}. Retrying in 10s...")
            cleanup_zombies()
            await asyncio.sleep(10)


# Run the script with scheduling
if __name__ == "__main__":
    import gc
    import subprocess

    def cleanup_zombies():
        """Ensure no stranded background browser processes are taking memory on Linux"""
        if os.name != 'nt':
            try:
                subprocess.run(["pkill", "-9", "-f", "firefox"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                subprocess.run(["pkill", "-9", "-f", "playwright"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass

    # Terminate any duplicate running test_extract_first_job instances
    if os.name != 'nt':
        try:
            current_pid = os.getpid()
            out = subprocess.check_output(["pgrep", "-f", "test_extract_first_job.py"]).decode().split()
            for pid_str in out:
                p = int(pid_str.strip())
                if p != current_pid:
                    try:
                        os.kill(p, 9)
                    except Exception:
                        pass
        except Exception:
            pass

    # Clean up old zombie browser processes before starting
    cleanup_zombies()

    # Start premium bot in a background thread so it does not block the job scraper
    logger.info("Starting premium bot in background thread...")
    try:
        import asyncio as _asyncio

        def _run_bot():
            loop = _asyncio.new_event_loop()
            _asyncio.set_event_loop(loop)
            try:
                run_premium_bot(PREMIUM_TOKEN)
            except Exception as e:
                logger.error(f"Premium bot encountered error: {e}")
            finally:
                loop.close()

        bot_thread = threading.Thread(target=_run_bot, name="PremiumBotThread", daemon=True)
        bot_thread.start()
        logger.info("Premium bot started in background thread")
    except Exception as e:
        logger.warning(f"Failed to start premium bot thread: {e}. Continuing with scraper.")

    try:
        asyncio.run(main_scheduler())
    except KeyboardInterrupt:
        logger.info("Scheduler stopped by user")
        cleanup_zombies()
    except Exception as e:
        logger.error(f"Scheduler crashed: {str(e)}")
        cleanup_zombies()