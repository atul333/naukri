import os
import json
import time
import threading
import logging
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext, ConversationHandler, CallbackQueryHandler

# Set up logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Define conversation states
TITLE, EXPERIENCE, LOCATION = range(3)

# Path to the premium users JSON file
PREMIUM_USERS_FILE = "premium_users.json"

# Initialize premium users data structure if file doesn't exist
if not os.path.exists(PREMIUM_USERS_FILE):
    with open(PREMIUM_USERS_FILE, "w") as f:
        json.dump({}, f)

def load_premium_users():
    """Load premium users from JSON file"""
    try:
        with open(PREMIUM_USERS_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return {}

def save_premium_users(premium_users):
    """Save premium users to JSON file"""
    with open(PREMIUM_USERS_FILE, "w") as f:
        json.dump(premium_users, f, indent=2)

def start(update: Update, context: CallbackContext) -> int:
    """Send welcome message when the command /start is issued."""
    user = update.effective_user
    user_id = str(user.id)
    username = user.username or user.first_name
    
    # Load premium users
    premium_users = load_premium_users()
    
    # Set premium membership for 10 minutes
    expiry_time = datetime.now() + timedelta(minutes=10)
    
    # Store user data with expiry time
    premium_users[user_id] = {
        "username": username,
        "expiry_time": expiry_time.timestamp(),
        "is_premium": True,
        "preferences": {
            "job_title": "",
            "experience": "",
            "location": ""
        }
    }
    
    # Save updated premium users
    save_premium_users(premium_users)
    
    # Send welcome message
    update.message.reply_text(
        f"Welcome {username} to our premium membership! 🎉\n\n"
        f"You have 10 minutes of premium membership."
    )
    
    # Start countdown timer in a separate thread
    countdown_thread = threading.Thread(
        target=show_countdown, 
        args=[user_id, context.bot, 10]
    )
    countdown_thread.daemon = True
    countdown_thread.start()
    
    # Schedule expiry check
    threading.Timer(600, check_and_expire_membership, args=[user_id, context.bot]).start()
    
    # Send separate message for job title prompt
    context.bot.send_message(
        chat_id=user_id,
        text="Let's set up your job preferences. Please tell me your preferred job title (maximum 2 words):"
    )
    
    return TITLE

def job_title(update: Update, context: CallbackContext) -> int:
    """Store job title and ask for experience."""
    user_id = str(update.effective_user.id)
    job_title = update.message.text.strip()
    
    # Check if job title has more than 2 words
    words = job_title.split()
    if len(words) > 2:
        update.message.reply_text(
            "⚠️ Please enter job title in 2 words only.\n\n"
            "For example: 'Software Engineer' or 'Data Scientist'"
        )
        return TITLE
    
    # Load premium users
    premium_users = load_premium_users()
    
    # Update job title preference
    if user_id in premium_users:
        premium_users[user_id]["preferences"]["job_title"] = job_title
        save_premium_users(premium_users)
    
    update.message.reply_text(
        f"Great! Your preferred job title is: {job_title}\n\n"
        f"Now, please tell me your total experience (in years):"
    )
    
    return EXPERIENCE

def experience(update: Update, context: CallbackContext) -> int:
    """Store experience and ask for location."""
    user_id = str(update.effective_user.id)
    experience = update.message.text.strip()
    
    # Load premium users
    premium_users = load_premium_users()
    
    # Update experience preference
    if user_id in premium_users:
        premium_users[user_id]["preferences"]["experience"] = experience
        save_premium_users(premium_users)
    
    update.message.reply_text(
        f"Thanks! Your experience is set to: {experience} years\n\n"
        f"Finally, please tell me your preferred job location:"
    )
    
    return LOCATION

def location(update: Update, context: CallbackContext) -> int:
    """Store location and complete the setup."""
    user_id = str(update.effective_user.id)
    location = update.message.text.strip()
    
    # Load premium users
    premium_users = load_premium_users()
    
    # Update location preference
    if user_id in premium_users:
        premium_users[user_id]["preferences"]["location"] = location
        save_premium_users(premium_users)
    
    # Get all preferences for confirmation
    preferences = premium_users[user_id]["preferences"]
    
    update.message.reply_text(
        f"Perfect! Your job preferences have been saved:\n\n"
        f"🔹 Job Title: {preferences['job_title']}\n"
        f"🔹 Experience: {preferences['experience']} years\n"
        f"🔹 Location: {preferences['location']}\n\n"
        f"You will receive job alerts matching these preferences during your premium membership.\n"
        f"Your premium membership will expire in 10 minutes from when you started."
    )
    
    return ConversationHandler.END

def show_countdown(user_id, bot, minutes):
    """Show countdown timer for premium membership"""
    total_seconds = minutes * 60
    update_interval = 60  # Update every minute
    
    for remaining_seconds in range(total_seconds, 0, -update_interval):
        remaining_minutes = remaining_seconds // 60
        
        if remaining_minutes in [5, 2, 1]:  # Show countdown at these specific times
            try:
                bot.send_message(
                    chat_id=user_id,
                    text=f"⏳ Your premium membership will expire in {remaining_minutes} minute{'s' if remaining_minutes > 1 else ''}!"
                )
            except Exception as e:
                logger.error(f"Failed to send countdown notification to user {user_id}: {e}")
        
        time.sleep(update_interval)

def check_and_expire_membership(user_id, bot):
    """Check if membership has expired and notify user"""
    premium_users = load_premium_users()
    
    if user_id in premium_users:
        premium_users[user_id]["is_premium"] = False
        save_premium_users(premium_users)
        
        try:
            bot.send_message(
                chat_id=user_id,
                text="⚠️ YOUR PREMIUM MEMBERSHIP HAS EXPIRED! ⚠️\n\n"
                     "Your countdown has reached zero. Premium features are no longer available.\n\n"
                     "To continue receiving job alerts matching your preferences, "
                     "please renew your premium membership."
            )
            logger.info(f"Premium membership expired for user {user_id}")
        except Exception as e:
            logger.error(f"Failed to send expiry notification to user {user_id}: {e}")

def cancel(update: Update, context: CallbackContext) -> int:
    """Cancel and end the conversation."""
    update.message.reply_text('Preferences setup cancelled. You can restart anytime with /start')
    return ConversationHandler.END

def check_expired_memberships():
    """Periodically check for expired memberships"""
    while True:
        premium_users = load_premium_users()
        current_time = datetime.now().timestamp()
        
        for user_id, user_data in premium_users.items():
            if user_data.get("is_premium", False) and user_data.get("expiry_time", 0) < current_time:
                logger.info(f"Membership expired for user {user_id}")
                premium_users[user_id]["is_premium"] = False
                
        save_premium_users(premium_users)
        time.sleep(60)  # Check every minute

def run_premium_bot(telegram_token):
    """Run the premium bot"""
    updater = Updater(telegram_token)
    dispatcher = updater.dispatcher
    
    # Create conversation handler for collecting job preferences
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            TITLE: [MessageHandler(Filters.text & ~Filters.command, job_title)],
            EXPERIENCE: [MessageHandler(Filters.text & ~Filters.command, experience)],
            LOCATION: [MessageHandler(Filters.text & ~Filters.command, location)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )
    
    dispatcher.add_handler(conv_handler)
    
    # Start the expiry checker in a separate thread
    expiry_thread = threading.Thread(target=check_expired_memberships)
    expiry_thread.daemon = True
    expiry_thread.start()
    
    # Start the bot in polling mode (without blocking with idle())
    updater.start_polling()
    logger.info("Premium bot started")
    
    # Don't call updater.idle() when running in a thread
    # Just return the updater so it stays alive with the main thread
    return updater

if __name__ == "__main__":
    # Create the Updater and pass it your bot's token
    telegram_token = "8348312063:AAH6DMUjtDfNaS2huKoALhVHUiK_8auMxbU"
    run_premium_bot(telegram_token)