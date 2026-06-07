import asyncio
import logging
from main import NaukriJobScraper

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_telegram_posting():
    """Test the Telegram posting functionality with sample data"""
    # Configuration
    telegram_token = "8737613068:AAGtpmp32TVyz7YACORGYhNta89HJDg3HFg"
    channel_id = "@IT_Job_openings_Naukri"
    
    # Initialize scraper
    scraper = NaukriJobScraper(telegram_token, channel_id)
    
    # Sample job for testing
    test_job = {
        'job_id': 'test_job_123',
        'title': 'Test Python Developer',
        'company': 'Test Company',
        'location': 'Remote',
        'posted_date': 'Today',
        'apply_link': 'https://www.naukri.com/job-listings-test',
        'timestamp': '2023-07-01T12:00:00'
    }
    
    # Test posting to Telegram
    logger.info("Testing Telegram posting...")
    success = await scraper.post_job_to_telegram(test_job)
    
    if success:
        logger.info("✅ Successfully posted test job to Telegram")
    else:
        logger.error("❌ Failed to post test job to Telegram")

if __name__ == "__main__":
    asyncio.run(test_telegram_posting())