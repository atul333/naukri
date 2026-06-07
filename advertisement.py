"""
Advertisement module for Naukri bot
"""
import os
import random
import logging
import asyncio
from telegram import Bot

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def get_advertisement_message():
    """
    Returns an energetic advertisement message for the Naukri bot
    """
    ad_message = """
🚀 <b>Supercharge Your Job Search with Premium_Naukri_bot!</b>

⚡️ Be the <b>FIRST</b> to apply for jobs on Naukri com - completely FREE!

✨ <b>Why use our bot?</b> ✨
🔍 Filter jobs by keywords that matter to YOU
💼 Set your experience level for perfect matches
📍 Choose your preferred locations
🔔 Get instant notifications for new openings

🏆 <b>Stay ahead of the competition</b> - Apply before anyone else! 🏆

👉 <b>Start now:</b> <a href="https://t.me/Premium_Naukri_bot">https://t.me/Premium_Naukri_bot</a> 👈
    """
    return ad_message.strip()

# Alternative advertisement messages for variety
def get_alternative_ad_message():
    """
    Returns an alternative advertisement message
    """
    alt_ad_message = """
🔥 <b>FREE PRIMIUM BOT WITH JOB FILTER</b>

⏰ <a href="https://t.me/Premium_Naukri_bot">https://t.me/Premium_Naukri_bot</a> delivers Naukri com jobs to you INSTANTLY! ⏰

✅ Custom keyword filters
✅ Experience level matching
✅ Location preferences
✅ 100% FREE to use!

💯 <b>Never miss your dream job again!</b> 💯

🤖 <b>Try it now:</b> <a href="https://t.me/Premium_Naukri_bot">https://t.me/Premium_Naukri_bot</a>
    """
    return alt_ad_message.strip()

def send_advertisement_to_channel(telegram_token, channel_id):
    """
    Sends an advertisement message to the specified Telegram channel
    """
    try:
        # Choose a random advertisement message
        ad_messages = [get_advertisement_message(), get_alternative_ad_message()]
        ad_message = random.choice(ad_messages)
        
        # Create a bot instance
        bot = Bot(token=telegram_token)
        
        # Send the advertisement to the channel - synchronous version
        bot.send_message(
            chat_id=channel_id,
            text=ad_message,
            parse_mode='HTML',
            disable_web_page_preview=True
        )
        
        logger.info(f"Advertisement sent to channel {channel_id}")
        return True
    except Exception as e:
        logger.error(f"Error sending advertisement: {str(e)}")
        # Print more detailed error information for debugging
        import traceback
        logger.error(f"Detailed error: {traceback.format_exc()}")
        return False

def check_and_send_advertisement(telegram_token, channel_id):
    """
    Checks if an advertisement should be sent after a job posting
    and sends it if conditions are met
    """
    counter_file = "job_post_counter.txt"
    
    # Create counter file if it doesn't exist
    if not os.path.exists(counter_file):
        with open(counter_file, "w", encoding="utf-8") as f:
            f.write("0")
    
    # Read current counter value
    with open(counter_file, "r", encoding="utf-8") as f:
        try:
            counter = int(f.read().strip())
        except ValueError:
            counter = 0
    
    # Increment counter
    counter += 1
    
    # Write updated counter back to file
    with open(counter_file, "w", encoding="utf-8") as f:
        f.write(str(counter))
    
    # Send advertisement after exactly 1 successful job posting
    if counter == 1:
        logger.info("Sending advertisement after first successful job posting")
        send_advertisement_to_channel(telegram_token, channel_id)
        return True
    
    return False