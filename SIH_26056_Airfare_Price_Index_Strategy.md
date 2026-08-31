# Hackathon Strategy Report
### Real-time Airfare Price Index (APIx) for India — Smart Automation of CPI Data Collection

| | |
|---|---|
| **Problem Statement ID** | 26056 |
| **Organization** | MoSPI |
| **Department** | Data Informatics & Innovation Division (DIID) |
| **Category** | Software |
| **Theme** | Smart Automation |
| **Dataset** | [esankhyiki.mospi.gov.in](https://esankhyiki.mospi.gov.in) |

---

## 1. Problem Understanding

**In Simple Terms**
India's official inflation number (CPI) still measures airfares the old-fashioned way — manual checks at a limited set of ticket counters/travel agents. But over 90% of tickets are now bought online, and prices swing 200–400% in a single day depending on booking window, demand, festivals, and fuel costs. The official number no longer reflects what people actually pay. The task is to build a system that automatically scrapes real airline/OTA prices daily, cleans the data, and computes a live "Airfare Price Index" that MoSPI/RBI can plug into CPI calculations.

**Core Problem**
Stale, low-frequency, non-representative sampling of a highly volatile, digitally-transacted price category — resulting in an inaccurate inflation signal for a segment that RBI relies on for monetary policy decisions.

**Why It Matters**
- RBI's inflation-targeting framework depends on CPI accuracy; a mispriced sub-index distorts repo rate decisions.
- Air travel is a growing consumption category (post-COVID recovery, UDAN scheme, rising middle class) — its CPI weight will only increase.
- It is a template problem: solving this for airfares opens the door to similar automated price-index approaches for hotels, fuel, and other dynamically-priced goods — a broader "digital CPI" modernization opportunity.

---

## 2. Stakeholder Analysis

| Category | Details |
|---|---|
| **Primary Users** | MoSPI/NSO statisticians and analysts compiling CPI; RBI's monetary policy committee and research staff. |
| **Secondary Users** | Academic/economic researchers, aviation policymakers (Ministry of Civil Aviation, DGCA), journalists tracking travel inflation, airlines benchmarking competitors. |
| **Organizations Involved** | MoSPI (owner), DGCA (traffic data source), RBI (index consumer), airlines and OTAs (non-cooperating data sources), NIC/cloud providers for hosting. |
| **Who Benefits Most** | MoSPI (statutory mandate fulfilled) and RBI (better policy inputs) directly; every Indian consumer indirectly, through more accurate inflation-linked policy decisions (interest rates, wage indexation, subsidy calculations). |

---

## 3. Root Cause Analysis

**Why This Problem Exists**
- CPI methodology was designed for an era of physical retail outlets and ticket counters, not e-commerce-style dynamic pricing.
- Manual price collection is infrequent (monthly) and low-sample, incompatible with fares that change hourly.
- No institutional pipeline exists to ingest OTA/airline data at scale — this requires scraping infrastructure and data science capability that a statistics ministry doesn't traditionally build in-house.

**Current Alternatives & Why They Fall Short**

| Existing Solution | Limitation |
|---|---|
| Manual field data collection (current CPI method) | Sparse, delayed, low-frequency sampling. |
| DGCA monthly average domestic fare data | Aggregated, backward-looking, no route/lead-time granularity. |
| Private fare-tracking tools (Google Flights trends, ixigo insights, Skyscanner) | Consumer-facing, not statistically rigorous, proprietary, and not integrated into official CPI. |

None of these combine daily frequency, route-level granularity, advance-purchase segmentation, and a formal, auditable index methodology suitable for government statistics.

---

## 4. Constraints & Requirements

**Technical**
- JS-rendered SPA pages on airline/OTA sites require headless browser automation (Playwright/Selenium), not simple requests + BeautifulSoup.
- Anti-bot defenses: CAPTCHAs, IP blocking, rate limiting, session/cookie management, browser fingerprinting.
- Scheduling/orchestration needed at scale — routes × advance-purchase windows × sources creates combinatorial scraping volume.
- Data normalization across sites that present base fare, taxes, and convenience fees differently.

**Business, Legal & Ethical**
- Must respect robots.txt and Terms of Service; a government-adjacent project cannot ignore legal/ethical scraping norms.
- Rate-limiting required to avoid overloading source sites.
- Long-term sustainability may require APIs/data-sharing MoUs with airlines rather than pure scraping.

**Data**
- Missing values from sold-out flights and dynamically removed fares; outliers from glitch fares; de-duplication across sources quoting the same flight.
- A defined basket of city-pairs (DGCA traffic-weighted) and advance-purchase windows (T+1/7/15/30/45) is a sampling-design problem, not just engineering.
- Index construction requires a defensible statistical methodology (weights, aggregation formula) that will be scrutinized by evaluators.

**Time (10-Day Hackathon Feasibility)**
Full production-grade anti-bot scraping for 6 airlines and 5+ OTAs is unrealistic in 10 days. The MVP scopes down to 2–3 sources and ~8 routes with a few advance-purchase windows, while the architecture demonstrates a clear path to full scale.

---

## 5. Key Opportunities

| Area | Opportunity |
|---|---|
| **Innovation** | First-of-its-kind real-time, granular price index for a government statistical agency in India. |
| **Automation** | Fully scheduled scraping → cleaning → index computation → dashboard refresh pipeline, zero manual touch. |
| **AI/ML Usage** | ML-based anomaly/outlier detection; missing-fare imputation; lead-time elasticity/fare-prediction modeling; LLM-assisted scraping resilience against layout drift. |
| **Data-Driven Insights** | Sector-wise heatmaps, festival/demand-surge detection, fuel-price correlation analysis, elasticity curves by advance-purchase window. |
| **UX Improvements** | Clean analyst dashboard with drill-down (route → carrier → date), CSV/API export, natural-language query layer for trend exploration. |

---

## 6. Possible Solution Directions

### Approach A — Lean Scraper + Statistical Index Engine (Compliance-First Core Build)
- **Concept:** Focus entirely on doing the official ask well: robust scraper for a defined basket, clean pipeline, defensible index methodology, dashboard + API.
- **Core Features:** Scheduled Playwright scrapers for 2–3 airlines + 2–3 OTAs; PostgreSQL/TimescaleDB store; ETL cleaning (outlier removal, fare decomposition); index computation (Laspeyres-style with DGCA traffic weights); dashboard (trend, heatmap, elasticity curve); REST API for RBI/MoSPI.
- **Tech Stack:** Python (Playwright/Scrapy), Airflow/Cron, PostgreSQL/TimescaleDB, Pandas/NumPy, FastAPI, React + Recharts/Plotly, Docker.
- **Why It Can Win:** Directly and rigorously answers the problem statement's exact deliverables — methodological correctness and DGCA backtesting will be highly valued by MoSPI-affiliated judges.

### Approach B — AI-Resilient Scraping + Predictive Index (Tech-Heavy Differentiator)
- **Concept:** Same pipeline as Approach A, but scraping resilience is boosted using LLM-assisted selector generation (self-healing scrapers) and a predictive layer forecasting near-term index movement.
- **Core Features:** LLM-based DOM parsing fallback when CSS selectors break; ML-based anomaly detection; short-horizon fare/index forecasting (Prophet/LSTM); confidence-scored data quality flags.
- **Tech Stack:** Playwright + LangChain/LLM API for selector repair, scikit-learn/Prophet for forecasting, same storage/dashboard stack as Approach A.
- **Why It Can Win:** Demonstrates cutting-edge AI applied to a real infrastructure pain point (scraper fragility) — shows technical depth beyond a basic scraper.

### Approach C — Crowd-Augmented Hybrid Index (Data-Sustainability Differentiator)
- **Concept:** Since pure scraping is legally/technically fragile long-term, hybridize scraping with a lightweight opt-in crowdsourced fare-submission layer and future official API partnerships.
- **Core Features:** Everything in Approach A, plus a browser extension/PWA for opt-in fare capture, deduplication logic merging scraped and crowd data, trust-scoring per data source.
- **Tech Stack:** Same backend as Approach A + a Chrome extension (JS) or simple PWA, plus a contribution API.
- **Why It Can Win:** Addresses the single point of failure in pure scraping and shows systems-thinking about sustainability — answers the judge question, "what happens when an airline blocks your IP?"

> **Recommendation:** Build Approach A as the solid core (this is literally what is graded), layer in elements of Approach B (resilience/ML) as the demo differentiator, and mention Approach C as a future roadmap item.

---

## 7. MVP (10 Days, Team of 6)

**Scope**
3 airlines (IndiGo, Air India, SpiceJet — covering both LCC and full-service) + 2 OTAs (MakeMyTrip, EaseMyTrip), 8 representative city-pairs (DEL-BOM, DEL-BLR, BOM-BLR, DEL-CCU, BLR-HYD, MAA-DEL, DEL-PNQ, BOM-GOI), and 3 advance-purchase windows (T+1, T+7, T+30) — architecture built to extend to 5 windows and more sources.

**Core Functionality**
- Scheduled scraper (runs 2x/day) pulling fares across the route × window × source matrix.
- Cleaning pipeline: outlier removal (IQR + rule-based sold-out/error detection), fare decomposition (base/tax/fee where extractable), de-duplication across overlapping OTA-airline listings.
- Index engine: daily APIx per route plus an aggregate weighted national index using DGCA traffic-share weights (documented Laspeyres-style fixed-basket formula).
- Backtest module: compares computed index trend vs. publicly available DGCA monthly average fares, with correlation/error metrics.
- Dashboard: national index trend line, sector-wise heatmap, lead-time elasticity curve, carrier comparison, data-quality/coverage indicator.
- Public API (FastAPI): endpoints for daily index, per-route index, and raw fares (with auth key) for RBI/MoSPI consumption.

**Architecture Overview**
```
Playwright/Scrapy Scrapers
        │
        ▼
Raw Fare Staging (Kafka/Redis or DB staging)
        │
        ▼
Cleaning & Normalization Service (Python/Pandas)
        │
        ▼
PostgreSQL/TimescaleDB (fare + index tables)
        │
        ▼
Index Computation Job (scheduled)
        │
        ▼
FastAPI Backend  ──────►  React Dashboard (Recharts/D3)
        │
        └────────────►  Public REST API

Airflow/Cron orchestrates scraper, cleaning, and index jobs daily.
Logging/monitoring layer tracks scraper success rate and data completeness.
```

**Team Split (6 People)**
2 on scraping engine · 1 on cleaning/ETL + index math · 1 on backend/API · 1 on dashboard/frontend · 1 on backtesting, documentation & DevOps/deployment.

**Tools / Frameworks**
Python (Playwright, Pandas, NumPy, FastAPI), PostgreSQL/TimescaleDB, Airflow (or cron for MVP), React + Tailwind + Recharts/Plotly/D3, Docker Compose, GitHub Actions for CI/basic tests, Streamlit as a fast fallback dashboard if React time is tight.

---

## 8. Differentiation Strategy

| Factor | How It Stands Out |
|---|---|
| **Innovation** | Self-healing/LLM-assisted selectors tackle scraper fragility head-on — most teams' scrapers break on the first layout change. |
| **Impact** | Framed as a plug-in module for actual monetary policy input, not a toy dashboard; quantify how even 1–2% mismeasurement in a CPI sub-weight can shift RBI's real-rate calculus. |
| **Scalability** | Architecture trivially extends to more routes/carriers/windows and other dynamically-priced CPI categories (hotels, cabs) — pitch as a reusable "Dynamic Price Index Framework." |
| **Demo Potential** | Live scrape-to-dashboard run during the demo, plus a backtest overlay of the computed index vs. official DGCA numbers as visual proof of validity. |

---

## 9. Risks & Challenges

| Risk | Mitigation |
|---|---|
| IP bans / CAPTCHAs blocking scrapers mid-hackathon | Use rotating proxies sparingly, respect rate limits, cache aggressively, keep a pre-scraped dataset as demo fallback. |
| Legal/ToS concerns with scraping airline/OTA sites | Scrape only publicly visible fare-search pages, honor robots.txt, document ethical-scraping safeguards, position as a pilot needing eventual data-sharing MoUs. |
| Site layout changes breaking selectors | Build resilient/self-healing selector logic; add monitoring alerts for scraper failure rate. |
| Judges questioning index methodology rigor | Clearly document the formula (DGCA traffic-based route weights, fixed basket, aggregation method), cite index theory (Laspeyres/Fisher), present backtest correlation numbers. |
| Limited data volume in 10 days for meaningful backtest | Start scraping from day 1 and run continuously in the background while building other components; supplement with legally available historical/cached data. |
| Team overload trying to do too much at once | Strict MVP scoping (3 airlines, 2 OTAs, 8 routes) and clear parallel work-streams from day 1. |

---

## 10. Elevator Pitch (30 Seconds)

> "Right now, India's official inflation number treats airfares like it's still 2005 — a few manual price checks a month, even though fares swing 300% in a single day and 90% of tickets are bought online. We built **APIx** — a real-time Airfare Price Index that automatically scrapes IndiGo, Air India, SpiceJet, and top OTAs every day, cleans out the noise, and computes a statistically rigorous, DGCA-weighted price index across India's busiest routes — backtested against official government data. It's not just a dashboard; it's a plug-and-play data pipeline MoSPI and RBI can actually consume via API, with self-healing scrapers so it doesn't break the moment a website changes. This is inflation measurement, modernized."

---

*Prepared as a hackathon strategy brief for SIH Problem Statement 26056 — Development of a Real-time Airfare Price Index for India.*
