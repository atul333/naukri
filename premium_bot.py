"""
Premium Naukri Bot — python-telegram-bot v20 (async)
Advanced interactive UI with rich dashboard, 1-click tech stack presets,
smart experience pickers, location selectors, and instant VIP notifications.
"""
import os
import json
import logging
import asyncio
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
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
STATE_KEYWORDS, STATE_EXPERIENCE, STATE_LOCATION, STATE_MENU = range(4)

PREMIUM_USERS_FILE = "premium_users.json"
PREMIUM_BOT_TOKEN = "8762043028:AAEtOD5gkXQVkf8BTk4HYgukBQfiEp5HoK8"
ADMIN_TELEGRAM_ID = "7708376300"


# ─────────────────────────────────────────────
# Admin Notification Helper
# ─────────────────────────────────────────────
async def notify_admin_preference_update(bot, user, prefs, updated_field="Preferences Updated"):
    """
    Sends an instant alert to Admin (7708376300) whenever a user saves or updates preferences.
    """
    try:
        keywords = prefs.get("job_keywords") or "Not set"
        experience = prefs.get("experience") or "Not set"
        location = prefs.get("location") or "Not set"
        username_str = f"@{user.username}" if user.username else "No username"

        admin_msg = (
            "🔔 <b>NEW VIP PREFERENCE SUBMITTED</b>\n\n"
            f"👤 <b>User:</b> {user.full_name} ({username_str})\n"
            f"🆔 <b>User ID:</b> <code>{user.id}</code>\n"
            f"⚡ <b>Action:</b> {updated_field}\n\n"
            "📋 <b>Configured Profile:</b>\n"
            f"🎯 <b>Keywords:</b> <code>{keywords}</code>\n"
            f"⏳ <b>Experience:</b> <code>{experience} Yrs</code>\n"
            f"📍 <b>Location:</b> <code>{location}</code>\n\n"
            f"🕒 <b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        await bot.send_message(
            chat_id=ADMIN_TELEGRAM_ID,
            text=admin_msg,
            parse_mode="HTML"
        )
        logger.info(f"Admin notified for user {user.id} ({updated_field})")
    except Exception as e:
        logger.warning(f"Could not notify admin {ADMIN_TELEGRAM_ID}: {e}")


# ─────────────────────────────────────────────
# Tech Stack Presets
# ─────────────────────────────────────────────
PRESET_STACKS = {
    "preset_devops": {
        "label": "☁️ DevOps & Cloud",
        "keywords": "DevOps, AWS, Kubernetes, Docker, Terraform, CI/CD, Linux"
    },
    "preset_python": {
        "label": "🐍 Python & Backend",
        "keywords": "Python, Django, FastAPI, Flask, PostgreSQL, REST API"
    },
    "preset_fullstack": {
        "label": "⚛️ Full Stack (React / Node)",
        "keywords": "React, Node.js, TypeScript, JavaScript, Next.js, MongoDB"
    },
    "preset_java": {
        "label": "☕ Java & Spring Boot",
        "keywords": "Java, Spring Boot, Microservices, Hibernate, REST API, SQL"
    },
    "preset_data": {
        "label": "🤖 AI, ML & Data Science",
        "keywords": "Python, Machine Learning, Data Science, AI, Deep Learning, SQL"
    },
    "preset_qa": {
        "label": "🧪 QA & Automation",
        "keywords": "Automation Testing, Selenium, QA, Python, Java, TestNG, API Testing"
    },
    "preset_dataeng": {
        "label": "📊 Data Engineering",
        "keywords": "Data Engineer, PySpark, Spark, SQL, ETL, AWS, Hadoop, Kafka"
    },
    "preset_security": {
        "label": "🛡️ Cyber Security",
        "keywords": "Cyber Security, SOC, Penetration Testing, SIEM, CISSP, Network Security"
    }
}

