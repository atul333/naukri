"""
Advertisement Scheduler for Naukri bot
Posts advertisements to the Telegram channel every 1 minute
"""
import time
import logging
import schedule
from advertisement import send_advertisement_to_channel

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Telegram configuration
from config import TELEGRAM_BOT_TOKEN as TELEGRAM_TOKEN, TELEGRAM_CHANNELS
CHANNELS_STR = ", ".join(TELEGRAM_CHANNELS)

def post_advertisement():
    """
    Posts an advertisement to all configured Telegram channels
    """
    logger.info(f"Posting scheduled advertisement to channels: {CHANNELS_STR}")
    result = send_advertisement_to_channel(TELEGRAM_TOKEN, TELEGRAM_CHANNELS)
    if result:
        logger.info("✅ Advertisement posted successfully to all channels")
    else:
        logger.error("❌ Failed to post advertisement")

def main():
    """
    Main function to run the advertisement scheduler
    """
    logger.info("Starting advertisement scheduler")
    logger.info(f"Advertisements will be posted every 12 hours to {CHANNELS_STR}")
    
    # Schedule advertisement posting every 12 hours
    schedule.every(12).hours.do(post_advertisement)
    
    # Post one advertisement immediately on startup
    post_advertisement()
    
    # Keep the script running
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Advertisement scheduler stopped by user")
    except Exception as e:
        logger.error(f"Error in advertisement scheduler: {str(e)}")
        import traceback
        logger.error(f"Detailed error: {traceback.format_exc()}")