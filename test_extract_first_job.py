import asyncio
import logging
import os
import json
import threading
import sys
import re
import time
import random
import gc
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

async def send_job_to_matching_premium_users(job_title, message, telegram_token, job_experience=None, job_location=None, job_url=None, all_hashtags=None, all_skills=None):
    """
    Send job posts to premium users whose keywords match the post title or ANY extracted hashtags/skills,
    whose experience falls within the job post's experience range,
    and whose location preference matches the job location.
    """
    try:
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
        
        # Create bot instance using PREMIUM_TOKEN (so DMs are delivered from @Premium_Naukri_bot)
        bot_token = PREMIUM_TOKEN if PREMIUM_TOKEN else telegram_token
        bot = Bot(token=bot_token)
        
        # Clean job title for matching
        import re
        job_title_lower = (job_title or "").lower()
        clean_title = re.sub(r'[^a-zA-Z0-9\s\.\#\+\-]', ' ', job_title_lower)
        title_tokens = [w.strip() for w in clean_title.split() if len(w.strip()) >= 2]
        
        # Collect ALL hashtags and skills without '#' for filtering
        matchable_tags = set()
        if all_hashtags:
            for t in all_hashtags:
                clean_t = re.sub(r'[^a-zA-Z0-9]', '', t).lower().strip()
                if clean_t:
                    matchable_tags.add(clean_t)
        if all_skills:
            for s in all_skills:
                clean_s = s.lower().strip()
                if clean_s:
                    matchable_tags.add(clean_s)
                    matchable_tags.add(re.sub(r'[^a-zA-Z0-9]', '', clean_s))

        # Fallback to job_details.json if not passed directly
        if not matchable_tags and os.path.exists("job_details.json"):
            try:
                with open("job_details.json", "r", encoding="utf-8") as f:
                    all_details = json.load(f)
                    job_info = all_details.get(job_url, {})
                    if not job_info and job_title:
                        for u, d in all_details.items():
                            if d.get("title") == job_title:
                                job_info = d
                                break
                    for t in (job_info.get("all_hashtags") or job_info.get("hashtags") or []):
                        matchable_tags.add(re.sub(r'[^a-zA-Z0-9]', '', t).lower().strip())
                    for s in job_info.get("skills", []):
                        matchable_tags.add(s.lower().strip())
                        matchable_tags.add(re.sub(r'[^a-zA-Z0-9]', '', s.lower().strip()))
            except Exception:
                pass

        logger.info(f"Matchable skills/tags count: {len(matchable_tags)} -> {list(matchable_tags)[:8]}")
        
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
        logger.info(f"Job experience range: {min_exp}-{max_exp} yrs (from '{job_experience}')")
        job_loc_lower = (job_location or "").lower()
        
        # Track matched users for logging
        matched_users = []
        
        # Check each premium user
        for user_id, user_data in premium_users.items():
            if user_data.get("is_premium", False):
                preferences = user_data.get("preferences", {})
                user_keywords = preferences.get("job_keywords", "").lower()
                user_experience = preferences.get("experience", "0")
                user_location = preferences.get("location", "").lower()
                
                if not user_keywords:
                    continue
                
                user_min_exp, user_max_exp = parse_exp_range(user_experience)
                keywords_list = [k.strip().lower() for k in user_keywords.split(',') if k.strip()]
                
                # 1. Keyword & All-Tags Matching
                matching_keywords = []
                for kw in keywords_list:
                    kw_clean = re.sub(r'[^a-zA-Z0-9]', '', kw).lower()
                    # Check in title
                    if kw in clean_title or kw in job_title_lower:
                        matching_keywords.append(kw)
                    # Check in ALL extracted hashtags and skills (with '#' stripped)
                    elif any(kw == tag or kw_clean == tag or kw in tag or tag in kw for tag in matchable_tags if len(tag) >= 2):
                        matching_keywords.append(kw)
                    # Check in word tokens
                    elif any(kw == tok or tok.startswith(kw) for tok in title_tokens):
                        matching_keywords.append(kw)
                
                title_match = bool(matching_keywords)
                
                # 2. Experience Overlap Match
                experience_match = (user_min_exp <= max_exp) and (user_max_exp >= min_exp)
                
                # 3. Multi-Location Matching
                user_loc_list = [l.strip().lower() for l in user_location.split(',') if l.strip()]
                if not user_loc_list or "any" in user_loc_list or "all" in user_loc_list or "india" in user_loc_list:
                    location_match = True
                elif not job_loc_lower:
                    location_match = True
                elif "remote" in job_loc_lower and any("remote" in u for u in user_loc_list):
                    location_match = True
                else:
                    location_match = any(u_loc in job_loc_lower or job_loc_lower in u_loc for u_loc in user_loc_list)
                
                # Debug log
                logger.info(f"Checking user {user_id}: kw_match={title_match} ({matching_keywords}), exp_match={experience_match} ({user_min_exp}-{user_max_exp} vs {min_exp}-{max_exp}), loc_match={location_match}")
                
                if title_match and experience_match and location_match:
                    try:
                        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
                        apply_target = job_url if (job_url and job_url.startswith('http')) else (f"https://www.naukri.com{job_url}" if job_url else "https://www.naukri.com")
                        dm_keyboard = InlineKeyboardMarkup([
                            [InlineKeyboardButton("⚡ Quick Apply", url=apply_target)],
                            [InlineKeyboardButton("⚙️ VIP Preferences", url="https://t.me/Premium_Naukri_bot")]
                        ])
                        
                        matched_kw_text = ", ".join(matching_keywords)
                        personalized_message = (
                            "🔔 <b>NEW VIP MATCHING JOB ALERT</b>\n"
                            f"🎯 <b>Matched Skills:</b> <code>{matched_kw_text}</code> • <code>{user_experience} Yrs</code>\n\n"
                            f"{message}"
                        )
                        await bot.send_message(
                            chat_id=user_id,
                            text=personalized_message,
                            parse_mode='HTML',
                            reply_markup=dm_keyboard,
                            disable_web_page_preview=True
                        )
                        username = user_data.get('username') or str(user_id)
                        matched_users.append(f"{username} (skills: {matched_kw_text})")
                        logger.info(f"✅ Sent VIP alert to premium user {user_id} ({username})")
                    except Exception as e:
                        logger.error(f"Failed to send VIP alert to user {user_id}: {str(e)}")
        
        if matched_users:
            logger.info(f"🎉 Job '{job_title}' matched and delivered to {len(matched_users)} VIP users: {', '.join(matched_users)}")
        else:
            logger.info(f"No premium users matched all criteria for '{job_title}' ({job_experience})")
            
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
            logger.warning(f"No job cards found on page. Title: '{await page.title()}', URL: '{page.url}'")
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
        
        company_element = target_job.select_one('.comp-name, a.comp-name, .companyName, .company, [class*="company"], .subTitle, [class*="subTitle"], .companyInfo, [data-test="company-name"], [class*="comp"], [class*="org"], [itemprop="hiringOrganization"]')
        if not company_element and target_job.parent:
            company_element = target_job.parent.select_one('.comp-name, a.comp-name, .companyName, .company, [class*="company"], .subTitle, [class*="subTitle"], .companyInfo')
        company = company_element.text.strip() if company_element else "Top Tech Company"
        # Clean ratings/reviews from company name if merged
        company = re.split(r'\d+\.?\d*\s*Reviews|\d+\.?\d*\s*★', company)[0].strip()
        company = re.sub(r'\d+\.?\d*$', '', company).strip()
        if not company:
            company = "Top Tech Company"
        
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
        
        # Extract ALL skills & generate hashtags (Show max 3 in post, use ALL for VIP filter matching)
        skill_tags = target_job.select('.tag-li, .tags-gt li, [class*="tag"], [class*="skill"], .dot-gt, .has-descriptions li')
        all_skills = []
        for st in skill_tags:
            t = st.text.strip()
            if t and len(t) > 1 and len(t) < 40 and t not in all_skills:
                all_skills.append(t)
        
        # Build ALL hashtags for keyword matching
        all_hashtags = []
        for s in all_skills:
            tag = re.sub(r'[^a-zA-Z0-9]', '', s)
            if tag and f"#{tag}" not in all_hashtags:
                all_hashtags.append(f"#{tag}")
        
        if not all_hashtags:
            words = [w for w in re.split(r'[^a-zA-Z0-9]', title_clean) if len(w) > 2]
            for w in words:
                all_hashtags.append(f"#{w}")
                
        # Display ONLY max 3 hashtags in Telegram channel message
        display_hashtags = all_hashtags[:3]
        hashtag_str = " ".join(display_hashtags)
        
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
            "hashtags": display_hashtags,
            "all_hashtags": all_hashtags,
            "skills": all_skills,
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
                    
        # Send to matching premium VIP users (passes all extracted hashtags and skills)
        await send_job_to_matching_premium_users(
            title_clean, message, scraper.telegram_token, experience_clean,
            location_clean, job_url, all_hashtags=all_hashtags, all_skills=all_skills
        )
        return True
    except Exception as e:
        logger.error(f"Error in extract_and_process_job: {e}")
        return False


