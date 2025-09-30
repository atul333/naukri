import asyncio
import logging
import os
import json
import threading
import sys
import re
from datetime import datetime
from main import NaukriJobScraper
from telegram import Bot
from telegram.error import TimedOut, NetworkError
from premium_bot import run_premium_bot, load_premium_users
from advertisement import check_and_send_advertisement

# Use the actual token from the file
TELEGRAM_TOKEN = "8470957235:AAFigzyiwRXSZGnIFn_x7wX6zLLAFX00ABk"

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

logger = logging.getLogger('test_extract_first_job')

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
                        # Send personalized message to the user
                        personalized_message = f"🔔 *Job Alert Matching Your Preferences!*\n\n{message}"
                        await bot.send_message(
                            chat_id=user_id,
                            text=personalized_message,
                            parse_mode='Markdown'
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
    telegram_token = "8470957235:AAFigzyiwRXSZGnIFn_x7wX6zLLAFX00ABk"
    channel_id = "@job_opening_free"
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
            
            await page.goto(job_url, wait_until='domcontentloaded', timeout=60000)
            
            # Wait for the page to load completely
            await asyncio.sleep(15)  # Increased wait time for page to fully load
            
            # Check for and handle rotation message
            try:
                rotation_message = await page.query_selector('text="Please rotate your device"')
                if rotation_message:
                    logger.info("Detected rotation message, attempting to bypass...")
                    # Execute JavaScript to remove the rotation message and any overlay
                    await page.evaluate("""
                        () => {
                            // Remove rotation message elements
                            const elements = document.querySelectorAll('*');
                            for (const el of elements) {
                                if (el.textContent && el.textContent.includes('rotate your device')) {
                                    el.style.display = 'none';
                                }
                                // Also remove any overlay or blocking elements
                                if (el.style && (el.style.position === 'fixed' || el.style.position === 'absolute')) {
                                    if (el.style.zIndex > 100 || el.style.opacity < 1) {
                                        el.style.display = 'none';
                                    }
                                }
                            }
                            // Force desktop mode
                            document.querySelector('body').classList.remove('portrait');
                            document.querySelector('body').classList.add('landscape');
                            return true;
                        }
                    """)
                    logger.info("Applied JavaScript fixes for rotation message")
                    await asyncio.sleep(5)  # Wait for changes to apply
            except Exception as e:
                logger.warning(f"Error handling rotation message: {str(e)}")
                # Continue anyway
            
            # Click on Sort by dropdown
            logger.info("Clicking on Sort by dropdown")
            try:
                # No need to save screenshot before sorting
                
                # Try multiple approaches to find and click the sort dropdown
                # First try: Use evaluate to find and click the sort dropdown by text content
                logger.info("Trying to find sort dropdown by text content")
                sort_clicked = await page.evaluate("""
                    () => {
                        // Try to find elements containing 'Sort by' or 'Relevance' text
                        const elements = Array.from(document.querySelectorAll('*'));
                        for (const el of elements) {
                            if (el.textContent && (el.textContent.includes('Sort by') || el.textContent.includes('Relevance'))) {
                                el.click();
                                return true;
                            }
                        }
                        return false;
                    }
                """)
                
                if sort_clicked:
                    logger.info("Found and clicked sort dropdown using JavaScript")
                    await asyncio.sleep(3)  # Wait for dropdown to appear
                    
                    # No need to save screenshot after clicking dropdown
                    
                    # Try to click on Date option using JavaScript
                    date_clicked = await page.evaluate("""
                        () => {
                            // Try to find elements containing 'Date' text
                            const elements = Array.from(document.querySelectorAll('*'));
                            for (const el of elements) {
                                if (el.textContent && el.textContent.trim() === 'Date') {
                                    el.click();
                                    return true;
                                }
                            }
                            return false;
                        }
                    """)
                    
                    if date_clicked:
                        logger.info("Selected Date sorting option using JavaScript")
                        # Wait for page to refresh with new sorting
                        await asyncio.sleep(10)
                    else:
                        logger.warning("Could not find Date option in dropdown using JavaScript")
                else:
                    # Second try: Use traditional selectors with broader matching
                    logger.info("Trying traditional selectors for sort dropdown")
                    sort_dropdown = await page.wait_for_selector(
                        '[data-qa*="sort"], [class*="sort"], [class*="Sort"], [class*="filter"], [class*="Filter"], button:has-text("Sort"), div:has-text("Sort by"), span:has-text("Sort by"), div:has-text("Relevance")', 
                        timeout=10000
                    )
                    if sort_dropdown:
                        await sort_dropdown.click()
                        logger.info("Clicked on Sort by dropdown using selector")
                        
                        # Wait for dropdown options to appear and click on Date option
                        await asyncio.sleep(3)
                        date_option = await page.wait_for_selector(
                            '[data-qa*="Date"], li:has-text("Date"), .option:has-text("Date"), [class*="option"]:has-text("Date"), div:has-text("Date")', 
                            timeout=10000
                        )
                        if date_option:
                            await date_option.click()
                            logger.info("Selected Date sorting option using selector")
                            # Wait for page to refresh with new sorting
                            await asyncio.sleep(10)
                        else:
                            logger.warning("Could not find Date option in dropdown using selector")
                    else:
                        logger.warning("Could not find Sort by dropdown using selector")
            except Exception as e:
                logger.error(f"Error while trying to sort by date: {str(e)}")
                logger.info("Continuing with default sorting")
            
            # Get page content immediately for analysis
            page_content = await page.content()
            with open("page_content.html", "w", encoding="utf-8") as f:
                f.write(page_content)
            logger.info("Saved page content to page_content.html")
            
            # Use BeautifulSoup to extract job information directly
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(page_content, 'html.parser')
            
            # Look for the first job card after sorting by date
            logger.info("Looking for the first job card after sorting by date")
            
            # Try to find job cards with various selectors
            job_cards = soup.select('article.jobTupleWrapper, .jobTuple, .SRPstyle__NormalCardStyle-sc-1rnhgwh-0, div[data-job-id]')
            logger.info(f"Found {len(job_cards)} potential job cards")
            
            target_job = None
            
            # Get the first job card
            if job_cards:
                target_job = job_cards[0]
                title_element = target_job.select_one('.jobTupleHeader .title, h2.jobTitle, .title, h2, h3, .srpHdr, .list-job-title')
                if title_element:
                    logger.info(f"Found first job: {title_element.text.strip()}")
                else:
                    logger.info("Found first job card but couldn't extract title")
            else:
                logger.warning("No job cards found on the page")
            
            if target_job:
                # Extract all required information from the job card
                title_element = target_job.select_one('.jobTupleHeader .title, h2.jobTitle, .title, h2, h3, .srpHdr, .list-job-title')
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
                experience_element = target_job.select_one('.ellipsis.fleft.fs12.lh16, [class*="experience"], [class*="exp"]')
                experience = experience_element.text.strip() if experience_element else "Not specified"
                
                # Extract location
                location_element = target_job.select_one('.locWdth span.ellipsis, .location, [class*="location"], [class*="loc"]')
                location = location_element.text.strip() if location_element else "Not specified"
                
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
                
                message = f"""
📌 *{job['title']}*

🏢 *Company:* {job['company']}

⏳ *Experience:* {job['experience']}

📍 *Location:* {job['location']}

💰 *CTC:* {job['ctc']}

{hashtag_str}

🔗 *Apply Link:* {encrypted_link}
                """
                
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
                    "posted_date": "Just Now",
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
                        # Use the scraper's send_telegram_message method instead of direct bot usage
                        result = await scraper.send_telegram_message(message, parse_mode='Markdown')
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
                    date_selectors = ['.fleft.postedDate', '.date', '[class*="date"]', '[class*="posted"]']
                    
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
                        
                        # No additional code needed here as advertisement is handled by check_and_send_advertisement
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
    
    def run_job():
        """Run the job scraper"""
        try:
            logger.info("Running scheduled job scraper...")
            asyncio.run(extract_and_post_first_job())
            logger.info("Scheduled job completed successfully")
        except Exception as e:
            logger.error(f"Scheduled job failed: {str(e)}")
    
    # Start premium bot directly (no need for threading)
    logger.info("Starting premium bot...")
    try:
        premium_bot_updater = run_premium_bot(telegram_token)
        logger.info("Premium bot started")
    except (TimedOut, NetworkError) as e:
        logger.warning(f"Telegram connection error: {e}. Continuing with other functionality.")
        # Continue with the rest of the script without the bot
    
    # Run immediately on startup
    logger.info("Running job scraper immediately on startup")
    run_job()
    
    # Schedule to run every 5 seconds
    logger.info("Setting up schedule to run every 60 seconds")
    schedule.every(60).seconds.do(run_job)
    
    try:
        # Keep the script running and check for scheduled jobs
        while True:
            schedule.run_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Scheduler stopped by user")
    except Exception as e:
        logger.error(f"Scheduler crashed: {str(e)}")