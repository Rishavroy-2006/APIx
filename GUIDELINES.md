# APIx — Data Pipeline Guidelines
### SIH 26056 · Real-time Airfare Price Index
**Status: Binding for all scraper, cleaning, and index code — human or AI-agent authored.**

This document is the single source of truth for how APIx collects, cleans, and
indexes fare data. If any code (yours, a teammate's, or an AI coding agent's)
disagrees with this file, **this file wins** — open an issue/PR to change the
guideline first, then change the code. This prevents the schema/logic drift we
already hit once between the original scraper and the rewritten one.

---

## 1. Ethical Scraping — Non-Negotiable

These rules apply to every scraper in this repo, regardless of who writes it or
how many times it gets rewritten:

- **Always check `robots.txt` before scraping a new domain**, and respect it.
  If a rewrite drops this check, that is a regression, not a simplification.
- **Identify with a descriptive User-Agent** stating purpose and contact info.
  Never spoof a real browser UA to evade detection.
- **Rate-limit every scraper**: minimum 4–8s randomized delay between requests
  to the same domain. No exceptions for "the demo needs to run faster."
- **Never scrape behind a login wall or fetch personal/account data.** Public
  fare-search results only.
- **No IP rotation / proxy pools for the hackathon build.** If a source blocks
  you, that's signal to slow down or cache more aggressively — not to route
  around the block. (Post-hackathon, this becomes a documented ToS discussion,
  not a default engineering answer.)

Any scraper rewrite must carry these forward explicitly. Confirm this in code
review before merging — don't assume a rewrite kept them.

---

## 2. Canonical Data Schema

**One schema. All scrapers output this. No source-specific variants.**

| Column | Type | Notes |
|---|---|---|
| `origin` | string (IATA) | 3-letter code, validated against the fixed route basket |
| `destination` | string (IATA) | 3-letter code, validated against the fixed route basket |
| `carrier_code` | string | 2-letter IATA carrier code, derived from `flight_num` prefix (e.g. `6E`, `SG`) — the stable join key against DGCA traffic-weight data |
| `carrier_name` | string | human-readable name, derived from `carrier_code` via the fixed lookup table below — never scraped as free text |
| `flight_num` | string | full flight number, e.g. `6E 5314` |
| `travel_date` | date (YYYY-MM-DD) | departure date being priced |
| `advance_purchase_days` | int | one of {1, 7, 15, 30, 45} — no other values |
| `fare_class` | string | `economy` \| `business` — required, not inferred |
| `base_fare` | float \| null | pre-tax component |
| `taxes_and_fees` | float \| null | UDF + convenience fee + statutory taxes |
| `total_fare` | float \| null | `base_fare + taxes_and_fees` — must reconcile |
| `departure_time` | string (HH:MM) | local time, 24hr |
| `status` | enum | `ok` \| `sold_out` \| `parse_error` \| `no_flights` |
| `scraped_at` | ISO 8601 UTC timestamp | when this record was captured |
| `capture_run` | string | e.g. `2026-08-30_1000IST` — see Section 3 |

**Do not replace `total_fare`/`base_fare`/`taxes_and_fees` with fare-class-specific
columns like `business_fare`/`economy_fare`.** Fare class is a *row-level
attribute* (`fare_class` column), not separate columns. One row = one specific
fare quote for one fare class. This keeps the schema stable no matter how many
fare classes a source exposes, and keeps `fare_class` filterable in one place
(see Section 5 on which fare class feeds the index).

Likewise, don't collapse `carrier_code`/`carrier_name` into a single free-text
`carrier` column — keep them separate for the reasons above.

If a scraper cannot determine `base_fare`/`taxes_and_fees` split from the
source page, it may write `total_fare` only with the other two as `null` —
but it must never guess a split without labeling it as an estimate (see
Section 4).

**Carrier code → name lookup (fixed table, do not scrape this as free text):**

| `carrier_code` | `carrier_name` |
|---|---|
| `6E` | IndiGo |
| `AI` | Air India |
| `IX` | Air India Express |
| `SG` | SpiceJet |
| `QP` | Akasa Air |

Note: Vistara (`UK`) and AirAsia India (`I5`) have both merged into Air India /
Air India Express respectively — do not add them as separate active carriers
in new data. If a scraper ever encounters a code not in this table, it should
flag the row (`carrier_name = null`, log a warning) rather than guess.

---

## 3. Sampling Protocol — Fixed-Time Snapshots

Airfares change intraday, sometimes hourly. The index does not need to catch
every fluctuation — it needs a **consistent, repeatable snapshot**, the same
way physical CPI collectors visit the same shop at the same time each cycle.

- **Scrape at fixed times only**: minimum once daily at **10:00 IST**.
  Optionally add a second fixed run at **18:00 IST** if time allows, tracked as
  a separate `capture_run` value (e.g. `_AM` / `_PM`) — never blended silently
  into one number.
- **Never scrape "whenever convenient" and treat the result as comparable
  across days.** A 9 AM scrape one day and a 4 PM scrape the next is not two
  points on the same trend line — it's noise from an inconsistent protocol.
- **Document the exact capture rule in the README**: e.g. *"Lowest available
  economy fare across all flights for that route/date, sampled at 10:00 IST."*
  This one sentence is what makes the index defensible to a judge.
- Optional bonus metric (not part of the core index): if multiple intraday
  checks are done, report the day's fare **range** (min–max) as a separate
  volatility panel. Keep this cosmetic/secondary — the core index must stay
  built from the single fixed-time snapshot.

---

## 4. Fare Decomposition (Base Fare vs. Taxes)

- If the source page shows the base/tax split directly, extract it directly.
- If it does not (most search-results pages only show total), an estimated
  split may be applied **only if explicitly flagged** — add a boolean column
  `fare_split_estimated` (true/false) so downstream consumers know which rows
  are measured vs. modeled.
