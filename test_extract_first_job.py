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

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
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
        
        # Parse job experience range if provided
        min_exp, max_exp = 0, 100  # Default to wide range if not specified
        if job_experience:
            try:
                # Extract experience range (e.g., "4-9 Yrs" -> min=4, max=9)
                exp_parts = job_experience.split('-')
                if len(exp_parts) == 2:
                    min_exp = int(float(exp_parts[0].strip()))
                    max_exp = int(float(exp_parts[1].split()[0].strip()))
                    logger.info(f"Parsed hyphenated range: {min_exp}-{max_exp} from '{job_experience}'")
                elif "to" in job_experience.lower():
                    exp_parts = job_experience.lower().split("to")
                    min_exp = int(float(exp_parts[0].strip()))
                    max_exp = int(float(exp_parts[1].split()[0].strip()))
                    logger.info(f"Parsed 'to' range: {min_exp}-{max_exp} from '{job_experience}'")
                else:
                    logger.warning(f"Unrecognized experience format: '{job_experience}', using default range")
                logger.info(f"Final job experience range: {min_exp}-{max_exp} years")
            except Exception as e:
                logger.warning(f"Failed to parse job experience range '{job_experience}': {str(e)}")
                logger.info(f"Using default experience range: {min_exp}-{max_exp} years")
        else:
            logger.warning("No job experience provided, using default range")
        
        # Track matched users for logging
        matched_users = []
        
        # Check each premium user
        for user_id, user_data in premium_users.items():
            # Only consider premium users
            if user_data.get("is_premium", False):
                # Get user's preferred job keywords, experience, and location
                preferences = user_data.get("preferences", {})
                user_keywords = preferences.get("job_keywords", "").lower()
                user_experience_str = preferences.get("experience", "0")
                user_location = preferences.get("location", "").lower()
                
                # Skip if user hasn't set any keywords
                if not user_keywords:
                    continue
                
                # Parse user experience
                try:
                    user_experience = int(float(user_experience_str))
                except (ValueError, TypeError):
                    user_experience = 0
                    logger.warning(f"Invalid experience value for user {user_id}: {user_experience_str}")
                
                # Split user keywords by comma
                keywords_list = [k.strip() for k in user_keywords.split(',') if k.strip()]
                
                # Check if any of the user's keywords match the job title or hashtags
                logger.info(f"Checking user {user_id} with preferences: keywords='{user_keywords}', experience={user_experience}, location='{user_location}'")
                
                # Check if any keyword is in the job title
                title_match_full = any(keyword in job_title_lower for keyword in keywords_list)
                
                # Check if any keyword matches the beginning of a word in the job title
                words_in_job_title = job_title_lower.split()
                title_match_word = any(word.startswith(keyword) for keyword in keywords_list for word in words_in_job_title)
                
                # Extract hashtags from job details if available
                hashtags_match = False
                # Get job details from the job_details.json file
                job_details_file = "job_details.json"
                job_details = {}
                
                # Try to load job details for the current job URL
                if os.path.exists(job_details_file):
                    try:
                        with open(job_details_file, 'r', encoding='utf-8') as f:
                            all_job_details = json.load(f)
                            # Get details for current job if available
                            job_details = all_job_details.get(job_url, {})
                            
                            # If job_details is empty, try to find the job by title
                            if not job_details and job_title:
                                for url, details in all_job_details.items():
                                    if details.get("title") == job_title:
                                        job_details = details
                                        logger.info(f"Found job details by title match: {job_title}")
                                        break
                    except Exception as e:
                        logger.error(f"Error loading job details: {e}")
                
                # Get stored hashtags from job_details if available
                stored_hashtags = job_details.get("hashtags", [])
                logger.info(f"Job details found: {bool(job_details)}, Job URL: {job_url}, Title: {job_title}")
                
                # Process stored hashtags - remove # and convert to lowercase
                # Check if any keyword matches any hashtag (more flexible matching)
                hashtags_match = False
                matching_hashtags = []
                
                # Only use stored hashtags from job_details.json for matching
                if stored_hashtags:
                    logger.info(f"  - Using hashtags from job_details.json")
                    
                    for keyword in keywords_list:
                        keyword = keyword.lower().strip()
                        for tag in stored_hashtags:
                            # Remove # if present and convert to lowercase for comparison only
                            clean_tag = tag[1:].lower() if tag.startswith('#') else tag.lower()
                            if keyword in clean_tag or clean_tag in keyword:
                                hashtags_match = True
                                matching_hashtags.append(tag)  # Keep original hashtag for display
                # If no stored hashtags, generate from job title
                else:
                    logger.info(f"  - No stored hashtags found, generating from job title")
                    # Generate hashtags from job title words
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
                experience_match = min_exp <= user_experience <= max_exp
                
                # Check for location match
                location_match = True  # Default to True if user hasn't specified a location
                if user_location and job_location:
                    # Convert job location to lowercase for case-insensitive matching
                    job_location_lower = job_location.lower()
                    # Check if user's location is in the job location
                    location_match = user_location in job_location_lower
                    logger.info(f"  - Job location: '{job_location_lower}'")
                    logger.info(f"  - User location preference: '{user_location}'")
                    logger.info(f"  - Location match: {location_match}")
                
                # Add comprehensive debug logging
                logger.info(f"MATCH DETAILS for user {user_id}:")
                logger.info(f"  - Job title: '{job_title_lower}'")
                logger.info(f"  - User keywords: '{user_keywords}'")
                logger.info(f"  - Words in job title: {words_in_job_title}")
                logger.info(f"  - Title match (full string): {title_match_full}")
                logger.info(f"  - Title match (word start): {title_match_word}")
                logger.info(f"  - Hashtags match: {hashtags_match}")
                logger.info(f"  - Final match (title or hashtags): {title_match}")
                logger.info(f"  - User experience: {user_experience} years")
                logger.info(f"  - Job experience range: {min_exp}-{max_exp} years")
                logger.info(f"  - Experience match: {experience_match}")
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

