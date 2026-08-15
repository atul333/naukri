"""
Advanced Advertisement Module for Naukri Telegram Channel
Features dynamic high-converting VIP promotional cards with rich HTML styling,
decorative ASCII borders, tech stack highlights, and interactive inline action buttons.
"""
import os
import random
import logging
import asyncio
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_USERNAME = "Premium_Naukri_bot"
BOT_URL = f"https://t.me/{BOT_USERNAME}"


# ─────────────────────────────────────────────────────────────
# Ultra-Advanced Advertisement Cards
# ─────────────────────────────────────────────────────────────

def get_ad_vip_radar():
    """Style 1: VIP AI-Powered Job Radar Card"""
    return """
╔═════════════════════════════════╗
   💎 <b>VIP NAUKRI JOB RADAR (100% FREE)</b>
╚═════════════════════════════════╝

⚡️ <b>Tired of applying late to job postings?</b>
Over 80% of recruiters review only the <b>first 25 applicants</b>. Stop scrolling through irrelevant jobs manually!

🌟 <b>SUPERCHARGE YOUR JOB SEARCH:</b>
━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 <b>Custom Skill Filters</b> ➔ Python, DevOps, AWS, Java, React & more
⏳ <b>Experience Matching</b> ➔ 0–1 yr, 3–5 yrs, 5–8+ yrs exact match
📍 <b>Location Precision</b> ➔ Remote, Bengaluru, Pune, Hyderabad, NCR
⚡ <b>Lightning Speed</b> ➔ Alerts delivered in <b>&lt; 60 seconds</b> of posting!
━━━━━━━━━━━━━━━━━━━━━━━━━

🔥 <b>Never miss your dream job again — 100% Free Forever!</b>

👉 <b>Activate VIP Alerts:</b> <a href="{bot_url}">@{bot_username}</a>
""".format(bot_url=BOT_URL, bot_username=BOT_USERNAME).strip()


def get_ad_first_mover():
    """Style 2: The 60-Second First-Mover Advantage Card"""
    return """
┌─────────────────────────────────┐
   🚀 <b>BE THE #1 APPLICANT ON NAUKRI.COM</b>
└─────────────────────────────────┘

⏰ <b>Speed is Everything in Tech Hiring!</b>
When a top tech company opens a vacancy, hundreds apply within hours.

🤖 <b>Our Automated Bot Works For You 24/7:</b>
✅ Scans live Naukri openings every minute
✅ Filters strictly by YOUR tech stack & experience
✅ Sends instant private Telegram alerts directly to you
✅ Apply before 99% of other candidates even see the post!

━━━━━━━━━━━━━━━━━━━━━━━━━
💼 <b>Supported Tech Domains:</b>
☁️ <i>DevOps & Cloud</i>  •  🐍 <i>Python & Django</i>
⚛️ <i>Full Stack & React</i>  •  ☕ <i>Java & Spring Boot</i>
🤖 <i>AI / ML & Data</i>  •  🧪 <i>QA Automation</i>
━━━━━━━━━━━━━━━━━━━━━━━━━

👇 <b>Tap below to configure your custom job radar in 30 seconds!</b>
""".strip()


def get_ad_personalized_engine():
    """Style 3: Private Personalized Match Engine Card"""
    return """
╔═════════════════════════════════╗
   🎯 <b>PRIVATE JOB ALERT ENGINE</b>
╚═════════════════════════════════╝

📢 <b>Stop sorting through hundreds of irrelevant job posts!</b>
Get only the jobs that match <b>YOUR exact skills, years of experience, and preferred city</b>.

✨ <b>WHY TECH PROFESSIONALS LOVE OUR BOT:</b>
🔹 <b>1-Click Presets:</b> Instant setup for all major IT stacks
🔹 <b>Direct Apply Links:</b> Fast, decrypted direct Naukri links
🔹 <b>Zero Spam:</b> Only alerts matching your configured criteria
🔹 <b>Private Chat Delivery:</b> Clean alerts sent straight to your DMs

━━━━━━━━━━━━━━━━━━━━━━━━━
🏆 <b>100% FREE VIP ACCESS FOR CHANNEL MEMBERS</b>
━━━━━━━━━━━━━━━━━━━━━━━━━

👉 <b>Start your personal radar:</b> <a href="{bot_url}">@{bot_username}</a>
""".format(bot_url=BOT_URL, bot_username=BOT_USERNAME).strip()