- Never silently assume a fixed percentage split without this flag. This is
  the same principle as never auto-labeling an unknown fare class as
  "Economy" — no unlabeled assumptions enter the dataset.

---

## 5. Which Fare Feeds the Index

- **The core APIx uses `economy_fare` rows only** (`fare_class == 'economy'`).
  CPI reflects what typical consumers actually pay — overwhelmingly economy
  class. Business fares are a different consumption basket entirely.
- **Business-class fares are tracked and reported separately** (e.g. a
  "Business Fare Trend" side panel) — they must never be blended into the
  same weighted average as economy fares. Mixing fare classes into one number
  makes the index meaningless for its stated purpose.
- If a route/carrier only sells one cabin class, that's fine — just don't
  backfill a missing class with the other class's price.

---

## 6. Cleaning & Outlier Policy

**Flag, don't silently delete — unless a quote is physically implausible.**

- Compute IQR bounds per `(route, advance_purchase_days, fare_class)` group.
- A fare outside 1.5×IQR gets `flag = 'outlier_candidate'`, not automatic
  removal. A genuine demand surge (festival, strike, capacity cut) is real
  inflation signal — deleting it defeats the purpose of the index.
- **Hard-exclude only physically implausible values**: fare ≤ 0, fare below a
  documented minimum sane threshold (e.g. <₹500 one-way domestic), or fare
  above 10× the highest fare ever observed for that exact route with no
  corroborating news event (festival calendar, strike, capacity cut logged
  separately).
- `sold_out` and `parse_error` rows are excluded from index computation but
  **retained in the raw dataset** — sold-out frequency is itself a useful
  supply-constraint signal, don't throw it away.
- Aggregate same-day, same-route, same-window quotes (across multiple flights)
  using **median, not mean** — fare distributions are right-skewed, and a
  couple of last-seat premium fares shouldn't drag the "representative" price
  up the way they would with a mean.

---

## 7. Route Basket & Filtering

- The route basket is fixed for the hackathon build (see MVP scope in the
  strategy doc) — do not silently expand or shrink it in code.
- If a scraped result resolves to an airport code outside the intended
  origin/destination pair (e.g. a secondary/alternate airport), **discard the
  row from the dataset but log it** to a `discarded_routes.log` with a count —
  don't just drop it silently. A growing share of traffic moving to an
  alternate airport (e.g. a new airport opening) is exactly the kind of thing
  that should trigger a basket-definition review later, not disappear
  invisibly.

---

## 8. Index Construction

- **Weighting**: Laspeyres-style fixed-basket weighted average across the
  route basket, weights sourced from real DGCA city-pair passenger-traffic
  data (see `DGCA_ROUTE_WEIGHTS` config) — never equal-weighted by default
  once real weights are available. Equal-weighting is only a placeholder
  before real DGCA weights are wired in, and must be labeled as such in
  comments/UI if still in use.
- **Base period**: fixed reference average, documented explicitly in code
  (constant, not a magic number) — index = 100 at base period.
- **Aggregation across advance-purchase windows**: document whether windows
  are equal-weighted or traffic-weighted, and state the choice explicitly —
  don't leave it implicit.

---

## 9. Backtest & Disclosure Rules — No Silent Simulation

This is the most important rule in this document, and the one most likely to
get violated by well-intentioned "make the demo look complete" edits.

- **Any chart, number, or line that is simulated, modeled, or placeholder
  data must be visibly labeled as such in the UI** — not just in a code
  comment. A dashed "DGCA baseline" line that looks like real government data
  but isn't is a misrepresentation risk the moment a judge asks where it came
  from.
- **Real vs. synthetic data must never be silently blended in the same
  series.** If 8 days of the 30-day trend are real scraped data and the rest
  is reconstructed, the chart/README must say so explicitly: *"Live daily
  collection began [date]; N days shown are real captures. Remaining days
  are a calibrated placeholder pending continued collection."*
- Once real DGCA/MoSPI CPI Transport-group data is available (see Section 10),
  the backtest chart must be wired to that real series — the simulated
  baseline is a placeholder, not a final feature.

---

## 10. External Data Sources — Confirmed as of This Project

- **DGCA route/passenger-traffic data** (for basket selection + weighting):
  DGCA's own site publishes it as scattered monthly PDF/Excel reports under
  Data & Reports → Aviation Statistics → Air Transport → Domestic Air
  Transport. For speed, use the pre-cleaned mirror at
  `github.com/Vonter/india-aviation-traffic` (ODbL-licensed CSVs).
- **CPI backtest ground truth**: `esankhyiki.mospi.gov.in` → Data Catalogue →
  Product = CPI → the **group-wise** file (Table No. pattern
  `CPIMCY<YY><NNN><MONTH>`), NOT the division-wise or combined-level files.
  As of the 2024 base-year revision, the old "Transport and Communication"
  division was **split into two separate divisions**: `07 Transport` and
  `08 Information and communication`. The division-level "Transport" index
  bundles fuel, vehicle purchase, and fares across all modes — it is **not**
  air-fare-specific. The actual comparable line sits one level deeper, inside
  the group-wise breakdown of Division 07. Confirm the exact sub-group label
  when the group-wise file is opened — do not assume the old combined name
  still applies anywhere in the new base-year structure.

---

## 11. Change Control

- Any schema change must update this file in the same PR/commit.
- Any change to cleaning/outlier/index logic must update Sections 6–8 in the
  same PR/commit.
- If an AI coding agent (Antigravity, Claude Code, etc.) is asked to modify
  the pipeline, paste this file into its context first and instruct it to
  flag — not silently resolve — any conflict between a requested change and
  a rule here.
