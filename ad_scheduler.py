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
TELEGRAM_TOKEN = "8737613068:AAGtpmp32TVyz7YACORGYhNta89HJDg3HFg"  # Telegram bot token
CHANNEL_ID = "@IT_Job_openings_Naukri"  # Telegram channel ID

def post_advertisement():
    """
    Posts an advertisement to the Telegram channel
    """
    logger.info("Posting scheduled advertisement to channel")
    result = send_advertisement_to_channel(TELEGRAM_TOKEN, CHANNEL_ID)
    if result:
        logger.info("✅ Advertisement posted successfully")
    else:
        logger.error("❌ Failed to post advertisement")

def main():
    """
    Main function to run the advertisement scheduler
    """
    logger.info("Starting advertisement scheduler")
    logger.info(f"Advertisements will be posted every 1 minute to {CHANNEL_ID}")
    
    # Schedule advertisement posting every 1 minute
    schedule.every(60).minutes.do(post_advertisement)
    
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