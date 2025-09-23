import asyncio
import logging
from main import NaukriJobScraper

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_full_functionality():
    """Test the full scraper functionality"""
    # Configuration
    telegram_token = "8348312063:AAH6DMUjtDfNaS2huKoALhVHUiK_8auMxbU"
    channel_id = "@job_opening_free"
    
    # Initialize scraper
    scraper = NaukriJobScraper(telegram_token, channel_id)
    
    # Test the full process
    logger.info("Testing full scraper functionality...")
    await scraper.process_jobs()
    
    logger.info("✅ Full test completed")

if __name__ == "__main__":
    asyncio.run(test_full_functionality())