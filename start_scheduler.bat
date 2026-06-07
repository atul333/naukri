@echo off
echo ============================================
echo  Naukri.com Job Scraper - Full Automation
echo ============================================
echo.
echo This will:
echo  1. Open Naukri.com IT Jobs page
echo  2. Sort results by Date (newest first)
echo  3. Extract the first (latest) job
echo  4. Post it to Telegram channel
echo  5. Repeat every 60 seconds automatically
echo.
echo Press Ctrl+C to stop.
echo.
python test_extract_first_job.py
pause