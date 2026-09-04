#!/bin/bash

# Udaan Metrics Automated Scheduler Wrapper
# Delegates to smart_orchestrator.py which handles all 4 carriers
# (IndiGo, Air India, SpiceJet, Akasa) with state-aware skip logic,
# inter-scraper cooldowns, and a final summary.
#
# Usage:
#   ./schedule_udaan.sh              — full run, all 5 horizons (T+1..T+45)
#   ./schedule_udaan.sh 1,7          — targeted run for specific windows only
#
# The orchestrator itself skips any windows already present in udaan_data/
# so it is safe to re-run this script as a cron retry.

set -euo pipefail

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

echo "====================================================="
echo " Udaan Metrics Scrape Run"
echo " Time: $(date '+%Y-%m-%d %H:%M %Z')"
echo "====================================================="

python3 smart_orchestrator.py

EXIT_CODE=$?

echo "====================================================="
if [ $EXIT_CODE -eq 0 ]; then
    echo " ✅  Orchestrator completed successfully."
else
    echo " ❌  Orchestrator exited with code $EXIT_CODE."
fi
echo " Time: $(date '+%Y-%m-%d %H:%M %Z')"
echo "====================================================="

exit $EXIT_CODE
