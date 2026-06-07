"""
Premium Naukri Bot — python-telegram-bot v20 (async)
Users register, set preferences (keywords, experience, location).
main.py reads premium_users.json and sends matching jobs directly to each user.
"""
import os
import json
import logging
import asyncio
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ConversationHandler, CallbackQueryHandler,
    ContextTypes
)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Conversation states
TITLE, EXPERIENCE, LOCATION, EDIT_PREFERENCES = range(4)

PREMIUM_USERS_FILE = "premium_users.json"
PREMIUM_BOT_TOKEN = "8762043028:AAEtOD5gkXQVkf8BTk4HYgukBQfiEp5HoK8"


def load_premium_users():
    try:
        with open(PREMIUM_USERS_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return {}


def save_premium_users(data):
    with open(PREMIUM_USERS_FILE, "w") as f:
        json.dump(data, f, indent=2)


# ─────────────────────────────────────────────
# /start
# ─────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    user_id = str(user.id)
    username = user.username or user.first_name

    users = load_premium_users()

    # New user
    if user_id not in users:
        expiry = datetime.now() + timedelta(days=36500)
        users[user_id] = {
            "username": username,
            "expiry_time": expiry.timestamp(),
            "is_premium": True,
            "preferences": {
                "job_keywords": "",
                "experience": "",
                "location": ""
            }
        }
        save_premium_users(users)
        await update.message.reply_text(
            f"👋 Welcome *{username}* to Premium Naukri Bot! 🎉\n\n"
            f"Let's set up your job preferences so we can send you matching jobs.",
            parse_mode="Markdown"
        )
        await update.message.reply_text(
            "🔍 Enter 1–5 job keywords separated by commas:\n"
            "Example: `python, devops, aws, kubernetes`",
            parse_mode="Markdown"
        )
        return TITLE

    # Existing user
    prefs = users[user_id].get("preferences", {})
    has_prefs = all([
        prefs.get("job_keywords"),
        prefs.get("experience"),
        prefs.get("location")
    ])

    if has_prefs:
        keyboard = [
            [InlineKeyboardButton("✏️ Edit Keywords", callback_data="edit_keywords")],
            [InlineKeyboardButton("✏️ Edit Experience", callback_data="edit_experience")],
            [InlineKeyboardButton("✏️ Edit Location", callback_data="edit_location")],
            [InlineKeyboardButton("👍 Keep Current", callback_data="keep_preferences")],
        ]
        await update.message.reply_text(
            f"👋 Welcome back *{username}*!\n\n"
            f"Your current preferences:\n"
            f"🔍 Keywords: `{prefs.get('job_keywords', 'Not set')}`\n"
            f"⏳ Experience: `{prefs.get('experience', 'Not set')}` yrs\n"
            f"📍 Location: `{prefs.get('location', 'Not set')}`\n\n"
            f"Want to update them?",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        return EDIT_PREFERENCES
    else:
        await update.message.reply_text(
            "🔍 Enter 1–5 job keywords separated by commas:\n"
            "Example: `python, devops, aws, kubernetes`",
            parse_mode="Markdown"
        )
        return TITLE


# ─────────────────────────────────────────────
# Collect keywords
# ─────────────────────────────────────────────
async def job_title(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = str(update.effective_user.id)
    keywords = update.message.text.strip()

    users = load_premium_users()
    if user_id in users:
        users[user_id]["preferences"]["job_keywords"] = keywords
        save_premium_users(users)

    await update.message.reply_text(f"✅ Keywords saved: `{keywords}`\n\n📊 Now enter your total experience in years (e.g. `4`):", parse_mode="Markdown")
    return EXPERIENCE


# ─────────────────────────────────────────────
# Collect experience
# ─────────────────────────────────────────────
async def experience_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = str(update.effective_user.id)
    exp = update.message.text.strip()

    users = load_premium_users()
    if user_id in users:
        users[user_id]["preferences"]["experience"] = exp
        save_premium_users(users)

    await update.message.reply_text(f"✅ Experience saved: `{exp}` yrs\n\n📍 Enter your preferred job location (e.g. `Mumbai, Pune`):", parse_mode="Markdown")
    return LOCATION


# ─────────────────────────────────────────────
# Collect location
# ─────────────────────────────────────────────
async def location_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = str(update.effective_user.id)
    loc = update.message.text.strip()

    users = load_premium_users()
    if user_id in users:
        users[user_id]["preferences"]["location"] = loc
        save_premium_users(users)

    prefs = users[user_id]["preferences"]
    await update.message.reply_text(
        f"🎉 *Preferences saved!*\n\n"
        f"🔍 Keywords: `{prefs['job_keywords']}`\n"
        f"⏳ Experience: `{prefs['experience']}` yrs\n"
        f"📍 Location: `{prefs['location']}`\n\n"
        f"You will now receive matching job alerts directly here! ✅",
        parse_mode="Markdown"
    )
    return ConversationHandler.END


# ─────────────────────────────────────────────
# Edit preference callbacks
# ─────────────────────────────────────────────
async def edit_keywords(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(
        "🔍 Enter new keywords (comma-separated):\nExample: `python, devops, aws`",
        parse_mode="Markdown"
    )
    return TITLE


async def edit_experience(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(
        "⏳ Enter your years of experience (e.g. `4`):",
        parse_mode="Markdown"
    )
    return EXPERIENCE


async def edit_location(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(
        "📍 Enter your preferred location (e.g. `Mumbai, Pune`):",
        parse_mode="Markdown"
    )
    return LOCATION


async def keep_preferences(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    user_id = str(update.callback_query.from_user.id)
    users = load_premium_users()
    prefs = users[user_id]["preferences"]
    await update.callback_query.edit_message_text(
        f"👍 Preferences unchanged:\n\n"
        f"🔍 Keywords: `{prefs.get('job_keywords', 'Not set')}`\n"
        f"⏳ Experience: `{prefs.get('experience', 'Not set')}` yrs\n"
        f"📍 Location: `{prefs.get('location', 'Not set')}`",
        parse_mode="Markdown"
    )
    return ConversationHandler.END


# ─────────────────────────────────────────────
# /cancel
# ─────────────────────────────────────────────
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Setup cancelled. Use /start to begin again.")
    return ConversationHandler.END


# ─────────────────────────────────────────────
# /mypreferences
# ─────────────────────────────────────────────
async def my_preferences(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    users = load_premium_users()
    if user_id not in users:
        await update.message.reply_text("You are not registered. Use /start to set up.")
        return
    prefs = users[user_id].get("preferences", {})
    await update.message.reply_text(
        f"📋 *Your current preferences:*\n\n"
        f"🔍 Keywords: `{prefs.get('job_keywords', 'Not set')}`\n"
        f"⏳ Experience: `{prefs.get('experience', 'Not set')}` yrs\n"
        f"📍 Location: `{prefs.get('location', 'Not set')}`",
        parse_mode="Markdown"
    )


# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────
def run_premium_bot(token=None):
    token = token or PREMIUM_BOT_TOKEN

    app = Application.builder().token(token).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, job_title)],
            EXPERIENCE: [MessageHandler(filters.TEXT & ~filters.COMMAND, experience_handler)],
            LOCATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, location_handler)],
            EDIT_PREFERENCES: [
                CallbackQueryHandler(edit_keywords,    pattern="^edit_keywords$"),
                CallbackQueryHandler(edit_experience,  pattern="^edit_experience$"),
                CallbackQueryHandler(edit_location,    pattern="^edit_location$"),
                CallbackQueryHandler(keep_preferences, pattern="^keep_preferences$"),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(conv)
    app.add_handler(CommandHandler("mypreferences", my_preferences))

    logger.info("Starting Premium Naukri Bot (v20 async)...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    run_premium_bot()