# Udaan Metrics Web Scraping Architecture & Extraction Rules

This document outlines the scraping architecture, engineering rules, and anti-bot mitigation patterns implemented across our production airline scrapers (exemplified by [`indigo_scraper_uc.py`](file:///Users/rishavroy/SIH/indigo/indigo_scraper_uc.py) and [`air_india_scraper.py`](file:///Users/rishavroy/SIH/air_india/air_india_scraper.py)).

---

## 1. Execution Order & Pipeline Resilience

- **Horizons Outer, Routes Inner**: Scrapers **must** iterate over Advance Purchase Horizons (`T+1, T+7, T+15, T+30, T+45`) in the outer loop, and route pairs in the inner loop:
  ```python
  for advance_days in ADVANCE_PURCHASE_WINDOWS:       # Outer: T+1, T+7, ...
      for origin, dest in ROUTES:                    # Inner: DEL->BOM, ...
          scrape_one_window(...)
  ```
- **Rationale**: If a scraper crashes halfway through a multi-hour collection run, the index is still guaranteed to have captured the entire route basket for critical near-term horizons (`T+1`, `T+7`) rather than capturing all horizons for only one route and missing the others.
- **Atomic Append per Route**: Quotes are written and flushed to CSV immediately after each route finishes, preventing data loss on process interruption.

---

## 2. Selenium Driver Lifecycle & Process Management Rules

- **Fresh Browser per Route (No Shared Long-Lived Sessions)**:
  - **Rule**: Never run an entire multi-hour scraping job inside a single continuous Selenium session. Instead, instantiate a **fresh, isolated driver instance per route query**:
    ```python
    for origin, dest in ROUTES:
        options = uc.ChromeOptions()
        driver = uc.Chrome(options=options, version_main=151)
        try:
            quotes = scrape_one_window(driver, origin, dest, advance_days)
            append_csv(quotes, csv_path)
        finally:
            driver.quit()  # CRITICAL: Guaranteed termination
    ```
- **Guaranteed Cleanup via `try ... finally`**:
  - Web scraping is inherently prone to network timeouts, dynamic DOM shifts, and transient element blocks.
  - **Rule**: `driver.quit()` **must unconditionally execute inside a `finally` block**. Never rely on Python garbage collection or script termination to kill the browser.
- **Orphan Process & Port Exhaustion Prevention**:
  - Undetected ChromeDriver spawns external Chrome binary subprocesses communicating over local TCP debug ports (e.g., ports 50000+).
  - Failing to explicitly quit causes orphaned zombie processes on macOS/Linux, leading to socket exhaustion (`ConnectionRefusedError: [Errno 61]`) and memory leaks.
- **Anti-Bot Footprint & Cookie Accumulation Reset**:
  - CDNs (Cloudflare, Akamai Bot Manager) monitor the lifetime and query volume of a single browser session. Long-lived sessions accumulating dozens of route queries trigger behavioural rate limits and CAPTCHA challenges.
  - Restarting the browser generates a pristine session context, fresh TLS session cache, and resets DOM memory and cookie states.
- **Headful Windowed Mode (No `--headless`)**:
  - Modern anti-bot services detect headless Chrome through WebGL canvas rendering, plugin arrays (`navigator.plugins`), and headless window metrics.
  - Run in standard windowed mode (`headless=False`) or with stealth wrappers.
- **Explicit Major Version Alignment (`version_main`)**:
  - Explicitly specify `version_main` in `uc.Chrome(version_main=151)` to match the installed Chrome browser version, preventing silent driver mismatch crashes.

---

## 3. DOM Interaction & Synthetic Event Dispatching

- **React & Angular Synthetic Event Bubbling**:
  - Modern Single Page Application (SPA) frameworks (like IndiGo's React calendar or Air India's Angular Material) use synthetic event systems where `element.click()` fails to bubble to document root listeners.
  - **Rule**: Dispatch full synthetic `MouseEvent` sequences with bubbling enabled:
    ```javascript
    ['mousedown', 'mouseup', 'click'].forEach(function(evtName) {
        el.dispatchEvent(new MouseEvent(evtName, {
            bubbles: true,
            cancelable: true,
            view: window
        }));
    });
    ```
- **Calendar Month Pagination Loop (T+30 / T+45 Horizons)**:
  - For long-horizon bookings (`T+30`, `T+45`), the target travel date is not initially visible on the active calendar page.
  - **Rule**: Implement a pagination loop (up to 6 months) that checks for the target date selector and clicks the next-month button (`button.rdrNextButton` or `button.ai-date-picker__arrow--right`) via JavaScript until the target date element is rendered in the DOM:
    ```python
    target_date_selector = f"div[data-date='{travel_date}']"
    for _ in range(6):
        elements = driver.find_elements(By.CSS_SELECTOR, target_date_selector)
        if elements:
            # Dispatch synthetic MouseEvent
            break
        next_btn = driver.find_element(By.CSS_SELECTOR, "button.rdrNextButton")
        driver.execute_script("arguments[0].click();", next_btn)
        time.sleep(0.5)
    ```

- **Two-Step Combobox Selection (Type + Explicit Dropdown Click)**:
  - Simply typing text into airport input fields does not trigger the internal state change in SPAs.
  - **Rule**: Click the input field, send keystrokes via `ActionChains` or `human_type`, pause `1.0s – 1.5s` for the autocomplete overlay to render, and explicitly click the matched option element (`//*[text()='{origin_code}']`) via JavaScript.

---

## 4. Defensive Extraction & Route Validation

- **Alternate / Satellite Airport Rejection**:
  - Airlines frequently return nearby secondary airports (e.g. Navi Mumbai `NMI` for `BOM`, or Hindon `HDO` for `DEL`).
  - **Rule**: Scrapers must extract the actual departure and arrival IATA codes from each individual flight card:
    ```python
    if act_origin != target_origin or act_dest != target_dest:
        with open("discarded_routes.log", "a") as lf:
            lf.write(f"Discarded {act_origin}->{act_dest} (Target: {target_origin}->{target_dest})\n")
        continue
    ```

- **Timeout & Empty SRP Fallback Logging**:
  - If the Search Results Page (SRP) times out or returns zero flight cards, never silently fail or crash the script.
  - **Rule**: Record an explicit fallback quote with `status="no_flights_or_timeout"` to guarantee complete visibility in the daily data audit.

- **CLI Horizon Flag Support (`--windows`)**:
  - Scrapers must support an optional `--windows` argument (e.g., `python3 scraper.py --windows 1,7`) to enable modular testing and targeted backfills without having to run all 5 horizons.
- **Flight Number & Carrier Parsing**:
  - Use regex matching (`\b6E\s*[-]?\s*\d{2,4}\b`, `\bAI\s*[-]?\s*\d{3,4}\b`) on card text.
  - Detect codeshares and operating carriers (e.g., "Operated by Air India Express") and assign carrier metadata accurately.

---

## 5. Multi-Class Hierarchy Traversal & Fare Isolation

- **Isolated Ancestor Crawling**:
  - Flight cards often display multiple fare categories (`Economy`, `Flexi Plus`, `Super 6E`, `Business`).
  - To prevent price-bleeding between chips, climb ancestor containers (up to 5 levels) to locate the exact DOM scope that contains exactly one isolated price element per chip:
    ```python
    for i in range(1, 6):
        parent = chip.find_element(By.XPATH, f"./ancestor::div[{i}]")
        prices = parent.find_elements(By.CSS_SELECTOR, SELECTORS["fare_card_price"])
        if len(prices) == 1:
            price_val = float(clean(prices[0].text))
            break
    ```
- **Sold Out / Unavailable Handling**:
  - Cards matching `.sold-out`, `.unavailable`, or containing textual "Sold Out" must be logged explicitly with `status="sold_out"` and `total_fare=None` rather than dropped silently.

---

## 6. Rate Limiting, Jitter & Timing Protocol

- **Multi-Tiered Delays**:
  1. **Micro-actions**: `0.5s – 1.5s` between UI clicks and input focus.
  2. **Page & SRP Render**: `15s` fixed wait or `WebDriverWait` for flight card presence.
  3. **Inter-Route Jitter**: `random.uniform(30.0, 45.0)` seconds between consecutive route queries.
- **Fixed Daily Snapshot Times**:
  - Live production runs must start at **07:00 IST** to publish by **10:00 IST**.
  - All timestamps must be timezone-aware (UTC+05:30) with standardized `capture_run` tags (e.g., `2026-09-01_0700IST`).

---

## 7. Canonical CSV Output Schema

All scrapers must write to `udaan_data/raw/<YYYY-MM-DD>/<carrier>_raw_<YYYY-MM-DD>_batch_<windows>_<HHMM>IST.csv` adhering to the exact 16-column specification:

| Column Name | Type | Description | Example |
| :--- | :--- | :--- | :--- |
| `origin` | String (3) | Target origin IATA code | `DEL` |
| `destination` | String (3) | Target destination IATA code | `BOM` |
| `carrier_code` | String (2) | 2-letter airline code | `6E`, `AI`, `QP`, `SG` |
| `carrier_name` | String | Official airline brand name | `IndiGo`, `Air India`, `Akasa Air`, `SpiceJet` |
| `flight_num` | String | Standard flight identifier | `6E 2034`, `AI 865` |
| `travel_date` | String (YYYY-MM-DD) | Flight departure date | `2026-09-02` |
| `advance_purchase_days` | Integer | Advance booking horizon | `1`, `7`, `15`, `30`, `45` |
| `fare_class` | String | Normalised fare category | `Economy`, `Business` |
| `base_fare` | Float / Null | Decomposed base tariff | `5800.0` or empty |
| `taxes_and_fees` | Float / Null | Decomposed taxes/fees | `933.0` or empty |
| `total_fare` | Float / Null | Gross payable airfare in INR | `6733.0` |
| `fare_split_estimated` | Boolean | True if base/tax was estimated | `False` |
| `departure_time` | String (HH:MM) | 24-hour departure time | `08:55` |
| `status` | String | Extraction status | `ok`, `sold_out`, `parse_error`, `error` |
| `scraped_at` | ISO-8601 String | UTC+5:30 collection timestamp | `2026-09-01T04:58:00+05:30` |
| `capture_run` | String | Fixed collection run batch ID | `2026-09-01_0458IST` |
