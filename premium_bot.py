import os
import json
import time
import threading
import logging
import qrcode
import io
import base64
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext, ConversationHandler, CallbackQueryHandler

# Set up logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Define conversation states
TITLE, EXPERIENCE, LOCATION, EDIT_PREFERENCES = range(4)

# Path to the premium users JSON file
PREMIUM_USERS_FILE = "premium_users.json"

# Admin configuration
ADMIN_USERNAME = "SocialAdLinker"
ADMIN_CHAT_ID = None  # Will be set when admin uses the bot

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
    
    # Check if user already exists and has preferences
    user_exists = user_id in premium_users
    has_preferences = False
    
    if user_exists:
        preferences = premium_users[user_id].get("preferences", {})
        has_job_keywords = preferences.get("job_keywords", "") != ""
        has_experience = preferences.get("experience", "") != ""
        has_location = preferences.get("location", "") != ""
        has_preferences = has_job_keywords and has_experience and has_location
    
    # If user doesn't exist, create new user
    if not user_exists:
        # Set premium status to lifetime (using a very distant future date)
        expiry_time = datetime.now() + timedelta(days=36500)  # ~100 years (effectively lifetime)
        
        # Store user data with lifetime expiry time
        premium_users[user_id] = {
            "username": username,
            "expiry_time": expiry_time.timestamp(),
            "is_premium": True,
            "preferences": {
                "job_keywords": "",
                "experience": "",
                "location": ""
            }
        }
        
        # Save updated premium users
        save_premium_users(premium_users)
        
        # Send welcome message
        update.message.reply_text(
            f"Welcome {username} to our premium membership! 🎉\n\n"
                f"You have LIFETIME premium membership."
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
    
    # If user exists and has preferences, ask if they want to edit
    if has_preferences:
        keyboard = [
            [InlineKeyboardButton("✏️ Edit Job Keywords", callback_data="edit_keywords")],
            [InlineKeyboardButton("✏️ Edit Experience", callback_data="edit_experience")],
            [InlineKeyboardButton("✏️ Edit Location", callback_data="edit_location")],
            [InlineKeyboardButton("👍 Keep Current Preferences", callback_data="keep_preferences")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Show current preferences
        current_prefs = premium_users[user_id]["preferences"]
        update.message.reply_text(
            f"Welcome back {username}! 👋\n\n"
            f"Your current job preferences are:\n"
            f"🔍 Keywords: {current_prefs.get('job_keywords', 'Not set')}\n"
            f"⏳ Experience: {current_prefs.get('experience', 'Not set')} years\n"
            f"📍 Location: {current_prefs.get('location', 'Not set')}\n\n"
            f"Would you like to edit your preferences?",
            reply_markup=reply_markup
        )
        return EDIT_PREFERENCES
    else:
        # Send separate message for job keywords prompt
        context.bot.send_message(
            chat_id=user_id,
            text="Let's set up your job preferences. 🔍 Please enter minimum 1 and maximum 5 keywords for your job search separated by commas (,):\n\nExample: developer,python,web,frontend,react 💻"
        )
        
        return TITLE

def renew_membership(update: Update, context: CallbackContext) -> None:
    """Handle the /renew_membership command"""
    # Create inline keyboard with payment options
    keyboard = [
        [InlineKeyboardButton("1 Day - ₹2", callback_data="payment_1_day")],
        [InlineKeyboardButton("7 Days - ₹10", callback_data="payment_7_days")],
        [InlineKeyboardButton("30 Days - ₹30", callback_data="payment_30_days")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    update.message.reply_text(
        text="📱 *Premium Membership Renewal Options*\n\n"
             "Please select a subscription period:\n\n"
             "• 1 Day = ₹2\n"
             "• 7 Days = ₹10\n"
             "• 30 Days = ₹30",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

def job_title(update: Update, context: CallbackContext) -> int:
    """Store job keywords and ask for experience."""
    user_id = str(update.effective_user.id)
    keywords = update.message.text.strip()
    
    # Load premium users
    premium_users = load_premium_users()
    
    # Update job keywords preference
    if user_id in premium_users:
        premium_users[user_id]["preferences"]["job_keywords"] = keywords
        save_premium_users(premium_users)
    
    update.message.reply_text(
        f"🎯 Great! Your job keywords are set: {keywords}\n\n"
        f"📊 Now, please tell me your total experience (in years):"
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
        f"🔹 Job Keywords: {preferences['job_keywords']}\n"
        f"🔹 Experience: {preferences['experience']} years\n"
        f"🔹 Location: {preferences['location']}\n\n"
        f"You will receive job alerts matching these keywords during your premium membership.\n"
        f"Your premium membership will never expire - you have LIFETIME access."
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
            # Create inline keyboard with renewal option
            keyboard = [
                [InlineKeyboardButton("💰 Renew Membership", callback_data="renew_membership")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            bot.send_message(
                chat_id=user_id,
                text="⚠️ YOUR PREMIUM MEMBERSHIP HAS EXPIRED! ⚠️\n\n"
                     "Your countdown has reached zero. Premium features are no longer available.\n\n"
                     "To continue receiving job alerts matching your preferences, "
                     "please renew your premium membership.",
                reply_markup=reply_markup
            )
            logger.info(f"Premium membership expired for user {user_id}")
        except Exception as e:
            logger.error(f"Failed to send expiry notification to user {user_id}: {e}")

def cancel(update: Update, context: CallbackContext) -> int:
    """Cancel and end the conversation."""
    update.message.reply_text('Preferences setup cancelled. You can restart anytime with /start')
    return ConversationHandler.END

def renew_membership_callback(update: Update, context: CallbackContext):
    """Handle the renewal button click"""
    query = update.callback_query
    query.answer()
    
    # Create inline keyboard with payment options
    keyboard = [
        [InlineKeyboardButton("1 Day - ₹2", callback_data="payment_1_day")],
        [InlineKeyboardButton("7 Days - ₹10", callback_data="payment_7_days")],
        [InlineKeyboardButton("30 Days - ₹30", callback_data="payment_30_days")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    query.edit_message_text(
        text="📱 *Premium Membership Renewal Options*\n\n"
             "Please select a subscription period:\n\n"
             "• 1 Day = ₹2\n"
             "• 7 Days = ₹10\n"
             "• 30 Days = ₹30",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

def generate_upi_qr_code(upi_id, amount, reference):
    """Generate QR code for UPI payment"""
    # Create UPI URI
    upi_uri = f"upi://pay?pa={upi_id}&pn=NaukriBot&am={amount}&cu=INR&tn={reference}"
    
    # Generate QR code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(upi_uri)
    qr.make(fit=True)
    
    # Create an image from the QR Code
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Save to bytes
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='PNG')
    img_byte_arr.seek(0)
    
    return img_byte_arr

def handle_payment_option(update: Update, context: CallbackContext):
    """Handle payment option selection"""
    query = update.callback_query
    query.answer()
    
    # Get the selected option
    option = query.data
    user_id = str(update.effective_user.id)
    
    # Parse the option to get days and amount
    days = 1
    amount = 2
    
    if option == "payment_7_days":
        days = 7
        amount = 10
    elif option == "payment_30_days":
        days = 30
        amount = 30
    
    # Generate a unique payment reference
    payment_ref = f"PREMIUM_{user_id}_{int(time.time())}"
    
    # Store the payment reference and details in user data
    premium_users = load_premium_users()
    if user_id in premium_users:
        premium_users[user_id]["pending_payment"] = {
            "reference": payment_ref,
            "days": days,
            "amount": amount,
            "timestamp": time.time()
        }
        save_premium_users(premium_users)
    
    # Create QR code for UPI payment
    upi_id = "8329707239-2@ybl"
    qr_code_bytes = generate_upi_qr_code(upi_id, amount, payment_ref)
    
    # Create payment verification button
    keyboard = [
        [InlineKeyboardButton("✅ I've Completed Payment", callback_data=f"verify_payment_{payment_ref}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # First send payment instructions
    query.edit_message_text(
        text=f"💳 *Payment Details*\n\n"
             f"Amount: ₹{amount}\n"
             f"UPI ID: `{upi_id}`\n"
             f"Reference: `{payment_ref}`\n\n"
             f"Please scan the QR code below or make the payment using any UPI app and include the reference in the payment notes.\n\n"
             f"After payment, click the button below to verify and activate your premium membership for {days} day{'s' if days > 1 else ''}.",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    # Then send the QR code as a photo
    context.bot.send_photo(
        chat_id=update.effective_chat.id,
        photo=qr_code_bytes,
        caption=f"QR Code for ₹{amount} payment - Scan to pay"
    )

def verify_payment(update: Update, context: CallbackContext):
    """Verify payment and request admin approval"""
    query = update.callback_query
    query.answer()
    
    user_id = str(update.effective_user.id)
    payment_ref = query.data.replace("verify_payment_", "")
    
    # Load premium users
    premium_users = load_premium_users()
    
    if user_id in premium_users and "pending_payment" in premium_users[user_id]:
        pending = premium_users[user_id]["pending_payment"]
        
        if pending["reference"] == payment_ref:
            # Mark payment as pending verification
            premium_users[user_id]["pending_payment"]["status"] = "pending_verification"
            premium_users[user_id]["pending_payment"]["verification_requested_at"] = time.time()
            
            # Save updated premium users
            save_premium_users(premium_users)
            
            # Create keyboard with admin contact
            keyboard = [
                [InlineKeyboardButton("📱 Contact Admin", url="https://t.me/SocialAdLinker")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Notify user that payment is being verified and to send screenshot
            query.edit_message_text(
                text="🔍 *Payment Verification In Progress*\n\n"
                     "Your payment is being verified by our admin.\n\n"
                     "📸 *Please send your payment screenshot to @SocialAdLinker*\n"
                     "Include your User ID: `" + user_id + "` in your message.\n\n"
                     "You will be notified once your payment is verified and your premium membership is activated.",
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
            
            # Notify admin about pending verification
            days = pending["days"]
            amount = pending["amount"]
            admin_message = (
                f"🔔 *Payment Verification Required*\n\n"
                f"User ID: `{user_id}`\n"
                f"Reference: `{payment_ref}`\n"
                f"Amount: ₹{amount}\n"
                f"Duration: {days} day{'s' if days > 1 else ''}\n\n"
                f"User has been instructed to send payment screenshot.\n"
                f"Use /approve_{payment_ref} to approve or /reject_{payment_ref} to reject."
            )
            
            # Send notification to admin if admin chat ID is available
            if ADMIN_CHAT_ID:
                try:
                    context.bot.send_message(
                        chat_id=ADMIN_CHAT_ID,
                        text=admin_message,
                        parse_mode='Markdown'
                    )
                except Exception as e:
                    logger.error(f"Failed to send notification to admin: {e}")
            
            logger.info(f"Payment verification requested by user {user_id} for {days} days - Ref: {payment_ref}")
        else:
            query.edit_message_text(
                text="❌ Payment verification failed. Invalid reference."
            )

def approve_payment(update: Update, context: CallbackContext):
    """Admin command to approve a payment"""
    # Check if the user is admin
    user = update.effective_user
    user_id = str(user.id)
    username = user.username
    
    # Set admin chat ID if this is the admin
    global ADMIN_CHAT_ID
    if username == ADMIN_USERNAME and ADMIN_CHAT_ID is None:
        ADMIN_CHAT_ID = user_id
        logger.info(f"Admin chat ID set to {ADMIN_CHAT_ID}")
    
    # Only allow admin to approve payments
    if username != ADMIN_USERNAME:
        update.message.reply_text("⛔ You are not authorized to use this command.")
        return
    
    # Get the payment reference from the command
    command_text = update.message.text
    if not command_text.startswith("/approve_"):
        update.message.reply_text("❌ Invalid command format. Use /approve_REFERENCE")
        return
    
    payment_ref = command_text.replace("/approve_", "")
    
    # Find the user with this pending payment
    premium_users = load_premium_users()
    target_user_id = None
    
    for uid, user_data in premium_users.items():
        if "pending_payment" in user_data and user_data["pending_payment"].get("reference") == payment_ref:
            target_user_id = uid
            break
    
    if not target_user_id:
        update.message.reply_text(f"❌ No pending payment found with reference: {payment_ref}")
        return
    
    # Get payment details
    pending = premium_users[target_user_id]["pending_payment"]
    days = pending["days"]
    
    # Calculate new expiry time
    current_time = datetime.now()
    
    # If user already has an active premium membership, extend it
    if target_user_id in premium_users and premium_users[target_user_id].get("is_premium", False):
        current_expiry = datetime.fromtimestamp(premium_users[target_user_id]["expiry_time"])
        if current_expiry > current_time:
            new_expiry = current_expiry + timedelta(days=days)
        else:
            new_expiry = current_time + timedelta(days=days)
    else:
        new_expiry = current_time + timedelta(days=days)
        premium_users[target_user_id]["is_premium"] = True
    
    # Update user's premium status
    premium_users[target_user_id]["expiry_time"] = new_expiry.timestamp()
    premium_users[target_user_id]["pending_payment"]["status"] = "approved"
    premium_users[target_user_id]["pending_payment"]["approved_at"] = time.time()
    premium_users[target_user_id]["pending_payment"]["approved_by"] = username
    
    # Save updated premium users
    save_premium_users(premium_users)
    
    # Notify admin
    update.message.reply_text(
        f"✅ Payment approved for User ID: {target_user_id}\n"
        f"Premium membership activated for {days} day{'s' if days > 1 else ''}.\n"
        f"Expiry: {new_expiry.strftime('%Y-%m-%d %H:%M:%S')}"
    )
    
    # Notify user
    try:
        context.bot.send_message(
            chat_id=target_user_id,
            text=f"✅ *Payment Verified!*\n\n"
                 f"Your premium membership has been activated for {days} day{'s' if days > 1 else ''}.\n"
                 f"Expiry: {new_expiry.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                 f"You will now receive job alerts matching your preferences.",
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Failed to send approval notification to user {target_user_id}: {e}")
    
    logger.info(f"Payment approved for user {target_user_id} - {days} days premium activated")

def reject_payment(update: Update, context: CallbackContext):
    """Admin command to reject a payment"""
    # Check if the user is admin
    user = update.effective_user
    username = user.username
    
    # Only allow admin to reject payments
    if username != ADMIN_USERNAME:
        update.message.reply_text("⛔ You are not authorized to use this command.")
        return
    
    # Get the payment reference from the command
    command_text = update.message.text
    if not command_text.startswith("/reject_"):
        update.message.reply_text("❌ Invalid command format. Use /reject_REFERENCE")
        return
    
    payment_ref = command_text.replace("/reject_", "")
    
    # Find the user with this pending payment
    premium_users = load_premium_users()
    target_user_id = None
    
    for uid, user_data in premium_users.items():
        if "pending_payment" in user_data and user_data["pending_payment"].get("reference") == payment_ref:
            target_user_id = uid
            break
    
    if not target_user_id:
        update.message.reply_text(f"❌ No pending payment found with reference: {payment_ref}")
        return
    
    # Mark payment as rejected
    premium_users[target_user_id]["pending_payment"]["status"] = "rejected"
    premium_users[target_user_id]["pending_payment"]["rejected_at"] = time.time()
    premium_users[target_user_id]["pending_payment"]["rejected_by"] = username
    
    # Save updated premium users
    save_premium_users(premium_users)
    
    # Notify admin
    update.message.reply_text(
        f"❌ Payment rejected for User ID: {target_user_id}\n"
        f"Reference: {payment_ref}"
    )
    
    # Notify user
    try:
        # Create renewal button
        keyboard = [
            [InlineKeyboardButton("🔄 Try Again", callback_data="renew_membership")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        context.bot.send_message(
            chat_id=target_user_id,
            text=f"❌ *Payment Verification Failed*\n\n"
                 f"We could not verify your payment. This could be due to:\n"
                 f"• Payment not received\n"
                 f"• Incorrect payment reference\n"
                 f"• Insufficient payment amount\n\n"
                 f"Please contact @SocialAdLinker for assistance or try again.",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    except Exception as e:
        logger.error(f"Failed to send rejection notification to user {target_user_id}: {e}")
    
    logger.info(f"Payment rejected for user {target_user_id} - Ref: {payment_ref}")

def approve_payment(user_id, payment_ref):
    """Approve payment and activate premium membership (called by admin or auto-approval)"""
    # Load premium users
    premium_users = load_premium_users()
    
    if user_id in premium_users and "pending_payment" in premium_users[user_id]:
        pending = premium_users[user_id]["pending_payment"]
        
        if pending["reference"] == payment_ref and pending.get("status") == "pending_verification":
            days = pending["days"]
            
            # Set premium membership to lifetime (using a very distant future date)
            expiry_time = datetime.now() + timedelta(days=36500)  # ~100 years (effectively lifetime)
            
            # Update user data with lifetime expiry time
            premium_users[user_id]["expiry_time"] = expiry_time.timestamp()
            premium_users[user_id]["is_premium"] = True
            
            # Remove pending payment
            premium_users[user_id].pop("pending_payment", None)
            
            # Save updated premium users
            save_premium_users(premium_users)
            
            # Send confirmation message to user
            try:
                updater.bot.send_message(
                    chat_id=user_id,
                    text=f"✅ *Payment Verified!*\n\n"
                         f"Your premium membership has been activated for LIFETIME.\n"
                         f"You will now receive job alerts matching your preferences.",
                    parse_mode='Markdown'
                )
                logger.info(f"Premium membership activated for user {user_id} for {days} days")
            except Exception as e:
                logger.error(f"Failed to send confirmation to user {user_id}: {e}")
    else:
        logger.error(f"Failed to approve payment for user {user_id}: User or payment not found")

def reject_payment(user_id, payment_ref, reason="Payment not received"):
    """Reject payment (called by admin)"""
    # Load premium users
    premium_users = load_premium_users()
    
    if user_id in premium_users and "pending_payment" in premium_users[user_id]:
        pending = premium_users[user_id]["pending_payment"]
        
        if pending["reference"] == payment_ref and pending.get("status") == "pending_verification":
            # Remove pending payment
            premium_users[user_id].pop("pending_payment", None)
            
            # Save updated premium users
            save_premium_users(premium_users)
            
            # Send rejection message to user
            try:
                updater.bot.send_message(
                    chat_id=user_id,
                    text=f"❌ *Payment Rejected*\n\n"
                         f"Your payment could not be verified.\n"
                         f"Reason: {reason}\n\n"
                         f"Please try again or contact support if you believe this is an error.",
                    parse_mode='Markdown'
                )
                logger.info(f"Payment rejected for user {user_id}: {reason}")
            except Exception as e:
                logger.error(f"Failed to send rejection to user {user_id}: {e}")
    else:
        logger.error(f"Failed to reject payment for user {user_id}: User or payment not found")


def check_expired_memberships():
    """Periodically check for expired memberships"""
    while True:
        premium_users = load_premium_users()
        current_time = datetime.now().timestamp()
        
        for user_id, user_data in premium_users.items():
            if user_data.get("is_premium", False) and "expiry_time" in user_data:
                expiry_time = user_data["expiry_time"]
                time_left = expiry_time - current_time
                
                # Send notifications at specific intervals
                if 300 <= time_left < 310:  # 5 minutes
                    send_expiry_notification(user_id, "5 minutes")
                elif 120 <= time_left < 130:  # 2 minutes
                    send_expiry_notification(user_id, "2 minutes")
                elif 60 <= time_left < 70:  # 1 minute
                    send_expiry_notification(user_id, "1 minute")
                elif time_left <= 0 and user_data.get("is_premium", False):
                    # Mark as expired
                    premium_users[user_id]["is_premium"] = False
                    send_expiry_notification(user_id, "EXPIRED")
                    logger.info(f"Premium membership expired for user {user_id}")
        
        save_premium_users(premium_users)
        time.sleep(60)  # Check every minute

def edit_job_keywords(update: Update, context: CallbackContext) -> int:
    """Handle edit job keywords button"""
    query = update.callback_query
    query.answer()
    user_id = str(query.from_user.id)
    
    query.edit_message_text(
        text="🔍 Please enter minimum 1 and maximum 5 keywords for your job search separated by commas (,):\n\n"
             "Example: developer,python,web,frontend,react 💻"
    )
    return TITLE

def edit_experience(update: Update, context: CallbackContext) -> int:
    """Handle edit experience button"""
    query = update.callback_query
    query.answer()
    user_id = str(query.from_user.id)
    
    query.edit_message_text(
        text="⏳ Please enter your years of experience (e.g., 2, 5, 8):"
    )
    return EXPERIENCE

def edit_location(update: Update, context: CallbackContext) -> int:
    """Handle edit location button"""
    query = update.callback_query
    query.answer()
    user_id = str(query.from_user.id)
    
    query.edit_message_text(
        text="📍 Please enter your preferred job location (e.g., Mumbai, Delhi, Bangalore):"
    )
    return LOCATION

def keep_preferences(update: Update, context: CallbackContext) -> int:
    """Handle keep current preferences button"""
    query = update.callback_query
    query.answer()
    user_id = str(query.from_user.id)
    
    # Load premium users to get current preferences
    premium_users = load_premium_users()
    current_prefs = premium_users[user_id]["preferences"]
    
    query.edit_message_text(
        text="👍 Great! Your preferences remain unchanged:\n\n"
             f"🔍 Keywords: {current_prefs.get('job_keywords', 'Not set')}\n"
             f"⏳ Experience: {current_prefs.get('experience', 'Not set')} years\n"
             f"📍 Location: {current_prefs.get('location', 'Not set')}\n\n"
             f"You will continue to receive job alerts matching these preferences."
    )
    return ConversationHandler.END

def send_expiry_notification(user_id, time_left):
    """Send notification about premium membership expiry"""
    try:
        if time_left == "EXPIRED":
            # Create inline keyboard with renewal button
            keyboard = [
                [InlineKeyboardButton("💰 Renew Membership", callback_data="renew_membership")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            message = "⚠️ YOUR PREMIUM MEMBERSHIP HAS EXPIRED! ⚠️\n\n" \
                     "Your countdown has reached zero.\n" \
                     "Premium features are no longer available.\n\n" \
                     "To continue receiving job alerts matching your preferences, please renew your premium membership."
            
            updater.bot.send_message(chat_id=user_id, text=message, reply_markup=reply_markup)
            logger.info(f"Sent expiry notification with renewal button to user {user_id}")
        else:
            message = f"⏳ Your premium membership will expire in {time_left}!"
            
            updater.bot.send_message(chat_id=user_id, text=message)
            logger.info(f"Sent expiry notification to user {user_id}: {time_left}")
    except Exception as e:
        logger.error(f"Failed to send expiry notification to user {user_id}: {e}")

def run_premium_bot(telegram_token):
    """Run the premium bot"""
    try:
        # Validate token format
        if not telegram_token or ":" not in telegram_token:
            logger.error("Invalid Telegram token format")
            raise ValueError("Invalid Telegram token format. Token should contain a colon.")
            
        global updater
        updater = Updater(telegram_token)
        dispatcher = updater.dispatcher
        
        # Create conversation handler for collecting job preferences
        conv_handler = ConversationHandler(
            entry_points=[CommandHandler('start', start)],
            states={
                TITLE: [MessageHandler(Filters.text & ~Filters.command, job_title)],
                EXPERIENCE: [MessageHandler(Filters.text & ~Filters.command, experience)],
                LOCATION: [MessageHandler(Filters.text & ~Filters.command, location)],
                EDIT_PREFERENCES: [
                    CallbackQueryHandler(edit_job_keywords, pattern='^edit_keywords$'),
                    CallbackQueryHandler(edit_experience, pattern='^edit_experience$'),
                    CallbackQueryHandler(edit_location, pattern='^edit_location$'),
                    CallbackQueryHandler(keep_preferences, pattern='^keep_preferences$'),
                ],
            },
            fallbacks=[CommandHandler('cancel', cancel)],
        )
        
        dispatcher.add_handler(conv_handler)
        
        # Register command handlers
        dispatcher.add_handler(CommandHandler("renew_membership", renew_membership))
        
        # Register callback handlers for renewal flow
        dispatcher.add_handler(CallbackQueryHandler(renew_membership_callback, pattern="^renew_membership$"))
        dispatcher.add_handler(CallbackQueryHandler(handle_payment_option, pattern="^payment_"))
        dispatcher.add_handler(CallbackQueryHandler(verify_payment, pattern="^verify_payment_"))
        
        # Register admin command handlers for payment approval/rejection
        # These use MessageHandler with regex to handle commands with dynamic payment references
        dispatcher.add_handler(MessageHandler(Filters.regex(r'^/approve_'), approve_payment))
        dispatcher.add_handler(MessageHandler(Filters.regex(r'^/reject_'), reject_payment))
        
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
    except Exception as e:
        logger.error(f"Error starting premium bot: {e}")
        raise

if __name__ == "__main__":
    # Create the Updater and pass it your bot's token
    telegram_token = "8348312063:AAH6DMUjtDfNaS2huKoALhVHUiK_8auMxbU"
    run_premium_bot(telegram_token)