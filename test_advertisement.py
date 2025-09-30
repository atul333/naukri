import asyncio
import logging
import traceback
from advertisement import send_advertisement_to_channel

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('test_advertisement')

# Use the actual token from the file
TELEGRAM_TOKEN = "8470957235:AAFigzyiwRXSZGnIFn_x7wX6zLLAFX00ABk"
CHANNEL_ID = "@job_opening_free"

async def test_advertisement():
    """Test sending an advertisement to the channel"""
    logger.info(f"Testing advertisement with channel: {CHANNEL_ID}")
    
    try:
        # Force advertisement to be sent by directly calling the function
        result = await send_advertisement_to_channel(TELEGRAM_TOKEN, CHANNEL_ID)
        
        if result:
            logger.info("✅ Advertisement sent successfully")
        else:
            logger.error("❌ Failed to send advertisement")
    except Exception as e:
        logger.error(f"Error in test: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")

if __name__ == "__main__":
    asyncio.run(test_advertisement())