def get_ad_career_booster():
    """Style 4: Smart Career Automation Suite Card"""
    return """
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
   ⚡ <b>SMART NAUKRI ALERT BOT v2.0</b>
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

💡 <b>Job hunting doesn't have to be full-time work!</b>
Let our automated cloud bot monitor Naukri.com around the clock while you focus on interview prep.

📊 <b>HOW IT WORKS:</b>
1️⃣ Tap <a href="{bot_url}">@{bot_username}</a>
2️⃣ Select your tech stack, experience & target cities
3️⃣ Relax! Get real-time alerts the second a matching role drops

━━━━━━━━━━━━━━━━━━━━━━━━━
💎 <b>Instant Notifications • Custom Keywords • 100% Free</b>
━━━━━━━━━━━━━━━━━━━━━━━━━

🚀 <b>Click below to get started now:</b>
""".format(bot_url=BOT_URL, bot_username=BOT_USERNAME).strip()


def get_ad_tech_talent():
    """Style 5: Exclusive VIP Tech Talent Alert Card"""
    return """
╭─────────────────────────────────╮
   ⭐ <b>EXCLUSIVE VIP JOB ALERTS</b>
╰─────────────────────────────────╯

🎯 <b>Looking for your next high-paying tech role?</b>
Whether you're targeting <b>Remote</b>, <b>Bengaluru</b>, <b>Pune</b>, <b>Hyderabad</b>, or <b>Mumbai</b> — get priority notifications!

🌟 <b>KEY HIGHLIGHTS:</b>
⚡ <b>Real-time Scrapes:</b> Active monitoring every 60s
🎯 <b>Smart Skill Parser:</b> Accurate tech matching
💰 <b>Salary & Experience Insights:</b> Clean structured cards
📱 <b>Interactive Dashboard:</b> Update preferences anytime with 1 tap

━━━━━━━━━━━━━━━━━━━━━━━━━
🔥 <b>Join engineers staying ahead of the competition!</b>
━━━━━━━━━━━━━━━━━━━━━━━━━

👉 <b>Launch Bot:</b> <a href="{bot_url}">@{bot_username}</a>
""".format(bot_url=BOT_URL, bot_username=BOT_USERNAME).strip()


# All available creative templates
AD_TEMPLATES = [
    get_ad_vip_radar,
    get_ad_first_mover,
    get_ad_personalized_engine,
    get_ad_career_booster,
    get_ad_tech_talent
]


def build_ad_keyboard():
    """Creates high-visibility interactive inline CTA buttons"""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🚀 Launch Free VIP Bot", url=BOT_URL),
        ],
        [
            InlineKeyboardButton("⚡ Set Custom Job Filters", url=BOT_URL),
        ]
    ])


# ─────────────────────────────────────────────────────────────
# Sender Functions
# ─────────────────────────────────────────────────────────────

def send_advertisement_to_channel(telegram_token, channel_id):
    """
    Sends a randomly chosen advanced advertisement message with interactive
    inline buttons to the specified Telegram channel.
    """
    try:
        # Pick random template
        ad_func = random.choice(AD_TEMPLATES)
        ad_message = ad_func()
        reply_markup = build_ad_keyboard()

        async def _send():
            bot = Bot(token=telegram_token)
            await bot.send_message(
                chat_id=channel_id,
                text=ad_message,
                parse_mode='HTML',
                disable_web_page_preview=True,
                reply_markup=reply_markup
            )

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            asyncio.create_task(_send())
        else:
            asyncio.run(_send())

        logger.info(f"✅ Advanced advertisement sent to channel {channel_id}")
        return True
    except Exception as e:
        logger.error(f"❌ Error sending advertisement: {str(e)}")
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