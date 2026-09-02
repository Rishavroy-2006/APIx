# APIx v2 — MVP Hardening & Platform Vision

### From a CPI Scraper to an Event-Aware Fare Intelligence Platform

> **Scope of this document:** This is split into two parts. **Part A — This Week** is the actual build list for the current core index: outlier filtering, DGCA weighting, and the disclosure/methodology work that makes the number defensible. **Part B — Beyond the Hackathon** is the citizen/government dashboard platform vision, kept as a condensed pitch appendix, not a task list. Nothing in Part B gets built until Part A is done and showing on the live data tab.

---

## Where We Actually Are

The pipeline scrapes and deduplicates fares, but the two pieces that make this an *index* rather than a raw price feed — IQR outlier filtering and DGCA-weighted aggregation — are not built yet. That's the one thing standing between "provisional aggregate" and a defensible number, and it's the thing closest to the problem statement's Expected Solution. Everything below in Part A exists to close that gap; everything in Part B exists to show where it goes next.

---

# Part A — This Week (MVP Hardening)

## A.1 Outlier Filtering — Route-Scoped IQR

Run the IQR pass scoped to `route + horizon + day`, not as a single global filter — DEL–BOM and a thin regional route have different natural price variance, so one global IQR either lets regional glitch-fares through or wrongly flags normal trunk-route pricing.

**Caveat to design around, not discover later:** IQR needs enough samples per route to produce a meaningful quartile. With two carriers and a few days of live data, some route/horizon cells may only have a handful of points — too few to distinguish "outlier" from "the second data point you've ever seen." Fall back to a global IQR for any route/horizon cell below a minimum sample threshold, and promote it to route-scoped once enough history accumulates. Document the threshold in the methodology page (A.4).

## A.2 DGCA-Weighted Index Computation

Compute the sub-index per route first (with its own sample size / confidence), validate each independently, *then* roll up into the Laspeyres/DGCA-weighted national index — rather than one blended weighted average in a single pass. This makes it easy to catch a sparse or bad route before it silently drags the national number, and the per-route numbers double as the data-provenance panel content in A.4.

## A.3 Festival / Event Calendar Tagging

Tag every scraped fare row with `days_to_event`, computed from a static festival/holiday calendar (Durga Puja, Diwali, Eid, wedding season, summer holidays) — a lookup table, not scraping, so this is a few hours of work. A route can map to more than one event (CCU: Durga Puja, Kali Puja, Poila Boishakh); tag with the nearest upcoming major event for that route/region.

This directly strengthens the existing narrative — "why prices move," not just "that they moved" — and is genuinely novel next to the manual CPI process, which produces no such breakdown at all.

## A.4 Public Methodology & Data-Quality Page

Near-zero engineering cost, disproportionate trust payoff. Should state, in writing:

- **Index formula & weights** — Laspeyres/DGCA weighting, outlier-removal method (including the sample-size fallback from A.1).
- **Data provenance** — sample size per route per day and scrape success rate, pulled from the existing `scrape_run_log.csv` the workflow already produces. This is formalizing an artifact you already have, not building a new one.
- **Historical-data honesty:** scraping only ever gives you *today's* live snapshot of forward fares (T+1…T+45) — there's no way to retroactively scrape what a fare was a year ago. State plainly that the "typical year" baseline is built from official DGCA/AERA traffic data and MoSPI's own historical CPI airfare sub-index (both public, free, monthly), paired with the project's own granular series growing forward from launch. This is *more* credible to a government evaluator than an unexplained claim of deep historical granularity, which would just invite "how did you get that."
- **Scraping ToS disclosure** — airline sites' terms typically restrict automated access. State this constraint proactively, alongside an intent to pursue an official data-partnership path with DGCA/airlines as the project matures. Raising it yourself builds credibility; a judge finding it unaddressed does the opposite.

## A.5 Pipeline Decomposition (supports A.1–A.2, not new scope)

The existing orchestrator already scans for missing scrape windows; these are the same idea applied one level deeper, and they make A.1/A.2 more robust without adding new surface area:

- **Scraping** — decompose by `carrier × route × horizon` instead of by carrier alone, so a stealth-block or layout change on one cell fails only that cell, not the day's data for that carrier. A simple status table (`route`, `horizon`, `carrier`, `status`, `attempts`, `last_error`) in whatever store you're using is enough — no external queue needed at this scale.
- **Validation** — split into a per-row checkpoint (schema, plausible price bounds, non-null fields) right after parsing, and a per-batch checkpoint (the route-scoped IQR pass from A.1) after each chunk lands.
- **Historical backfill** — keep official aggregate history and live-scraped data as separately tagged sources (`source: official_aggregate` vs `source: live_scrape`), merged only at the presentation layer. This keeps the honesty commitment in A.4 architecturally enforced, not just documented.

