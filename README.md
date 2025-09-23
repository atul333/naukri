# Naukri.com Job Scraper and Telegram Bot

This bot automatically scrapes job postings from Naukri.com and posts them to a specified Telegram channel.

## Features

- Scrapes job listings from Naukri.com
- Extracts job details (title, company, location, posted date, apply link)
- Stores job information in a SQLite database to prevent duplicates
- Posts new job listings to a Telegram channel
- Runs on a schedule (every 30 minutes by default)

## Setup

1. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

2. Install Playwright browsers:
   ```
   playwright install
   ```

3. Configure your Telegram bot token and channel ID in `main.py` (already set up with the provided values)

4. Run the bot:
   ```
   python main.py
   ```

## Configuration

The following parameters can be modified in the `main.py` file:

- `job_url`: The URL of the job listings page to scrape
- `telegram_token`: Your Telegram bot token
- `channel_id`: Your Telegram channel ID
- Scheduling interval (default is 30 minutes)

## Requirements

- Python 3.7+
- BeautifulSoup4
- Playwright
- python-telegram-bot
- SQLite3 (included with Python)