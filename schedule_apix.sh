#!/bin/bash

# APIx Automated Scheduler Wrapper
# This script wraps the IndiGo and SpiceJet scrapers to ensure they 
# run sequentially (not in parallel) to prevent IP rate-limiting or
# system memory exhaustion (since Chrome is memory-heavy).

# Get the directory where this script is located
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

# Ensure we have arguments
if [ -z "$1" ]; then
    echo "Usage: ./schedule_apix.sh [windows]"
    echo "Example: ./schedule_apix.sh 1,7"
    exit 1
fi

WINDOWS=$1

echo "====================================================="
echo " Starting APIx Scrape Run for Horizons: T+$WINDOWS"
echo " Time: $(date)"
echo "====================================================="

# 1. Run IndiGo Scraper
echo "[1/2] Launching IndiGo Scraper for T+$WINDOWS..."
python3 indigo/indigo_scraper_uc.py --windows "$WINDOWS"
if [ $? -ne 0 ]; then
    echo "❌ IndiGo scraper encountered an error."
else
    echo "✅ IndiGo scraper completed."
fi

# 2. Add a cooling off period between airlines just to be safe
echo "Cooling off for 60 seconds before launching SpiceJet..."
sleep 60

# 3. Run SpiceJet Scraper
echo "[2/2] Launching SpiceJet Scraper for T+$WINDOWS..."
python3 spicejet/spicejet_scraper.py --windows "$WINDOWS"
if [ $? -ne 0 ]; then
    echo "❌ SpiceJet scraper encountered an error."
else
    echo "✅ SpiceJet scraper completed."
fi

echo "====================================================="
echo " APIx Scrape Run Complete!"
echo " Time: $(date)"
echo "====================================================="