# ─────────────────────────────────────────────
# Helper Functions
# ─────────────────────────────────────────────
def load_premium_users():
    try:
        if os.path.exists(PREMIUM_USERS_FILE):
            with open(PREMIUM_USERS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Error loading premium users: {e}")
    return {}


def save_premium_users(data):
    try:
        with open(PREMIUM_USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving premium users: {e}")


def get_user_record(user):
    user_id = str(user.id)
    username = user.username or user.first_name or "VIP Member"
    users = load_premium_users()

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
    else:
        # Keep username updated
        if users[user_id].get("username") != username:
            users[user_id]["username"] = username
            save_premium_users(users)

    return users[user_id], users


def build_dashboard_text(user, user_data):
    prefs = user_data.get("preferences", {})
    keywords = prefs.get("job_keywords", "").strip() or "⚠️ <i>Not configured</i>"
    experience = prefs.get("experience", "").strip()
    exp_display = f"<b>{experience} Yrs</b>" if experience else "⚠️ <i>Not configured</i>"
    location = prefs.get("location", "").strip() or "⚠️ <i>Not configured</i>"

    is_complete = bool(prefs.get("job_keywords") and prefs.get("experience") and prefs.get("location"))
    status_badge = "🟢 <b>ACTIVE (Matching 24/7)</b>" if is_complete else "🟡 <b>SETUP INCOMPLETE</b>"

    dashboard = (
        "╔══════════════════════════╗\n"
        "║  💎 <b>PREMIUM NAUKRI VIP BOT</b>  ║\n"
        "╚══════════════════════════╝\n\n"
        f"👋 Welcome, <b>{user.first_name}</b>!\n"
        f"⭐ <b>Status:</b> {status_badge}\n"
        f"🆔 <b>Member ID:</b> <code>{user.id}</code>\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "📋 <b>YOUR TARGET PREFERENCES:</b>\n"
        f"🎯 <b>Keywords:</b> <code>{keywords}</code>\n"
        f"⏳ <b>Experience:</b> {exp_display}\n"
        f"📍 <b>Locations:</b> <code>{location}</code>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    )

    if not is_complete:
        dashboard += (
            "💡 <i>Complete your profile below to get real-time private alerts</i>\n"
            "<i>whenever a matching job is posted!</i>"
        )
    else:
        dashboard += (
            "🚀 <b>Auto-Filter Active!</b> You will receive instant notifications\n"
            "as soon as freshly posted jobs match your profile."
        )

    return dashboard


def build_main_menu_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("⚡ Quick 1-Click Tech Stacks", callback_data="menu_presets"),
        ],
        [
            InlineKeyboardButton("🎯 Edit Keywords", callback_data="menu_edit_keywords"),
            InlineKeyboardButton("⏳ Edit Experience", callback_data="menu_edit_experience"),
        ],
        [
            InlineKeyboardButton("📍 Edit Location", callback_data="menu_edit_location"),
            InlineKeyboardButton("📋 View Card", callback_data="menu_view_card"),
        ],
        [
            InlineKeyboardButton("🧪 Test Match Preview", callback_data="menu_test_match"),
            InlineKeyboardButton("❓ Help & Guide", callback_data="menu_help"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


# ─────────────────────────────────────────────
# /start & /menu handlers
# ─────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    user_data, _ = get_user_record(user)

    dashboard_text = build_dashboard_text(user, user_data)
    reply_markup = build_main_menu_keyboard()

    if update.callback_query:
        await update.callback_query.answer()
        try:
            await update.callback_query.edit_message_text(
                dashboard_text,
                reply_markup=reply_markup,
                parse_mode="HTML",
                disable_web_page_preview=True
            )
        except Exception:
            await update.callback_query.message.reply_text(
                dashboard_text,
                reply_markup=reply_markup,
                parse_mode="HTML",
                disable_web_page_preview=True
            )
    else:
        await update.message.reply_text(
            dashboard_text,
            reply_markup=reply_markup,
            parse_mode="HTML",
            disable_web_page_preview=True
        )

    return STATE_MENU


# ─────────────────────────────────────────────
# Tech Stack Presets Menu
# ─────────────────────────────────────────────
async def show_presets_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    keyboard = []
    # Two presets per row
    preset_keys = list(PRESET_STACKS.keys())
    for i in range(0, len(preset_keys), 2):
        row = [InlineKeyboardButton(PRESET_STACKS[preset_keys[i]]["label"], callback_data=preset_keys[i])]
        if i + 1 < len(preset_keys):
            row.append(InlineKeyboardButton(PRESET_STACKS[preset_keys[i+1]]["label"], callback_data=preset_keys[i+1]))
        keyboard.append(row)

    keyboard.append([InlineKeyboardButton("✍️ Custom Keyword Input", callback_data="menu_edit_keywords")])
    keyboard.append([InlineKeyboardButton("🔙 Back to Main Menu", callback_data="nav_main_menu")])

    text = (
        "⚡ <b>POPULAR TECH STACK PRESETS</b>\n\n"
        "Select your domain to automatically apply curated high-frequency tech keywords:\n"
    )
    for p in PRESET_STACKS.values():
        text += f"• <b>{p['label']}:</b> <code>{p['keywords']}</code>\n"

    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )
    return STATE_MENU


async def handle_preset_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    preset_key = query.data

    if preset_key in PRESET_STACKS:
        preset = PRESET_STACKS[preset_key]
        user = update.effective_user
        user_id = str(user.id)

        users = load_premium_users()
        if user_id not in users:
            get_user_record(user)
            users = load_premium_users()

        users[user_id]["preferences"]["job_keywords"] = preset["keywords"]
        save_premium_users(users)

        # Notify admin of new preference selection
        await notify_admin_preference_update(
            context.bot, user, users[user_id]["preferences"],
            updated_field=f"Preset Applied ({preset['label']})"
        )

        keyboard = [
            [InlineKeyboardButton("⏳ Next: Select Experience", callback_data="menu_edit_experience")],
            [InlineKeyboardButton("🏠 Back to Main Menu", callback_data="nav_main_menu")]
        ]
        await query.edit_message_text(
            f"✅ <b>Applied Preset: {preset['label']}</b>\n\n"
            f"🎯 <b>Saved Keywords:</b>\n<code>{preset['keywords']}</code>\n\n"
            "👉 Next, let's configure your experience level.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
    return STATE_MENU


# ─────────────────────────────────────────────
# Keyword Setup Handlers
# ─────────────────────────────────────────────
async def prompt_keywords(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if query:
        await query.answer()
        keyboard = [
            [InlineKeyboardButton("⚡ Use 1-Click Presets", callback_data="menu_presets")],
            [InlineKeyboardButton("🔙 Cancel / Back", callback_data="nav_main_menu")]
        ]
        await query.edit_message_text(
            "🎯 <b>CONFIGURE JOB KEYWORDS</b>\n\n"
            "Send your target job titles or skills separated by commas.\n\n"
            "📌 <i>Examples:</i>\n"
            "• <code>DevOps, AWS, Kubernetes, Terraform</code>\n"
            "• <code>Python, Django, FastAPI, Backend</code>\n"
            "• <code>React, Node.js, TypeScript, Frontend</code>\n"
            "• <code>Java, Spring Boot, Microservices</code>\n\n"
            "✍️ <i>Type your keywords in the chat now:</i>",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
    else:
        await update.message.reply_text(
            "🎯 <b>Enter your keywords separated by commas:</b>\n"
            "Example: <code>python, devops, aws</code>",
            parse_mode="HTML"
        )
    return STATE_KEYWORDS


async def save_keywords_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    user_id = str(user.id)
    keywords = update.message.text.strip()

    users = load_premium_users()
    if user_id not in users:
        get_user_record(user)
        users = load_premium_users()

    users[user_id]["preferences"]["job_keywords"] = keywords
    save_premium_users(users)

    # Notify admin of updated keywords
    await notify_admin_preference_update(
        context.bot, user, users[user_id]["preferences"],
        updated_field=f"Keywords Updated: {keywords}"
    )

    keyboard = [
        [InlineKeyboardButton("⏳ Next: Select Experience", callback_data="menu_edit_experience")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="nav_main_menu")]
    ]
    await update.message.reply_text(
        f"✅ <b>Keywords Saved!</b>\n\n"
        f"🎯 <b>Keywords:</b> <code>{keywords}</code>\n\n"
        "👉 Now set your experience level to filter jobs accurately.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )
    return STATE_MENU


# ─────────────────────────────────────────────
# Experience Setup Handlers
# ─────────────────────────────────────────────
async def prompt_experience(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if query:
        await query.answer()

    keyboard = [
        [
            InlineKeyboardButton("🎓 0-1 Yr (Fresher)", callback_data="exp_0-1"),
            InlineKeyboardButton("🔹 1-3 Yrs (Junior)", callback_data="exp_1-3"),
        ],
        [
            InlineKeyboardButton("🔸 3-5 Yrs (Mid)", callback_data="exp_3-5"),
            InlineKeyboardButton("💼 5-8 Yrs (Senior)", callback_data="exp_5-8"),
        ],
        [
            InlineKeyboardButton("🏆 8+ Yrs (Lead)", callback_data="exp_8+"),
            InlineKeyboardButton("✍️ Custom Range / Number", callback_data="exp_custom"),
        ],
        [
            InlineKeyboardButton("🔙 Back to Main Menu", callback_data="nav_main_menu")
        ]
    ]

    text = (
        "⏳ <b>SELECT YOUR EXPERIENCE RANGE</b>\n\n"
        "Choose your experience range (e.g. 5-8 Yrs) or click 'Custom Range / Number' to type:"
    )

    if query:
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    else:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

    return STATE_MENU


async def handle_exp_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "exp_custom":
        keyboard = [[InlineKeyboardButton("🔙 Cancel", callback_data="nav_main_menu")]]
        await query.edit_message_text(
            "⏳ <b>Enter your experience range or number:</b>\n\n"
            "Examples: <code>5-8</code> or <code>4</code> or <code>3-6</code>\n\n"
            "✍️ <i>Type in chat now:</i>",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
        return STATE_EXPERIENCE

    exp_val = data.replace("exp_", "")
    user = update.effective_user
    user_id = str(user.id)

    users = load_premium_users()
    if user_id not in users:
        get_user_record(user)
        users = load_premium_users()

    users[user_id]["preferences"]["experience"] = exp_val
    save_premium_users(users)

    # Notify admin of updated experience
    await notify_admin_preference_update(
        context.bot, user, users[user_id]["preferences"],
        updated_field=f"Experience Set: {exp_val} Yrs"
    )

    keyboard = [
        [InlineKeyboardButton("📍 Next: Select Location", callback_data="menu_edit_location")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="nav_main_menu")]
    ]
    await query.edit_message_text(
        f"✅ <b>Experience Saved:</b> <b>{exp_val} Yrs</b>\n\n"
        "👉 Next, let's select your preferred job locations.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )
    return STATE_MENU


async def save_experience_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    user_id = str(user.id)
    exp = update.message.text.strip()

    users = load_premium_users()
    if user_id not in users:
        get_user_record(user)
        users = load_premium_users()

    users[user_id]["preferences"]["experience"] = exp
    save_premium_users(users)

    # Notify admin of updated experience
    await notify_admin_preference_update(
        context.bot, user, users[user_id]["preferences"],
        updated_field=f"Experience Set: {exp} Yrs"
    )

    keyboard = [
        [InlineKeyboardButton("📍 Next: Select Location", callback_data="menu_edit_location")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="nav_main_menu")]
    ]
    await update.message.reply_text(
        f"✅ <b>Experience Saved:</b> <b>{exp} Yrs</b>\n\n"
        "👉 Next, set your preferred job locations.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )
    return STATE_MENU


# ─────────────────────────────────────────────
# Location Setup Handlers
# ─────────────────────────────────────────────
async def prompt_location(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if query:
        await query.answer()

    keyboard = [
        [
            InlineKeyboardButton("🌐 Remote / Pan India", callback_data="loc_remote"),
            InlineKeyboardButton("🏙️ Bengaluru", callback_data="loc_bengaluru"),
        ],
        [
            InlineKeyboardButton("🏙️ Hyderabad", callback_data="loc_hyderabad"),
            InlineKeyboardButton("🏙️ Pune", callback_data="loc_pune"),
        ],
        [
            InlineKeyboardButton("🏙️ Mumbai", callback_data="loc_mumbai"),
            InlineKeyboardButton("🏙️ Delhi NCR / Gurgaon", callback_data="loc_delhi"),
        ],
        [
            InlineKeyboardButton("🏙️ Chennai", callback_data="loc_chennai"),
            InlineKeyboardButton("✍️ Custom City List", callback_data="loc_custom"),
        ],
        [
            InlineKeyboardButton("🔙 Back to Main Menu", callback_data="nav_main_menu")
        ]
    ]

    text = (
        "📍 <b>SELECT PREFERRED JOB LOCATION</b>\n\n"
        "Choose a major tech hub or click 'Custom City List' to enter multiple locations:"
    )

    if query:
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    else:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

    return STATE_MENU


async def handle_location_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "loc_custom":
        keyboard = [[InlineKeyboardButton("🔙 Cancel", callback_data="nav_main_menu")]]
        await query.edit_message_text(
            "📍 <b>Enter your preferred cities (comma-separated):</b>\n\n"
            "Examples:\n"
            "• <code>Bengaluru, Hyderabad, Remote</code>\n"
            "• <code>Pune, Mumbai</code>\n"
            "• <code>Noida, Gurgaon, Delhi</code>\n\n"
            "✍️ <i>Type your cities in chat now:</i>",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
        return STATE_LOCATION

    loc_map = {
        "loc_remote": "Remote, Any",
        "loc_bengaluru": "Bengaluru, Bangalore",
        "loc_hyderabad": "Hyderabad",
        "loc_pune": "Pune",
        "loc_mumbai": "Mumbai",
        "loc_delhi": "Delhi, NCR, Gurgaon, Noida",
        "loc_chennai": "Chennai"
    }
    loc_val = loc_map.get(data, "Remote")

    user = update.effective_user
    user_id = str(user.id)

    users = load_premium_users()
    if user_id not in users:
        get_user_record(user)
        users = load_premium_users()

    users[user_id]["preferences"]["location"] = loc_val
    save_premium_users(users)

    # Notify admin of updated location
    await notify_admin_preference_update(
        context.bot, user, users[user_id]["preferences"],
        updated_field=f"Location Set: {loc_val}"
    )

    keyboard = [
        [InlineKeyboardButton("📋 View Complete Profile", callback_data="menu_view_card")],
        [InlineKeyboardButton("🏠 Return to Dashboard", callback_data="nav_main_menu")]
    ]
    await query.edit_message_text(
        f"🎉 <b>PREFERENCES FULLY CONFIGURED!</b>\n\n"
        f"📍 <b>Location:</b> <code>{loc_val}</code>\n\n"
        "🟢 <b>VIP Alert Engine is ACTIVE.</b> You will now receive matching jobs "
        "directly in this chat the moment they are posted!",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )
    return STATE_MENU


async def save_location_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    user_id = str(user.id)
    loc = update.message.text.strip()

    users = load_premium_users()
    if user_id not in users:
        get_user_record(user)
        users = load_premium_users()

    users[user_id]["preferences"]["location"] = loc
    save_premium_users(users)

    # Notify admin of updated location
    await notify_admin_preference_update(
        context.bot, user, users[user_id]["preferences"],
        updated_field=f"Location Set: {loc}"
    )

    keyboard = [
        [InlineKeyboardButton("📋 View Complete Profile", callback_data="menu_view_card")],
        [InlineKeyboardButton("🏠 Return to Dashboard", callback_data="nav_main_menu")]
    ]
    await update.message.reply_text(
        f"🎉 <b>PREFERENCES FULLY CONFIGURED!</b>\n\n"
        f"📍 <b>Location:</b> <code>{loc}</code>\n\n"
        "🟢 <b>VIP Alert Engine is ACTIVE.</b> You will now receive matching jobs "
        "directly in this chat the moment they are posted!",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )
    return STATE_MENU



# ─────────────────────────────────────────────
# Profile Card & Test Preview
# ─────────────────────────────────────────────
async def view_profile_card(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if query:
        await query.answer()

    user = update.effective_user
    user_data, _ = get_user_record(user)
    prefs = user_data.get("preferences", {})

    keywords = prefs.get("job_keywords") or "Not set"
    experience = prefs.get("experience") or "Not set"
    location = prefs.get("location") or "Not set"
    is_active = bool(prefs.get("job_keywords") and prefs.get("experience") and prefs.get("location"))

    card = (
        "┌───────────────────────────────┐\n"
        "│  💎 <b>VIP MEMBER PROFILE CARD</b>        │\n"
        "├───────────────────────────────┤\n"
        f"│ 👤 <b>Name:</b> {user.full_name}\n"
        f"│ 🆔 <b>Telegram ID:</b> <code>{user.id}</code>\n"
        f"│ ⭐ <b>Tier:</b> Lifetime VIP Member\n"
        f"│ 🔔 <b>Direct Alerts:</b> {'🟢 ENABLED' if is_active else '🔴 INCOMPLETE'}\n"
        "├───────────────────────────────┤\n"
        f"│ 🎯 <b>Target Keywords:</b>\n│  <code>{keywords}</code>\n"
        "│\n"
        f"│ ⏳ <b>Experience Filter:</b>\n│  <b>{experience} Years</b>\n"
        "│\n"
        f"│ 📍 <b>Target Location:</b>\n│  <code>{location}</code>\n"
        "└───────────────────────────────┘\n"
    )

    keyboard = [
        [InlineKeyboardButton("✏️ Modify Preferences", callback_data="menu_presets")],
        [InlineKeyboardButton("🏠 Back to Dashboard", callback_data="nav_main_menu")]
    ]

    if query:
        await query.edit_message_text(card, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    else:
        await update.message.reply_text(card, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

    return STATE_MENU


async def test_match_preview(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    user = update.effective_user
    user_data, _ = get_user_record(user)
    prefs = user_data.get("preferences", {})

    keywords = prefs.get("job_keywords") or "DevOps, Python"
    exp = prefs.get("experience") or "3"
    loc = prefs.get("location") or "Bengaluru"

    sample_job = (
        "🧪 <b>SAMPLE NOTIFICATION PREVIEW</b>\n\n"
        "⚡ <b>NEW TECH OPENING</b>\n\n"
        f"💼 <b>Role:</b> <b>Senior {keywords.split(',')[0].strip()} Specialist</b>\n"
        "🏢 <b>Company:</b> Global Tech Solutions\n"
        f"⏳ <b>Experience:</b> <code>{exp}-8 Yrs</code>\n"
        f"📍 <b>Location:</b> <code>{loc.split(',')[0].strip()}</code>\n"
        "💰 <b>Salary / CTC:</b> <code>₹ 18 - 30 Lacs P.A.</code>\n\n"
        f"🏷️ #{(keywords.split(',')[0].strip()).replace(' ', '')} #VIPAlert\n\n"
        "⚡ <i>Matches are delivered in under 60 seconds of posting!</i>"
    )

    keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data="nav_main_menu")]]
    await query.edit_message_text(sample_job, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    return STATE_MENU


async def show_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if query:
        await query.answer()

    help_text = (
        "ℹ️ <b>HOW THE VIP ALERT BOT WORKS</b>\n\n"
        "1️⃣ <b>Live Scraper:</b> Our cloud scraper scans 24/7 for newly published IT jobs.\n"
        "2️⃣ <b>Smart Filter:</b> Every single job is parsed for title, skill hashtags, required experience, and location.\n"
        "3️⃣ <b>Instant Direct Delivery:</b> If a job matches your keywords, experience range, and city, it is sent to this private chat instantly!\n\n"
        "💡 <b>Tips for Best Matches:</b>\n"
        "• Add 3–6 relevant skill keywords (e.g. <code>aws, kubernetes, python, devops</code>)\n"
        "• Set your exact total experience\n"
        "• Include <code>Remote</code> if you are open to work-from-home\n\n"
        "<b>Commands:</b>\n"
        "• /start or /menu — Open interactive dashboard\n"
        "• /profile — View your current filters\n"
        "• /help — Show this guide\n"
        "• /cancel — Reset current prompt"
    )

    keyboard = [[InlineKeyboardButton("🏠 Back to Dashboard", callback_data="nav_main_menu")]]

    if query:
        await query.edit_message_text(help_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    else:
        await update.message.reply_text(help_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

    return STATE_MENU


async def cancel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    keyboard = [[InlineKeyboardButton("🏠 Open Dashboard", callback_data="nav_main_menu")]]
    await update.message.reply_text(
        "👋 Action cancelled. You can return to the dashboard anytime with /start or /menu.",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return STATE_MENU


# ─────────────────────────────────────────────
# Post-Init: Register Telegram Commands Menu
# ─────────────────────────────────────────────
async def post_init(application: Application):
    try:
        commands = [
            BotCommand("start", "Launch VIP Dashboard"),
            BotCommand("menu", "Main interactive menu"),
            BotCommand("profile", "View profile & filters"),
            BotCommand("help", "How matching works"),
            BotCommand("cancel", "Cancel current action"),
        ]
        await application.bot.set_my_commands(commands)
        logger.info("Bot commands menu registered with Telegram successfully")
    except Exception as e:
        logger.warning(f"Could not register bot commands: {e}")


# ─────────────────────────────────────────────
# Main Runner
# ─────────────────────────────────────────────
def run_premium_bot(token=None):
    token = token or PREMIUM_BOT_TOKEN

    app = Application.builder().token(token).post_init(post_init).build()

    conv = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CommandHandler("menu", start),
            CommandHandler("profile", view_profile_card),
            CommandHandler("mypreferences", view_profile_card),
            CommandHandler("help", show_help),
            CallbackQueryHandler(start, pattern="^nav_main_menu$"),
        ],
        states={
            STATE_MENU: [
                CallbackQueryHandler(show_presets_menu,      pattern="^menu_presets$"),
                CallbackQueryHandler(prompt_keywords,        pattern="^menu_edit_keywords$"),
                CallbackQueryHandler(prompt_experience,      pattern="^menu_edit_experience$"),
                CallbackQueryHandler(prompt_location,        pattern="^menu_edit_location$"),
                CallbackQueryHandler(view_profile_card,      pattern="^menu_view_card$"),
                CallbackQueryHandler(test_match_preview,     pattern="^menu_test_match$"),
                CallbackQueryHandler(show_help,              pattern="^menu_help$"),
                CallbackQueryHandler(start,                  pattern="^nav_main_menu$"),
                CallbackQueryHandler(handle_preset_selection,pattern="^preset_"),
                CallbackQueryHandler(handle_exp_button,      pattern="^exp_"),
                CallbackQueryHandler(handle_location_button, pattern="^loc_"),
            ],
            STATE_KEYWORDS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, save_keywords_text),
                CallbackQueryHandler(show_presets_menu, pattern="^menu_presets$"),
                CallbackQueryHandler(start, pattern="^nav_main_menu$"),
            ],
            STATE_EXPERIENCE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, save_experience_text),
                CallbackQueryHandler(handle_exp_button, pattern="^exp_"),
                CallbackQueryHandler(start, pattern="^nav_main_menu$"),
            ],
            STATE_LOCATION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, save_location_text),
                CallbackQueryHandler(handle_location_button, pattern="^loc_"),
                CallbackQueryHandler(start, pattern="^nav_main_menu$"),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_handler),
            CommandHandler("start", start),
            CommandHandler("menu", start),
            CommandHandler("profile", view_profile_card),
            CommandHandler("help", show_help),
        ],
        allow_reentry=True,
        per_message=False,
    )

    app.add_handler(conv)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", start))
    app.add_handler(CommandHandler("profile", view_profile_card))
    app.add_handler(CommandHandler("mypreferences", view_profile_card))
    app.add_handler(CommandHandler("help", show_help))

    logger.info("Starting Advanced Premium Naukri Bot (v20 async)...")
    app.run_polling(allowed_updates=Update.ALL_TYPES, stop_signals=None, close_loop=False)


if __name__ == "__main__":
    run_premium_bot()