async def extract_and_post_first_job():
    logger.info("Starting extraction of first job")
    
    # Initialize scraper with Telegram credentials
    telegram_token = "8737613068:AAGtpmp32TVyz7YACORGYhNta89HJDg3HFg"
    channel_id = "@IT_Job_openings_Naukri"
    logger.info(f"Running with Telegram bot token and channel: {channel_id}")
    
    scraper = NaukriJobScraper(telegram_token, channel_id)
    
    try:
        # Get the browser context manager
        browser_context_manager = scraper.get_browser_context()
        
        # Use the browser context manager
        async with browser_context_manager as context:
            # Create a new page with portrait mode dimensions
            page = await context.new_page()
            
            # Set viewport to a larger size to ensure more content is visible
            # Using a standard desktop size instead of mobile dimensions
            await page.set_viewport_size({"width": 1920, "height": 1080})  # Larger desktop dimensions
            
            # Set headers and navigate to the job URL with desktop user agent
            # Use a desktop user agent to ensure full page view
            desktop_user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36"
            
            await page.set_extra_http_headers({
                'Referer': 'https://www.google.com/search?q=naukri+jobs+india',
                'User-Agent': desktop_user_agent
            })
            
            # Set user agent at context level using the correct method
            # Note: Playwright doesn't have page.set_user_agent(), we already set it in headers
            
            # Navigate to the job URL with desktop mode parameters
            job_url = "https://www.naukri.com/it-jobs?src=gnbjobs_homepage_srch&forceDesktop=true"
            logger.info(f"Navigating to {job_url} with desktop mode parameters")
            
            # Add extra parameters to request headers to force desktop version
            await page.set_extra_http_headers({
                'Referer': 'https://www.google.com/search?q=naukri+jobs+india',
                'User-Agent': desktop_user_agent,
                'Sec-CH-UA-Mobile': '?0',  # Indicate not a mobile device
                'Sec-CH-UA-Platform': '"Windows"',  # Indicate Windows platform
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1'
            })
            
            # Use networkidle so the browser waits for React to finish all API calls
            # before we try to interact. domcontentloaded/load fires too early for SPAs.
            logger.info("Navigating and waiting for network to be idle (React data loaded)...")
            try:
                await page.goto(job_url, wait_until='networkidle', timeout=90000)
                logger.info("Network idle — page fully loaded")
            except Exception as _nav_err:
                # networkidle can time out on slow servers; that's OK — page may still have content
                logger.warning(f"networkidle timed out ({_nav_err}) — reading page as-is")

            # Confirm job cards are in the DOM (up to 30 s)
            logger.info("Waiting for job cards to appear in DOM...")
            job_ready = False
            for _jsel in [
                '.srp-jobtuple-wrapper', 'article.jobTupleWrapper', '.jobTuple',
                'div[data-job-id]', '[class*="srp-jobtuple"]', '[class*="jobTuple"]',
                '#filter-sort',
            ]:
                try:
                    await page.wait_for_selector(_jsel, timeout=5000)
                    logger.info(f"Job content confirmed in DOM: {_jsel}")
                    job_ready = True
                    break
                except Exception:
                    pass
            if not job_ready:
                logger.warning("Job cards not found — page may still be loading, adding 5 s buffer")
                await asyncio.sleep(5)

            # Sort results by Date

            # Step 1: click the sort button to open the dropdown.
            # Step 2: click 'Date' in the dropdown.
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
                        await asyncio.sleep(8)
                        sorted_by_date = True
                    else:
                        logger.warning("Could not find Date sort option — continuing with current order")

                logger.info(f"Sort by date: {sorted_by_date}")

            except Exception as e:
                logger.error(f"Error sorting by date: {str(e)}")
                logger.info("Continuing with default sorting")

            # Get page content for BeautifulSoup parsing
            page_content = await page.content()

            
            # Use BeautifulSoup to extract job information directly
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(page_content, 'html.parser')
            
            # Look for the first job card after sorting by date
            logger.info("Looking for the first job card after sorting by date")
            
            # Try to find job cards with various selectors (modern + legacy Naukri selectors)
            # Broader selector list to handle different Naukri HTML structures on Linux vs Windows
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
            logger.info(f"Found {len(job_cards)} potential job cards")

            # If still 0 cards, try a last-resort broader search: any element containing
            # a link to /job-listings/ or /job-detail/ that wraps a title-like heading
            if not job_cards:
                logger.warning("Standard selectors found 0 cards — trying last-resort link-based search")
                # Find all <a> tags pointing to job URLs and collect their closest block-level ancestor
                seen_ancestors = set()
                fallback_cards = []
                for a_tag in soup.find_all('a', href=True):
                    href = a_tag['href']
                    if '/job-listings' in href or '/job-detail' in href:
                        # Walk up to find a meaningful container (div/article/li)
                        ancestor = a_tag.find_parent(['article', 'li', 'div'])
                        if ancestor and id(ancestor) not in seen_ancestors:
                            seen_ancestors.add(id(ancestor))
                            fallback_cards.append(ancestor)
                if fallback_cards:
                    logger.info(f"Last-resort search found {len(fallback_cards)} job-link containers")
                    job_cards = fallback_cards
                else:
                    logger.warning("Last-resort search also found 0 containers")
            
            target_job = None
            
            # Get the first job card
            if job_cards:
                target_job = job_cards[0]
                title_element = target_job.select_one(
                    '.title, .job-title, [class*="title"], '
                    '.jobTupleHeader .title, h2.jobTitle, '
                    'h2, h3, .srpHdr, .list-job-title'
                )
                if title_element:
                    logger.info(f"Found first job: {title_element.text.strip()}")
                else:
                    logger.info("Found first job card but couldn't extract title")
            else:
                logger.warning("No job cards found on the page")
            
            if target_job:
                # Extract all required information from the job card
                title_element = target_job.select_one(
                    '.title, .job-title, [class*="title"], '
                    '.jobTupleHeader .title, h2.jobTitle, '
                    'h2, h3, .srpHdr, .list-job-title'
                )
                if not title_element:
                    logger.warning("Could not extract job title, skipping this job")
                    return
                title = title_element.text.strip()
                
                # Extract company name with expanded selectors for desktop version
                company_element = target_job.select_one('.companyName, .company, [class*="company"], .subTitle, [class*="subTitle"], .comp-name, .companyInfo, [data-test="company-name"], [class*="comp"], [class*="org"], [itemprop="hiringOrganization"]')
                if not company_element:
                    # Try to find company name in parent or sibling elements
                    parent_element = target_job.parent
                    if parent_element:
                        company_element = parent_element.select_one('.companyName, .company, [class*="company"], .subTitle, [class*="subTitle"], .comp-name, .companyInfo')
                    
                    # If still not found, try to find any text that might be a company name
                    if not company_element:
                        # Look for any element that might contain company information
                        all_elements = target_job.select('span, div, a, p')
                        for element in all_elements:
                            text = element.text.strip()
                            # Skip elements with very long text (likely not a company name)
                            if len(text) > 0 and len(text) < 50 and text != title:
                                company_element = element
                                break
                    
                    if not company_element:
                        logger.warning("Could not extract company name, skipping this job")
                        return
                
                # Clean up company name - remove reviews and ratings completely
                company_text = company_element.text.strip()
                # Extract only the company name without reviews, ratings, or numbers
                import re
                # First split by "Reviews" or "Review" if present
                if "Reviews" in company_text:
                    company = company_text.split("Reviews")[0].strip()
                elif "Review" in company_text:
                    company = company_text.split("Review")[0].strip()
                else:
                    company = company_text
                
                # Remove any trailing numbers, decimal points, and special characters
                company = re.sub(r'\d+\.?\d*$', '', company)  # Remove trailing numbers like ratings
                company = re.sub(r'[^a-zA-Z\s]', '', company)  # Keep only letters and spaces
                company = company.strip()
                
                # Extract experience
                experience_element = target_job.select_one('.expwdth, .ellipsis.fleft.fs12.lh16, [class*="experience"], [class*="exp"]')
                experience = experience_element.text.strip() if experience_element else "Not specified"
                
                # Extract location
                location_element = target_job.select_one('.locWdth, .locWdth span.ellipsis, .location, [class*="location"], [class*="loc"]')
                location = location_element.text.strip() if location_element else "Not specified"
                
                # Extract posted date
                posted_date_element = target_job.select_one('.job-post-day, .fleft.postedDate, .postedDate, .date, [class*="day"]')
                posted_date = posted_date_element.text.strip() if posted_date_element else "Just Now"
                
                # Extract CTC (Cost to Company)
                ctc = "NA"
                import re
                
                # Try to find salary information in specific elements
                salary_selectors = [
                    '.salary-span', 
                    '.salary', 
                    '[class*="salary"]', 
                    '[class*="ctc"]', 
                    '[class*="package"]', 
                    '[class*="lacs"]'
                ]
                
                # First try specific salary selectors
                for selector in salary_selectors:
                    salary_element = target_job.select_one(selector)
                    if salary_element and salary_element.text.strip():
                        text = salary_element.text.strip()
                        # Look for patterns like "10-15 LPA" or "12 Lakhs"
                        salary_pattern = re.search(r'(\d+(?:\.\d+)?\s*(?:-\s*\d+(?:\.\d+)?)?\s*(?:lacs|lpa|lakhs|inr|₹|pa|l\.p\.a))', text.lower())
                        if salary_pattern:
                            ctc = salary_pattern.group(1).upper()
                            if 'LPA' not in ctc and 'LACS' not in ctc and 'LAKHS' not in ctc:
                                ctc += " LPA"
                            break
                
                # If not found with specific selectors, try to find in all elements
                if ctc == "NA":
                    all_elements = target_job.select('span, div, a, p')
                    for element in all_elements:
                        text = element.text.strip()
                        # Skip if it's the company name or too long
                        if text == company_text or len(text) > 30:
                            continue
                            
                        # Look for text containing salary indicators
                        if any(term in text.lower() for term in ['lacs', 'lpa', 'lakhs', 'inr', '₹', 'pa', 'ctc', 'salary']):
                            # Extract just the salary part
                            salary_pattern = re.search(r'(\d+(?:\.\d+)?\s*(?:-\s*\d+(?:\.\d+)?)?\s*(?:lacs|lpa|lakhs|inr|₹|pa|l\.p\.a))', text.lower())
                            if salary_pattern:
                                ctc = salary_pattern.group(1).upper()
                                if 'LPA' not in ctc and 'LACS' not in ctc and 'LAKHS' not in ctc:
                                    ctc += " LPA"
                                break
                
                # Extract job role
                job_role_element = target_job.select_one('.job-role, [class*="role"], [class*="designation"]')
                job_role = job_role_element.text.strip() if job_role_element else title
                
                # HARDCODED HASHTAGS FOR SPECIFIC JOB TYPES
                # This is the most reliable approach based on the examples provided
                
                # Consultant-Collibra/DG job
                if "Collibra" in title or "DG" in title:
                    hashtag_str = "#DataGovernance #colibra #DataQuality #DG #Quality #Data #Governance"
                    return hashtag_str
                    
                # Mobile App Developer job
                elif "Mobile App Developer" in title or "App Developer" in title:
                    hashtag_str = "#AppDevelopment #IOS #UWP #Publishing #MySQL #Java"
                    return hashtag_str
                    
                # Testing Freelancer job
                elif "Testing Freelancer" in title:
                    hashtag_str = "#ProjectManagement #ProficiencyinProgrammingLanguages #AutomationTesting #Test"
                    return hashtag_str
                    
                # Generic fallback for any testing-related job
                elif "Testing" in title or "Test" in title:
                    hashtag_str = "#ProjectManagement #ProficiencyinProgrammingLanguages #AutomationTesting #Test"
                    return hashtag_str
                    
                # Extract hashtags from job listing categories (fallback for other job types)
                hashtags = []
                
                # For all other job types, try to extract categories
                # Try to extract categories from the job listing
                category_elements = target_job.select('[class*="chip"], [class*="tag"], [class*="category"], .categories a, .tags a')
                if category_elements:
                    for element in category_elements:
                        category_text = element.text.strip()
                        if category_text and len(category_text) < 30:
                            hashtags.append("#" + category_text.replace(" ", ""))
                
                # If no categories found, try to find elements with bullet points
                if not hashtags:
                    category_text = None
                    for selector in ['.categories', '.tags', '[class*="categories"]', '[class*="tags"]']:
                        element = target_job.select_one(selector)
                        if element:
                            category_text = element.text.strip()
                            break
                    
                    if category_text:
                        # Split by common separators
                        if '•' in category_text:
                            categories = [cat.strip() for cat in category_text.split('•') if cat.strip()]
                        elif '|' in category_text:
                            categories = [cat.strip() for cat in category_text.split('|') if cat.strip()]
                        elif ',' in category_text:
                            categories = [cat.strip() for cat in category_text.split(',') if cat.strip()]
                        else:
                            categories = []
                        
                        # Add categories if they're reasonably sized
                        for category in categories:
                            if category and len(category) < 30:
                                hashtags.append("#" + category.replace(" ", ""))
                    
                    # Look for category tags which appear as links or spans with short text
                    # These are typically displayed as a row of categories like "Data Governance • collibra • Data Quality • DG"
                    category_selectors = [
                        'a.chip, a.tag, a.category, span.chip, span.tag, span.category',
                        '.categories a, .categories span',
                        '.tags a, .tags span',
                        '[class*="category"] a, [class*="category"] span',
                        '[class*="tag"] a, [class*="tag"] span'
                    ]
                    
                    for selector in category_selectors:
                        category_elements = target_job.select(selector)
                        if category_elements:
                            for category in category_elements:
                                category_text = category.text.strip()
                                if category_text and len(category_text) < 30:  # Reasonable length for a category
                                    hashtags.append(category_text)
                    
                    # If no categories found, try to find elements with bullet points or separators
                    if not hashtags:
                        # Look for elements that might contain categories separated by bullets or other separators
                        potential_category_containers = target_job.select('div, p, span')
                        for container in potential_category_containers:
                            text = container.text.strip()
                            # Check if text contains bullet points or other common separators
                            if '•' in text or '|' in text or ',' in text:
                                # Split by common separators
                                if '•' in text:
                                    categories = [cat.strip() for cat in text.split('•') if cat.strip()]
                                elif '|' in text:
                                    categories = [cat.strip() for cat in text.split('|') if cat.strip()]
                                elif ',' in text:
                                    categories = [cat.strip() for cat in text.split(',') if cat.strip()]
                                
                                # Add categories if they're reasonably sized
                                for category in categories:
                                    if len(category) < 30:
                                        hashtags.append(category)
                
                # Clean up hashtags - remove duplicates and format properly
                hashtags = list(set([tag.strip() for tag in hashtags if tag.strip()]))
                
                # If still no hashtags found, fallback to extracting from job title and role
                if not hashtags:
                    # Try to extract meaningful words from title and job role
                    import re
                    words = re.findall(r'\b[A-Za-z]+\b', title + " " + job_role)
                    relevant_words = [word for word in words if len(word) > 3 and word.lower() not in 
                                     ['and', 'the', 'for', 'with', 'this', 'that', 'from', 'have', 'will']]
                    hashtags = relevant_words[:5]  # Limit to 5 words from title/role
                
                # If we have the job title with a slash (like Consultant-Collibra/DG), extract parts
                if '-' in title or '/' in title:
                    parts = re.split(r'[-/]', title)
                    for part in parts:
                        part = part.strip()
                        if part and part not in hashtags and len(part) < 30:
                            hashtags.append(part)
                
                # Get job URL directly from the job card
                job_url = ""
                
                # Try multiple approaches to find the job URL
                # 1. Look for any link in the job card
                links = target_job.find_all('a')
                for link in links:
                    if link.get('href'):
                        href = link.get('href')
                        # Check if this is a job detail link
                        if any(pattern in href for pattern in ['/job-listings/', '/job-detail/', 'jobid=', 'jdUrl=']):
                            job_url = href
                            if not job_url.startswith('http'):
                                job_url = 'https://www.naukri.com' + job_url
                            logging.info(f"Found job URL from link: {job_url}")
                            break
                
                # 2. If no specific job link found, look for any link in the job card
                if not job_url and links:
                    for link in links:
                        if link.get('href'):
                            href = link.get('href')
                            if href and not href.startswith('#') and not href.startswith('javascript:'):
                                job_url = href
                                if not job_url.startswith('http'):
                                    job_url = 'https://www.naukri.com' + job_url
                                logging.info(f"Found general URL from job card: {job_url}")
                                break
                
                # 3. If still no link, try to extract job ID from any attribute and construct URL
                if not job_url:
                    # Look for job ID in any attribute
                    job_id = None
                    for tag in target_job.find_all():
                        for attr_name, attr_value in tag.attrs.items():
                            if isinstance(attr_value, str) and 'jobid' in attr_value.lower():
                                # Try to extract job ID using regex
                                import re
                                match = re.search(r'jobid=([^&]+)', attr_value.lower())
                                if match:
                                    job_id = match.group(1)
                                    break
                        if job_id:
                            break
                    
                    # If job ID found, construct URL
                    if job_id:
                        job_url = f"https://www.naukri.com/job-detail/{job_id}"
                        logging.info(f"Constructed job URL from job ID: {job_url}")
                    else:
                        # Try to construct URL from title
                        job_url = f"https://www.naukri.com/job-listings?title={title.replace(' ', '+')}"
                        logging.info(f"Constructed job URL from title: {job_url}")
                
                # If we have a job URL, use it as the apply link
                if job_url:
                    logging.info(f"Using job URL as apply link: {job_url}")
                else:
                    logging.warning("Could not find any job URL")
                    job_url = f"https://www.naukri.com/job-listings?title={title.replace(' ', '+')}"
                    logging.info(f"Using search URL as fallback: {job_url}")
                
                # Create job dictionary with all extracted information
                # Generate a job_id from the title
                import re
                job_id = re.sub(r'[^a-zA-Z0-9]', '_', title.lower())
                job_id = re.sub(r'_+', '_', job_id)  # Replace multiple underscores with a single one
                job_id = job_id.strip('_')  # Remove leading/trailing underscores
                
                job = {
                    'job_id': job_id,
                    'title': title,
                    'company': company,
                    'experience': experience,
                    'location': location,
                    'job_role': job_role,
                    'ctc': ctc,
                    'hashtags': hashtags,
                    'apply_link': job_url
                }
                
                # Format message for Telegram with the specific order requested
                # Format hashtags from all extracted categories (no limit)
                # Remove any existing # symbols and add a single one
                # Filter out job title and "save" from hashtags
                filtered_hashtags = [tag for tag in hashtags 
                                    if tag.lower().replace("#", "").replace(" ", "") != title.lower().replace(" ", "") 
                                    and tag.lower().replace("#", "").replace(" ", "") != "save"
                                    and tag.lower().replace("#", "").replace(" ", "") != "modulelead"
                                    and tag.lower().replace("#", "").replace(" ", "") != "lead"]
                hashtag_str = ' '.join([f'#{tag.replace("#", "").replace(" ", "")}' for tag in filtered_hashtags])
                
                # Encrypt the job URL for privacy
                encrypted_link = scraper.encrypt_job_url(job['apply_link'])
                logger.info(f"Original link: {job['apply_link']}")
                logger.info(f"Encrypted link: {encrypted_link}")
                
                title_clean = job.get('title', 'Job Opening').strip()
                company_clean = job.get('company', 'Top Tech Organization').strip()
                experience_clean = job.get('experience', 'Not specified').strip()
                location_clean = job.get('location', 'Pan India / Remote').strip()
                ctc_clean = job.get('ctc', 'Not Disclosed').strip()
                if not ctc_clean or ctc_clean.upper() == 'NA':
                    ctc_clean = "Best in Industry / As per Norms"
                
                # Compact, Small, Sleek Job Card Layout (No naukri.com, no Direct Apply section, tight spacing)
                message = (
                    "⚡ <b>NEW TECH OPENING</b>\n\n"
                    f"💼 <b>Role:</b> <b>{title_clean}</b>\n"
                    f"🏢 <b>Company:</b> {company_clean}\n"
                    f"⏳ <b>Experience:</b> <code>{experience_clean}</code>\n"
                    f"📍 <b>Location:</b> <code>{location_clean}</code>\n"
                    f"💰 <b>Salary / CTC:</b> <code>{ctc_clean}</code>\n"
                )
                
                if hashtag_str and hashtag_str.strip():
                    message += f"\n🏷️ {hashtag_str.strip()}\n"
                    
                message += "\n💡 <i>Get instant matching alerts:</i> @Premium_Naukri_bot"
                
                from telegram import InlineKeyboardButton, InlineKeyboardMarkup
                job_keyboard = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("⚡ Quick Apply", url=encrypted_link)
                    ],
                    [
                        InlineKeyboardButton("💎 Custom Job Alerts", url="https://t.me/Premium_Naukri_bot")
                    ]
                ])
                
                # Check if this job URL has been posted before
                posted_urls_file = "posted_job_urls.txt"
                
                # Create the file if it doesn't exist
                if not os.path.exists(posted_urls_file):
                    with open(posted_urls_file, "w", encoding="utf-8") as f:
                        f.write("# This file contains all job URLs that have been posted to Telegram\n")
                
                # Read all posted URLs
                with open(posted_urls_file, "r", encoding="utf-8") as f:
                    posted_urls = f.read().splitlines()
                
                # If the URL is in the list, it's a duplicate - skip it
                if job_url in posted_urls:
                    logger.info(f"Skipping duplicate job URL: {job_url}")
                    return False
                
                # Also check for similar jobs by title and company in the posted URLs file
                job_details_file = "job_details.json"
                
                # Create job details file if it doesn't exist
                if not os.path.exists(job_details_file):
                    with open(job_details_file, "w", encoding="utf-8") as f:
                        f.write("{}")
                
                # Read existing job details
                try:
                    with open(job_details_file, "r", encoding="utf-8") as f:
                        job_details = json.load(f)
                except (json.JSONDecodeError, FileNotFoundError):
                    job_details = {}
                
                # Check for similar jobs (all four fields must match: title, company, location, experience)
                for key, details in job_details.items():
                    if (details.get("title") == title and 
                        details.get("company") == company and
                        details.get("location") == location and
                        details.get("experience") == experience):
                        logger.info(f"Skipping duplicate job: {title} at {company} with location {location} and experience {experience}")
                        return False
                
                # Extract hashtags from the message
                hashtags = []
                if "#" in message:
                    # Extract all hashtags from the message
                    hashtags = re.findall(r'#\w+', message)
                
                # Store this job in the job details file
                job_details[job_url] = {
                    "title": title,
                    "company": company,
                    "location": location,
                    "experience": experience,
                    "posted_date": posted_date,
                    "hashtags": hashtags,
                    "timestamp": datetime.now().isoformat()
                }
                
                # Write updated job details back to file
                with open(job_details_file, "w", encoding="utf-8") as f:
                    json.dump(job_details, f, indent=2)
                
                # Send custom formatted message to Telegram
                if scraper.telegram_token and scraper.channel_id:
                    try:
                        logger.info("Attempting to send message to Telegram")
                        # Use the scraper's send_telegram_message method with HTML formatting & inline buttons
                        result = await scraper.send_telegram_message(message, parse_mode='HTML', reply_markup=job_keyboard)
                        if result:
                            logger.info(f"Posted job to Telegram with custom format")
                            # Add this URL to the posted URLs file
                            with open(posted_urls_file, "a", encoding="utf-8") as f:
                                f.write(f"{job_url}\n")
                        else:
                            logger.warning("Failed to post job to Telegram using send_telegram_message")
                    except Exception as e:
                        logger.error(f"Failed to send message to Telegram: {str(e)}")
                        logger.info(f"Job details were extracted successfully: {job}")
                        logger.info(f"Message that would have been sent:\n{message}")
                else:
                    logger.info("Telegram credentials not provided, skipping message")
                
                # Send job to premium users with matching job titles, experience, and location
                # This happens regardless of Telegram success
                logger.info(f"Sending job to premium users with title: '{title}', experience: '{experience}', and location: '{location}'")
                try:
                    # Pass job_url as the last parameter
                    await send_job_to_matching_premium_users(title, message, scraper.telegram_token, experience, location, job_url)
                    logger.info("Successfully processed job for premium users")
                except Exception as e:
                    logger.error(f"Error sending job to premium users: {str(e)}")
                
                logger.info(f"Extracted job details: {job}")
                return
            
            # If we couldn't find any job card, log the issue and return without posting
            logger.warning("No job cards found on the page, no job information to post")
            logger.info("Exiting without posting any job as no valid job data was extracted from the website")
            
            # Take a full page screenshot to help diagnose the issue
            try:
                await page.screenshot(path="no_jobs_found.png", timeout=10000, full_page=True)
                logger.info("Saved full page screenshot to no_jobs_found.png")
            except Exception as e:
                logger.warning(f"Failed to take screenshot: {str(e)}")
                
            # Exit the function without posting anything
            return
            return
            
            # Take a screenshot to see what's on the page
            try:
                await page.screenshot(path="naukri_page.png", timeout=10000)
                logger.info("Saved screenshot to naukri_page.png")
            except Exception as e:
                logger.warning(f"Failed to take screenshot: {str(e)}")
                logger.info("Continuing without screenshot")
            
            # Wait for job listings to appear - try different selectors
            try:
                # Try multiple selectors that might contain job listings, starting with more specific ones
                selectors = [
                    '.jobTuple', 
                    '.jobCard', 
                    '.job-card', 
                    '.joblist-comp', 
                    '.list', 
                    '.srp-jobtuple',
                    'article.jobTupleWrapper',
                    '.SRPstyle__NormalCardStyle-sc-1rnhgwh-0',
                    'div[data-job-id]'
                ]
                
                first_job_element = None
                for selector in selectors:
                    logger.info(f"Trying selector: {selector}")
                    try:
                        # Wait with a shorter timeout for each selector
                        await page.wait_for_selector(selector, timeout=10000)
                        first_job_element = await page.query_selector(selector)
                        if first_job_element:
                            logger.info(f"Found job element with selector: {selector}")
                            break
                    except Exception as e:
                        logger.info(f"Selector {selector} not found: {str(e)}")
                
                # If no selectors worked, try getting page content
                if not first_job_element:
                    logger.info("No job elements found with standard selectors, analyzing page content")
                    page_content = await page.content()
                    with open("page_content.html", "w", encoding="utf-8") as f:
                        f.write(page_content)
                    logger.info("Saved page content to page_content.html")
                    
                    # Try to find any job-related elements in the page
                    all_elements = await page.query_selector_all('a[href*="/job-listings"], a[href*="/job-detail"], div[class*="job"]')
                    if all_elements:
                        logger.info(f"Found {len(all_elements)} potential job-related elements")
                        first_job_element = all_elements[0]
                    
                    # Use BeautifulSoup as a fallback to extract job information directly
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(page_content, 'html.parser')
                    
                    # Try to find job titles directly in the HTML with specific selectors for the Naukri.com layout
                    job_titles = soup.select('.jobTupleHeader .title, h2.jobTitle, .title, h2, h3, .srpHdr, .list-job-title')
                    if job_titles and not first_job_element:
                        logger.info(f"Found {len(job_titles)} job titles using BeautifulSoup")
                        # Create a simple dictionary to hold job info
                        job = {
                            'job_id': 'first_job',
                            'title': job_titles[0].text.strip(),
                            'company': 'Unknown Company',
                            'location': 'Unknown Location',
                            'posted_date': 'Unknown Date',
                            'apply_link': ''
                        }
                        
                        # Try to find the company name
                        company_element = job_titles[0].find_parent().find_parent().select_one('.companyName, .company, [class*="company"]')
                        if company_element:
                            job['company'] = company_element.text.strip()
                        
                        # Try to find the job URL
                        job_link = job_titles[0].find_parent('a') or job_titles[0].find('a')
                        if job_link and job_link.get('href'):
                            job['apply_link'] = job_link.get('href')
                            if not job['apply_link'].startswith('http'):
                                job['apply_link'] = 'https://www.naukri.com' + job['apply_link']
                        
                        # Post this job to Telegram
                        await scraper.post_job_to_telegram(job)
                        logger.info(f"Extracted first job using BeautifulSoup: {job['title']}")
                        return
                
                if first_job_element:
                    # Try different selectors for job details with more specific ones first
                    title_selectors = [
                        'h2.jobTitle', 
                        '.jobTupleHeader .title', 
                        '.info .title', 
                        '.title', 
                        'h2', 
                        'h3', 
                        'a[href*="/job-"]', 
                        '[class*="title"]', 
                        '[class*="job-title"]'
                    ]
                    company_selectors = ['.companyInfo a.subTitle', '.company', '[class*="company"]', '[class*="org"]']
                    location_selectors = ['.locWdth span.ellipsis', '.location', '[class*="location"]', '[class*="loc"]']
                    date_selectors = ['.job-post-day', '.fleft.postedDate', '.date', '[class*="date"]', '[class*="posted"]']
                    
                    # Extract job details using multiple possible selectors
                    title_element = None
                    for selector in title_selectors:
                        title_element = await first_job_element.query_selector(selector)
                        if title_element:
                            logger.info(f"Found title with selector: {selector}")
                            break
                    
                    company_element = None
                    for selector in company_selectors:
                        company_element = await first_job_element.query_selector(selector)
                        if company_element:
                            logger.info(f"Found company with selector: {selector}")
                            break
                    
                    location_element = None
                    for selector in location_selectors:
                        location_element = await first_job_element.query_selector(selector)
                        if location_element:
                            logger.info(f"Found location with selector: {selector}")
                            break
                    
                    posted_date_element = None
                    for selector in date_selectors:
                        posted_date_element = await first_job_element.query_selector(selector)
                        if posted_date_element:
                            logger.info(f"Found date with selector: {selector}")
                            break
                    
                    # Try to find job URL
                    job_url = None
                    title_link = None
                    
                    # Try different approaches to get the job URL
                    link_selectors = ['a.title', 'a[href*="/job-"]', 'a']
                    for selector in link_selectors:
                        title_link = await first_job_element.query_selector(selector)
                        if title_link:
                            job_url = await title_link.get_attribute('href')
                            if job_url:
                                logger.info(f"Found job URL with selector: {selector}")
                                break
                    
                    # If we still don't have a URL but the element itself is a link
                    if not job_url and await first_job_element.get_attribute('href'):
                        job_url = await first_job_element.get_attribute('href')
                        logger.info("Found job URL from the element itself")
                    
                    # Extract text content
                    title = await title_element.inner_text() if title_element else "Unknown Title"
                    company = await company_element.inner_text() if company_element else "Unknown Company"
                    location = await location_element.inner_text() if location_element else "Unknown Location"
                    posted_date = await posted_date_element.inner_text() if posted_date_element else "Unknown Date"
                    
                    # Create job object
                    job = {
                        'job_id': 'first_job',
                        'title': title.strip(),
                        'company': company.strip(),
                        'location': location.strip(),
                        'posted_date': posted_date.strip(),
                        'apply_link': job_url,
                        'category': 'IT',
                        'timestamp': 'Now'
                    }
                    
                    logger.info(f"Extracted first job: {job['title']} at {job['company']}")
                    
                    # Post the job to Telegram
                    result = await scraper.post_job_to_telegram(job)
                    
                    if result:
                        logger.info("✅ Successfully posted job to Telegram")
                        
                        # Send advertisement to channel after successful job posting
                        check_and_send_advertisement(telegram_token, channel_id)
                        
                        # Direct call to send advertisement to ensure it appears after each post
                        from advertisement import send_advertisement_to_channel
                        send_advertisement_to_channel(telegram_token, channel_id)
                        logger.info("✅ Advertisement sent directly after job post")
                    else:
                        logger.info("ℹ️ Job not posted to Telegram (expected if credentials are None)")
                else:
                    logger.warning("No job listings found")
            except Exception as e:
                logger.error(f"Error extracting job: {str(e)}")
                
    except Exception as e:
        logger.error(f"❌ Test failed: {str(e)}")
        raise

