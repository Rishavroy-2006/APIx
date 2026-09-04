# Udaan Metrics Scraper Schema Audit

This document summarizes the schema audit and schema drift analysis across all scraper scripts in the Udaan Metrics repository.

---

## 1. Scraper File Inventory & Overview

| Scraper Script | Carrier / Source | Status | Automation Engine | Output Naming Pattern under `udaan_data/raw/` |
|---|---|---|---|---|
| [`spicejet/spicejet_scraper.py`](file:///c:/Users/aritr/OneDrive/Desktop/LLM_flights/spicejet/spicejet_scraper.py) | SpiceJet (`SG`) | Present & Tested | `undetected-chromedriver` | `udaan_data/raw/<YYYY-MM-DD>/spicejet_raw_<YYYY-MM-DD>_batch_<windows>_<HHMM>IST.csv` |
| [`akasa/akasa_scraper.py`](file:///c:/Users/aritr/OneDrive/Desktop/LLM_flights/akasa/akasa_scraper.py) | Akasa Air (`QP`) | Present & Tested | `undetected-chromedriver` | `udaan_data/raw/<YYYY-MM-DD>/akasa_raw_<YYYY-MM-DD>_batch_<windows>_<HHMM>IST.csv` |
| [`indigo/indigo_scraper_uc.py`](file:///c:/Users/aritr/OneDrive/Desktop/LLM_flights/indigo/indigo_scraper_uc.py) | IndiGo (`6E`) | Present & Tested | `undetected-chromedriver` | `udaan_data/raw/<YYYY-MM-DD>/indigo_raw_<YYYY-MM-DD>_batch_<windows>_<HHMM>IST.csv` |
| [`air_india/air_india_scraper.py`](file:///c:/Users/aritr/OneDrive/Desktop/LLM_flights/air_india/air_india_scraper.py) | Air India (`AI` / `IX`) | Present & Tested | `seleniumbase` (`SB(uc=True)`) | `udaan_data/raw/<YYYY-MM-DD>/air_india_raw_<YYYY-MM-DD>_batch_<windows>_<HHMM>IST.csv` |
| `MakeMyTrip Scraper` | MakeMyTrip (OTA) | **Missing** | N/A | *Script not present in repository (documented in `docs/OTA_INTEGRATION_PLAN.md`)* |
| `Goibibo Scraper` | Goibibo (OTA) | **Missing** | N/A | *Script not present in repository (documented in `docs/OTA_INTEGRATION_PLAN.md`)* |

---

## 2. Detailed Schema Analysis Per Scraper

### A. SpiceJet Scraper (`spicejet/spicejet_scraper.py`)
- **Status string values emitted**: `"ok"`, `"no_flights"`, `"parse_error"`
- **Python type of `total_fare`**: `float | None` (`float` for valid quotes e.g. `5800.0`, `None` for fallbacks; written as numeric string or `""` in CSV)
- **Python type of `fare_split_estimated`**: `bool` (`False` everywhere; written as `False` in CSV)
- **Casing of `fare_class`**: `"economy"` (lowercase) for valid quotes; `"unknown"` (lowercase) for fallback rows
- **Output naming pattern**: `udaan_data/raw/<YYYY-MM-DD>/spicejet_raw_<YYYY-MM-DD>_batch_<windows>_<HHMM>IST.csv`

### B. Akasa Air Scraper (`akasa/akasa_scraper.py`)
- **Status string values emitted**: `"ok"`, `"no_flights_or_timeout"`, `"error"`
- **Python type of `total_fare`**: `float | None` (`float` for calculated quotes e.g. `4500.0`, `None` for fallback/error rows; written as float string or `""` in CSV)
- **Python type of `fare_split_estimated`**: `bool` (`True` when calculated via mathematical fee estimation, `False` when missing/error; written as `True` / `False` in CSV)
- **Casing of `fare_class`**: `"economy"` (lowercase) always
- **Output naming pattern**: `udaan_data/raw/<YYYY-MM-DD>/akasa_raw_<YYYY-MM-DD>_batch_<windows>_<HHMM>IST.csv`

### C. IndiGo Scraper (`indigo/indigo_scraper_uc.py`)
- **Status string values emitted**: `"ok"`, `"sold_out"`, `"parse_error"`, `"scrape_error"`, `"error"`
- **Python type of `total_fare`**: `float | None` (`float` for valid quotes, `None` for sold-out/error rows; written as float string or `""` in CSV)
- **Python type of `fare_split_estimated`**: `bool` (`False` everywhere; written as `False` in CSV)
- **Casing of `fare_class`**: `"economy"`, `"business"` (lowercase) when quotes found; `""` (empty string) for `sold_out` and `parse_error`; `"unknown"` (lowercase) for `error` and `scrape_error`
- **Output naming pattern**: `udaan_data/raw/<YYYY-MM-DD>/indigo_raw_<YYYY-MM-DD>_batch_<windows>_<HHMM>IST.csv`

### D. Air India Scraper (`air_india/air_india_scraper.py`)
- **Status string values emitted**: `"ok"`, `"parse_error"`, `"error"`
- **Python type of `total_fare`**: `float | None` (`float` for parsed quotes, `None` for parse errors / error rows; written as float string or `""` in CSV)
- **Python type of `fare_split_estimated`**: `bool` (`False` everywhere; written as `False` in CSV)
- **Casing of `fare_class`**: `"economy"` (lowercase) always
- **Output naming pattern**: `udaan_data/raw/<YYYY-MM-DD>/air_india_raw_<YYYY-MM-DD>_batch_<windows>_<HHMM>IST.csv`

### E. MakeMyTrip & Goibibo Scrapers
- **Status**: **Missing from repository**. Per `docs/OTA_INTEGRATION_PLAN.md`, OTA scraper scripts have not been provided or located in this codebase.

---

## 3. Schema Drift & Discrepancies Summary

| Dimension | Drift / Discrepancy Observed | Impact / Note |
|---|---|---|
| **Status Enum Values** | Inconsistent status strings across scrapers:<br>- SpiceJet: `no_flights`, `parse_error`, `ok`<br>- Akasa: `no_flights_or_timeout`, `error`, `ok`<br>- IndiGo: `sold_out`, `parse_error`, `scrape_error`, `error`, `ok`<br>- Air India: `parse_error`, `error`, `ok` | Downstream parsers (`compute_daily_index.py`, `smart_orchestrator.py`) must account for multiple status strings (e.g. filtering out `'error'`, looking for `'ok'`). |
| **`fare_class` Empty / Fallback Values** | - IndiGo uses `""` for `sold_out`/`parse_error` and `"unknown"` for `error`/`scrape_error`.<br>- SpiceJet uses `"unknown"` for 0 usable quotes fallback.<br>- Akasa and Air India use `"economy"` even for fallback/error rows. | Case casing is consistently lowercase, but non-quote fallback values vary (`""` vs `"unknown"` vs `"economy"`). |
| **Fare Estimation (`fare_split_estimated`)** | Akasa Air sets `fare_split_estimated=True` (boolean) because base/tax split is mathematically estimated from total price. All other scrapers output `False`. | `compute_daily_index.py` handles boolean values properly when parsing CSV. |
| **Missing OTA Scraper Files** | MakeMyTrip and Goibibo scrapers referenced in prompt are absent from codebase. | Need to be added or provided when OTA integration phase starts. |

---

## 4. Project Constraint Guidelines

> **Constraint Acknowledgment:** The existing browser-automation logic (Selenium / `undetected-chromedriver` / `SeleniumBase` navigation, clicking, typing) in the existing scraper files is tested and working. Any future step in this project will only add new modules or append small hooks to these files — **never rewrite their existing scraping or navigation logic**.
