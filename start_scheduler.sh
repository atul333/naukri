#!/bin/bash
echo "============================================"
echo " Job Scraper - Full Automation"
echo "============================================"
echo ""

# Clean up any leftover processes from previous runs
pkill -9 -f test_extract_first_job.py 2>/dev/null || true
pkill -9 -f firefox 2>/dev/null || true
pkill -9 -f playwright 2>/dev/null || true

# Activate virtualenv if present (supports both vnev and venv)
if [ -f "vnev/bin/activate" ]; then
    source vnev/bin/activate
elif [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
fi

python3 test_extract_first_job.py

