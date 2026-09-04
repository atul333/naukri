"""
Configuration & Environment Loader for Naukri Job Scraper
Loads multi-channel settings from .env file and normalizes channel identifiers.
"""
import os
import logging

logger = logging.getLogger("config")

# Automatically load .env file
try:
    from dotenv import load_dotenv
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.exists(env_path):
        load_dotenv(dotenv_path=env_path)
    else:
        load_dotenv()
except ImportError:
    pass


def parse_channel_ids(channels):
    """
    Parses channel identifier(s) from a list, comma-separated string, or single string.
    Supports:
      - @channel_name
      - https://t.me/channel_name -> @channel_name
      - -1001234567890 (numeric IDs)
    Returns a list of clean channel identifiers.
    """
    if not channels:
        return []

    if isinstance(channels, str):
        raw_list = [c.strip() for c in channels.replace("\n", ",").split(",") if c.strip()]
    elif isinstance(channels, (list, tuple, set)):
        raw_list = [str(c).strip() for c in channels if str(c).strip()]
    else:
        raw_list = [str(channels).strip()]

    cleaned = []
    for item in raw_list:
        item = item.strip().strip("'\"")
        if not item:
            continue

        # Convert https://t.me/channel_name to @channel_name
        if "t.me/" in item:
            parsed_path = item.split("t.me/")[-1].strip("/").split("?")[0]
            if parsed_path:
                if parsed_path.startswith("+") or parsed_path.startswith("joinchat/"):
                    item = item
                elif not parsed_path.startswith("@") and not parsed_path.startswith("-"):
                    item = f"@{parsed_path}"
                else:
                    item = parsed_path
        elif not item.startswith("@") and not item.startswith("-") and not item.isdigit():
            item = f"@{item}"

        if item and item not in cleaned:
            cleaned.append(item)

    return cleaned


# Telegram Bot Token (from .env or default)
TELEGRAM_BOT_TOKEN = (
    os.getenv("TELEGRAM_BOT_TOKEN") 
    or os.getenv("TELEGRAM_TOKEN") 
    or "8737613068:AAGtpmp32TVyz7YACORGYhNta89HJDg3HFg"
)
TELEGRAM_TOKEN = TELEGRAM_BOT_TOKEN

# Telegram Channels (from .env)
_raw_channels = (
    os.getenv("TELEGRAM_CHANNELS") 
    or os.getenv("TELEGRAM_CHANNEL_IDS") 
    or os.getenv("CHANNEL_ID") 
    or "@IT_Job_openings_Naukri,@job_opening_free"
)
TELEGRAM_CHANNELS = parse_channel_ids(_raw_channels)
PRIMARY_CHANNEL_ID = TELEGRAM_CHANNELS[0] if TELEGRAM_CHANNELS else "@IT_Job_openings_Naukri"
CHANNEL_ID = PRIMARY_CHANNEL_ID

# Premium Bot Token & Admin ID
PREMIUM_BOT_TOKEN = (
    os.getenv("PREMIUM_BOT_TOKEN") 
    or os.getenv("PREMIUM_TOKEN") 
    or "8762043028:AAEtOD5gkXQVkf8BTk4HYgukBQfiEp5HoK8"
)
PREMIUM_TOKEN = PREMIUM_BOT_TOKEN
ADMIN_TELEGRAM_ID = os.getenv("ADMIN_TELEGRAM_ID", "7708376300")
