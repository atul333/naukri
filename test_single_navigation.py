import asyncio
import logging
from main import NaukriJobScraper

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

logger = logging.getLogger('test_single_navigation')

async def test_single_navigation():
    logger.info("Starting single navigation test")
    
    # Initialize scraper with test parameters
    telegram_token = None  # or "YOUR_TELEGRAM_BOT_TOKEN"
    channel_id = None  # or "YOUR_TELEGRAM_CHANNEL_ID"
    
    scraper = NaukriJobScraper(telegram_token, channel_id)
    
    # Set a single category for testing
    scraper.job_url = "https://www.naukri.com/it-jobs?src=gnbjobs_homepage_srch"
    
    try:
        # Process jobs - this should only navigate once
        await scraper.process_jobs()
        logger.info("✅ Single navigation test completed successfully")
    except Exception as e:
        logger.error(f"❌ Test failed: {str(e)}")
        raise

if __name__ == "__main__":
    asyncio.run(test_single_navigation())