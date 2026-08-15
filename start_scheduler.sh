#!/bin/bash
echo "============================================"
echo " Job Scraper - Full Automation"
echo "============================================"
echo ""

# Clean up any leftover zombie browser processes from previous runs
pkill -9 -f firefox 2>/dev/null || true
pkill -9 -f playwright 2>/dev/null || true

# Activate venv if present
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
fi

python3 test_extract_first_job.py

