import os
import subprocess
import random
import time
from datetime import datetime, timezone, timedelta

IST = timezone(timedelta(hours=5, minutes=30))

# -----------------------------------------------------------------------
# Carrier → scraper path mapping (add new carriers here only)
# -----------------------------------------------------------------------
SCRAPERS = {
    "6E": {
        "name":   "IndiGo",
        "prefix": "indigo_raw",
        "script": "indigo/indigo_scraper_uc.py",
    },
    "AI": {
        "name":   "Air India",
        "prefix": "air_india_raw",
        "script": "air_india/air_india_scraper.py",
    },
    "SG": {
        "name":   "SpiceJet",
        "prefix": "spicejet_raw",
        "script": "spicejet/spicejet_scraper.py",
    },
    "QP": {
        "name":   "Akasa Air",
        "prefix": "akasa_raw",
        "script": "akasa/akasa_scraper.py",
    },
}

REQUIRED_WINDOWS = {1, 7, 15, 30, 45}

# Inter-scraper cooling period in seconds (jitter applied on top)
INTER_SCRAPER_COOLDOWN = 60


def get_completed_horizons(prefix: str, today_str: str) -> set:
    """Return the set of advance-purchase-day integers already on disk."""
    raw_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "apix_data", "raw", today_str)
    if not os.path.exists(raw_dir):
        return set()

    completed = set()
    for fname in os.listdir(raw_dir):
        if fname.startswith(prefix) and fname.endswith(".csv"):
            parts = fname.split("_batch_")
            if len(parts) > 1:
                windows_part = parts[1].split("_")[0]  # e.g. "T1-T7-T15"
                for w in windows_part.split("-"):
                    try:
                        completed.add(int(w.replace("T", "")))
                    except ValueError:
                        pass
    return completed


def run_scraper(script: str, missing: set) -> bool:
    """
    Invoke a scraper for the given missing windows.
    --windows accepts comma-separated plain integers (e.g. "1,7,15").
    Returns True on success, False on error.
    """
    if not missing:
        return True

    windows_str = ",".join(str(w) for w in sorted(missing))
    base = os.path.dirname(os.path.abspath(__file__))

    print(f"\n{'='*62}")
    print(f"  🚀  {script}  →  windows: {windows_str}")
    print(f"{'='*62}")

    # Try xvfb-run first (CI / Linux); fall back for macOS dev machines
    for cmd in (
        ["xvfb-run", "--auto-servernum", "python3", script, "--windows", windows_str],
        ["python3", script, "--windows", windows_str],
    ):
        try:
            subprocess.run(cmd, cwd=base, check=True)
            return True
        except FileNotFoundError:
            if cmd[0] == "xvfb-run":
                print("  xvfb-run not found — running without virtual display (macOS mode).")
                continue
            print(f"  ❌  Script not found: {script}")
            return False
        except subprocess.CalledProcessError as e:
            print(f"  ❌  {script} exited with code {e.returncode}")
            return False

    return False


def main():
    now = datetime.now(IST)
    today_str = now.strftime("%Y-%m-%d")

    print(f"\n{'='*62}")
    print(f"  APIx Smart Orchestrator  —  {now.strftime('%Y-%m-%d %H:%M IST')}")
    print(f"{'='*62}")
    print(f"  Required windows: T+{', T+'.join(str(w) for w in sorted(REQUIRED_WINDOWS))}")

    # ---------------------------------------------------------------
    # 1. Audit what is already on disk for today
    # ---------------------------------------------------------------
    status = {}
    all_done = True
    for code, cfg in SCRAPERS.items():
        completed = get_completed_horizons(cfg["prefix"], today_str)
        missing   = REQUIRED_WINDOWS - completed
        status[code] = {"completed": completed, "missing": missing}
        print(f"\n  [{cfg['name']:12s} ({code})]  "
              f"done={sorted(completed) or '—'}   "
              f"missing={sorted(missing) or '—'}")
        if missing:
            all_done = False

    if all_done:
        print("\n  ✅  All data already collected for today. Nothing to do.")
        return

    # ---------------------------------------------------------------
    # 2. Run scrapers in fixed order with inter-scraper cooldowns.
    #    Longest scrapers (IndiGo, Air India) run first so the most
    #    critical T+1/T+7 data lands earliest.
    # ---------------------------------------------------------------
    RUN_ORDER = ["6E", "AI", "SG", "QP"]
    results   = {}

    for i, code in enumerate(RUN_ORDER):
        cfg     = SCRAPERS[code]
        missing = status[code]["missing"]

        if not missing:
            print(f"\n  ⏭   {cfg['name']} — already complete, skipping.")
            results[code] = True
            continue

        ok = run_scraper(cfg["script"], missing)
        results[code] = ok

        # Cooldown between scrapers (skip after the last active one)
        remaining_with_work = [c for c in RUN_ORDER[i+1:] if status[c]["missing"]]
        if remaining_with_work:
            jitter = random.uniform(-10, 10)
            wait   = max(30, INTER_SCRAPER_COOLDOWN + jitter)
            print(f"\n  ⏳  Cooling off {wait:.0f}s before next airline...")
            time.sleep(wait)

    # ---------------------------------------------------------------
    # 3. Final summary
    # ---------------------------------------------------------------
    print(f"\n{'='*62}")
    print("  ORCHESTRATOR SUMMARY")
    print(f"{'='*62}")
    for code in RUN_ORDER:
        cfg  = SCRAPERS[code]
        miss = status[code]["missing"]
        if not miss:
            print(f"  ✅  {cfg['name']:12s} — was already complete")
        elif results.get(code):
            print(f"  ✅  {cfg['name']:12s} — scraped T+{sorted(miss)} successfully")
        else:
            print(f"  ❌  {cfg['name']:12s} — FAILED for T+{sorted(miss)}")
    print()


if __name__ == "__main__":
    main()
