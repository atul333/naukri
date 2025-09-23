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

logger = logging.getLogger('test_simple')

async def test_simple_navigation():
    logger.info("Starting simple navigation test")
    
    # Initialize scraper with test parameters
    scraper = NaukriJobScraper(
        telegram_token=None,  # No Telegram notifications
        channel_id=None
    )
    
    # Override job URL for testing
    scraper.job_url = "https://www.naukri.com/it-jobs"
    
    try:
        # Just test navigation without full job processing
        logger.info("Testing navigation only")
        await scraper.process_jobs()
        logger.info("Test completed successfully")
    except Exception as e:
        logger.error(f"Test failed: {str(e)}")
        raise

if __name__ == "__main__":
    asyncio.run(test_simple_navigation())