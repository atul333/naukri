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

logger = logging.getLogger('test_telegram')

async def test_telegram_functionality():
    logger.info("Starting Telegram functionality test")
    
    # Initialize scraper with test parameters
    # Use None for testing or provide actual tokens if you want to test real sending
    telegram_token = None  # or "YOUR_TELEGRAM_BOT_TOKEN"
    channel_id = None  # or "YOUR_TELEGRAM_CHANNEL_ID"
    
    scraper = NaukriJobScraper(telegram_token, channel_id)
    
    # Create a test job
    test_job = {
        'job_id': 'test_job_123',
        'title': 'Test Software Engineer',
        'company': 'Test Company',
        'location': 'Remote',
        'posted_date': 'Today',
        'apply_link': 'https://example.com/job',
        'category': 'IT',
        'timestamp': '2025-09-23T10:00:00'
    }
    
    try:
        # Test the send_telegram_message method
        logger.info("Testing send_telegram_message method")
        test_message = "This is a test message from the Naukri scraper"
        result = await scraper.send_telegram_message(test_message)
        
        if result:
            logger.info("✅ Telegram message sent successfully")
        else:
            logger.info("ℹ️ Telegram message not sent (expected if credentials are None)")
        
        # Test the post_job_to_telegram method
        logger.info("Testing post_job_to_telegram method")
        job_result = await scraper.post_job_to_telegram(test_job)
        
        if job_result:
            logger.info("✅ Job posted to Telegram successfully")
        else:
            logger.info("ℹ️ Job not posted to Telegram (expected if credentials are None)")
            
        logger.info("✅ Telegram functionality test completed successfully")
    except Exception as e:
        logger.error(f"❌ Test failed: {str(e)}")
        raise

if __name__ == "__main__":
    asyncio.run(test_telegram_functionality())