async def solve_recaptcha_if_present(page):
    """Detects and automatically clicks Google reCAPTCHA checkbox if present"""
    try:
        logger.info("Checking for Google reCAPTCHA challenge...")
        captcha_found = False
        
        # Check by frame_locator
        recaptcha_frame = page.frame_locator('iframe[src*="recaptcha"], iframe[title*="reCAPTCHA"]')
        anchor = recaptcha_frame.locator('#recaptcha-anchor, .recaptcha-checkbox-border, .recaptcha-checkbox')
        
        try:
            if await anchor.is_visible(timeout=5000):
                captcha_found = True
        except Exception:
            pass
            
        if not captcha_found:
            for frame in page.frames:
                if "recaptcha" in frame.url:
                    captcha_found = True
                    break

        if captcha_found:
            logger.info("🤖 Google reCAPTCHA challenge detected! Simulating human click on checkbox...")
            await asyncio.sleep(random.uniform(1.0, 2.0))
            
            # Click via frame locator
            try:
                await anchor.click(timeout=6000)
                logger.info("✅ Clicked '#recaptcha-anchor' via frame locator.")
            except Exception as _c_err:
                logger.warning(f"Frame locator click failed ({_c_err}), trying frame selector...")
                for frame in page.frames:
                    if "recaptcha" in frame.url:
                        cb = await frame.query_selector("#recaptcha-anchor, .recaptcha-checkbox-border, .recaptcha-checkbox")
                        if cb:
                            await cb.click()
                            logger.info("✅ Clicked checkbox via direct frame selector.")
                            break
            
            logger.info("Waiting 8s for reCAPTCHA verification & page reload...")
            await asyncio.sleep(8)
            
            return True
        else:
            logger.info("No reCAPTCHA challenge detected.")
    except Exception as e:
        logger.warning(f"reCAPTCHA check notice: {e}")
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
            
            await page.set_viewport_size({"width": 1366, "height": 768})
            
            desktop_user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0"
            await page.set_extra_http_headers({
                'Referer': 'https://www.google.com/search?q=naukri+jobs+india',
                'User-Agent': desktop_user_agent
            })
            
            # Step 1: Pre-warm session on homepage to establish Akamai / session cookies
            logger.info("Visiting homepage to initialize session...")
            try:
                await page.goto("https://www.naukri.com/", wait_until='domcontentloaded', timeout=20000)
                await asyncio.sleep(2)
            except Exception as e:
                logger.info(f"Homepage pre-visit: {e}")
            
            # Step 2: Navigate to IT Jobs search
            logger.info(f"Navigating to {job_url}...")
            await page.goto(job_url, wait_until='domcontentloaded', timeout=45000)
            
            # Step 3: Check for reCAPTCHA challenge
            await solve_recaptcha_if_present(page)
            
            page_title = await page.title()
            logger.info(f"Page loaded: '{page_title}' | URL: {page.url}")
            
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
                logger.warning(f"Waiting for job cards timed out. Current Title: '{await page.title()}'")
                # Retry reCAPTCHA solve in case it appeared during load
                if await solve_recaptcha_if_present(page):
                    try:
                        await page.wait_for_selector(card_selectors, timeout=15000)
                        logger.info("Job cards detected after reCAPTCHA solve!")
                    except Exception:
                        pass

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

    job_url = "https://www.naukri.com/it-jobs?src=gnbjobs_homepage_srch"
    scan_interval = 60  # seconds between scans
    
    while True:
        try:
            # 1. Trigger scan - browser is opened ONLY for the duration of this call
            await run_single_scan(scraper, job_url)
            gc.collect()

            # 2. Check scheduled advertisement interval (every 12 hours / 43200 seconds)
            if time.time() - last_ad_time >= 12 * 3600:
                try:
                    logger.info("Posting 12-hour scheduled advertisement to channel...")
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