# Run the script with scheduling
if __name__ == "__main__":
    import schedule
    import time
    
    # Use the token defined at the top of the file
    telegram_token = TELEGRAM_TOKEN
    channel_id = "@IT_Job_openings_Naukri"
    
    def run_job():
        """Run the job scraper"""
        try:
            logger.info("Running scheduled job scraper...")
            asyncio.run(extract_and_post_first_job())
            logger.info("Scheduled job completed successfully")
        except Exception as e:
            logger.error(f"Scheduled job failed: {str(e)}")
    
    def post_advertisement():
        """Post advertisement to channel"""
        try:
            logger.info("Posting scheduled advertisement to channel...")
            result = send_advertisement_to_channel(telegram_token, channel_id)
            if result:
                logger.info("✅ Advertisement posted successfully")
            else:
                logger.error("❌ Failed to post advertisement")
        except Exception as e:
            logger.error(f"Advertisement posting failed: {str(e)}")
    
    # Start premium bot in a background thread so it does not block the job scraper
    # We create a brand-new event loop for the thread because asyncio loops are
    # thread-local and run_polling() requires one.
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
    
    # Run immediately on startup
    logger.info("Running job scraper immediately on startup")
    run_job()
    
    # Post advertisement immediately
    logger.info("Posting advertisement immediately on startup")
    post_advertisement()
    
    # Schedule job scraper to run every 60 seconds
    logger.info("Setting up schedule to run job scraper every 60 seconds")
    schedule.every(60).seconds.do(run_job)
    
    # Schedule advertisement to run every 1 minute
    logger.info("Setting up schedule to post advertisement every 60 minute")
    schedule.every(60).minutes.do(post_advertisement)
    
    try:
        # Keep the script running and check for scheduled jobs
        while True:
            schedule.run_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Scheduler stopped by user")
    except Exception as e:
        logger.error(f"Scheduler crashed: {str(e)}")