---

# Part B — Beyond the Hackathon (vision, not this week's task list)

This section exists as pitch material — "here's where this goes next" — and costs zero engineering hours as written. Nothing here starts until Part A is live.

## B.1 Two Dashboards, Two Jobs

The long-term shape is one data spine feeding two presentation layers, not two pipelines:

| | **User Dashboard** | **Government Dashboard** |
|---|---|---|
| Core question | "Should I book now?" | "What is airfare inflation doing, and why?" |
| Granularity | Single route, single user's dates | All routes, DGCA-weighted aggregate |
| Key visual | Personal fare trajectory + book-now/wait indicator | National index trend, route heatmap, event-contribution breakdown |
| Access | Public / lightweight signup | Authenticated, audit-logged |

**Citizen side:** personalized fare trajectory (T+1→T+45/90) plotted against a historical seasonal baseline, a simple traffic-light "book now or wait" signal, and price alerts via Telegram/email once a threshold or predicted local minimum is hit.

**Government side, additions on top of the core index:** a route heatmap of India (MoM/YoY change), a volatility-per-route signal (flags monopoly/near-monopoly routes — a competition-policy angle, not just a stats one), and an inflation-contribution breakdown showing which festivals/routes are driving the month's number — the seasonal tagging from A.3 makes this possible with no new data collection.

## B.2 Price Prediction Model

Gradient boosting (scikit-learn/LightGBM, weekly retrain via GitHub Actions, no GPU) on days-to-departure, day-of-week, event-proximity, and seasonality — clustered by route behavior (trunk routes vs. festival-driven regional routes) rather than one global model, since a Durga Puja route's booking signal shouldn't be smoothed out by averaging in routes that don't spike the same way. Realistic on free-tier compute, but needs real historical depth this project doesn't have yet — undemonstrable, or worse, visibly wrong if judged live, until the backfill strategy in A.4 has had time to accumulate.

## B.3 Other Roadmap Items

- **OTA integration** (MakeMyTrip, EaseMyTrip) for full-service-carrier coverage (Air India, Vistara) — currently IndiGo/SpiceJet-only skews the index toward LCC pricing.
- **WhatsApp/Telegram price alerts** — high reach for this user base, low-cost bot APIs on both platforms.
- **Multi-modal comparison** (rail alternative pricing) for a fuller cost-of-travel picture; IRCTC data is more structured than most people assume.
- **Rate-limited public API tier** for researchers/journalists.
- **Formal data-sharing conversation with DGCA/airlines**, to reduce long-term reliance on scraping.

## B.4 Low-Budget Architecture (for when B.1–B.3 get built)

Same principle throughout: free/near-free tiers, no infra you don't need yet.

| Layer | Choice | Why |
|---|---|---|
| Storage | Postgres + TimescaleDB (Supabase free tier) | Time-series-native, covers early-stage volume free |
| API | Lightweight FastAPI on Render/Railway | Serves both dashboards from one endpoint set |
| Dashboards | Static React/Next.js (Vercel free tier) | Periodic API polling is enough — no websockets needed |
| Alerts | Telegram Bot API + free-tier transactional email | Zero/near-zero cost at pilot scale |

"Real-time" here means the dashboard reflects today's scrape within the hour — the daily-cron-plus-hourly-cache pattern already covers that honestly; streaming infra would add cost without adding value at this stage.

---

## Risks & Honest Caveats (state up front, don't gloss over)

- **ToS/legal exposure of scraping** — see A.4. Worth exploring a parallel data-partnership path as the project matures rather than relying on scraping indefinitely.
- **Historical data honesty** — see A.4. Don't overclaim granularity that isn't actually there.
- **Index credibility** — a government-facing number needs a transparent, reproducible methodology (A.4) or it won't be adopted regardless of technical quality.
- **Sample bias** — IndiGo/SpiceJet-only skews toward LCC pricing; OTA/full-service-carrier expansion (B.3) matters more than a "Next" nice-to-have if the index is meant to represent the whole market.

---

## Updated Roadmap

**Now** — Part A in full: route-scoped IQR with sample-size fallback, DGCA-weighted index, festival/event tagging, public methodology page (incl. ToS disclosure), pipeline decomposition.

**Next** — Government dashboard extras (heatmap, provenance panel, event-contribution breakdown), basic citizen dashboard (trajectory + book-now/wait), OTA integration, price alerts.

**Future** — Price prediction model, multi-modal (rail) comparison, public researcher API tier, formal data-sharing conversation with DGCA/airlines.

---

## One-Line Positioning (for pitch decks)

*"APIx turns India's monthly, manually-collected airfare inflation number into a real-time, event-aware index — and gives citizens the same data back as a simple 'book now or wait' answer for the routes and festivals they actually care about."*
