# APIx: Hackathon Pitch & PPT Talking Points

> **Purpose:** This document tracks the key strategic narratives, technical achievements, and "gotchas" to highlight in the final presentation to the judges.

---

## 1. The `robots.txt` Paradox (Legal & Ethical Reality)
* **The Problem:** The hackathon explicitly asks for an automated airfare scraper, but all airlines explicitly forbid scraping their booking engines in their `robots.txt` (e.g., `Disallow: /booking/*`).
* **Our MVP Solution:** To prove the mathematical and engineering viability of the CPI pipeline during this 10-day sprint, we *had* to bypass this using stealth browsers (`undetected-chromedriver`) and spoofed user agents. 
* **The Winning Pitch (Long-Term):** Pure scraping is a fragile cat-and-mouse game and unsuitable for Government of India infrastructure. We will pitch that the production version of APIx must migrate away from scraping and rely on **official MoUs and B2B API integrations** with airlines (similar to what MakeMyTrip has). This shows the judges we have deep systems-thinking and understand legal compliance.

## 2. Smart Automation & Rate Limiting (The Engineering Flex)
* **The Problem:** Traditional scrapers get immediately blocked by enterprise firewalls like Akamai and Cloudflare (which IndiGo uses).
* **Our Solution:** We didn't brute-force it with expensive proxy pools. Instead, we implemented **Intelligent Rate Limiting**. 
* **How it works:** We chunked the scraping schedule. We prioritize critical short-term data (T+1 and T+7) in the morning, and push longer-term data (T+15, T+30) to the evening. We added human-like 30-45 second delays between queries. We stayed under the 15-request WAF limit and scraped completely undetected.

## 3. The "Horizon-First" Architecture
* **The Problem:** If a scraper crashes midway through a run, you lose all the data, including the most time-sensitive prices.
* **Our Solution:** We designed a **"Horizon-First"** nested loop. Instead of checking all dates for one route, we check the most critical date (T+1) across *all* routes first, save it instantly (append mode), and then move to T+7. If the bot crashes at T+45, we still have the most important data secured.

## 4. The Unified Data Schema
* **The Problem:** IndiGo uses a complex React Single Page Application (SPA). SpiceJet uses a more standard DOM layout. Every airline is different.
* **Our Solution:** We built a standard `FareQuote` dataclass. Regardless of how messy the source HTML is, our scrapers normalize everything into a strict, unified CSV schema (`origin`, `destination`, `carrier_code`, `travel_date`, `advance_purchase_days`, `fare_class`, `total_fare`). This makes aggregating the final price index mathematically trivial.

## 5. Handling Reality: "No Flights Available"
* **The Highlight:** SpiceJet is currently shrinking its fleet and has dropped direct flights on several routes (like DEL -> BLR).
* **Our Solution:** Our scraper doesn't crash when flights are missing. It intelligently detects "No flights available" messages and logs empty data (`status=no_flights`). This proves our system captures *true market availability*, making the CPI index highly accurate and resilient to real-world business changes.
