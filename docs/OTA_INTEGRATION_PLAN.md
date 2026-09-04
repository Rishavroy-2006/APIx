# OTA Integration Plan
**Udaan Metrics — SIH 26056**  
**Status: PLAN ONLY — no integration code written. Awaiting approval.**

> **Pre-condition (Item E.1):** The OTA scraper scripts (MakeMyTrip / EaseMyTrip) have not been provided or located in this repository. This plan is written speculatively based on the canonical schema and their public search-page behavior. Before writing any integration code, the actual script files must be shared so their current output columns and types can be confirmed against Section A below.

---

## A. Schema Reconciliation

OTA scrapers must output the full canonical `FareQuote` schema (GUIDELINES.md §2) **plus two new required fields**:

| New Field | Type | Values | Purpose |
|---|---|---|---|
| `source` | enum string | `"airline_direct"` \| `"ota"` | Distinguishes origin of quote — never inferred, always set explicitly by the scraper |
| `source_name` | string | e.g. `"MakeMyTrip"`, `"EaseMyTrip"` | Human-readable source identifier for display and filtering |

All existing airline-direct scrapers must also be updated to write `source="airline_direct"` and `source_name=<carrier_name>` to their output CSVs once OTA integration begins — this is a **schema bump** and requires a coordinated update.

### Existing field behavior for OTA sources:
- `carrier_code` / `carrier_name`: Must still come from the fixed GUIDELINES.md lookup table, derived from the flight number prefix shown on the OTA results page — **never scraped as free text from the OTA's own carrier label**, which may differ (e.g. "Air India" vs "Ai" vs "AI").
- `flight_num`: The actual flight number (e.g. `AI 101`) shown on the OTA page — OTAs typically display this. If absent, log `flight_num = "unknown"` and `status = "parse_error"`.
- `base_fare` / `taxes_and_fees`: OTAs often show a fare breakdown. Extract if available; set `fare_split_estimated = False` if directly shown, `True` if inferred from total.
- `total_fare`: The all-in price shown to the consumer on the OTA's search results page.

### Key invariant:
> An OTA quote and an airline-direct quote for the **same flight number, same travel date, same advance window** are **two distinct rows** in the dataset — a direct comparison point, not a duplicate. The dedup key (Section C) must enforce this.

---

## B. Functional Role

OTA data has **three distinct roles**, each with different implications. These must never be conflated:

### Role 1: Cross-validation
For any flight where both an airline-direct quote and an OTA quote exist for the same `(flight_num, travel_date, advance_purchase_days)`, compute and flag the delta:
```
ota_premium_pct = (ota_total_fare - direct_total_fare) / direct_total_fare * 100
```
A delta > 5% is a citable data point for the methodology section — OTA convenience fees and dynamic markup are real consumer cost signals. A delta ≤ 1% validates that both scrapers are capturing the same published fare.

### Role 2: Coverage extension (interim only)
For routes or carriers without a dedicated direct scraper (e.g. Air India Express before a dedicated scraper is built), OTA data may serve as a **clearly labeled interim stand-in**. Rules:
- Must carry `source="ota"` in every row
- Dashboard badges must say **"OTA (MakeMyTrip)"** or similar — never presented as equivalent to a direct scraper
- Must be excluded from the composite index by default (see Role 3)

### Role 3: Core index
The **composite Udaan Metrics index remains airline-direct-only** unless a separate, explicitly documented decision is made to blend OTA data. Rationale: OTA fares include a platform margin that airline-direct fares don't, making them a different consumption series. Blending them silently would make the index indefensible to MoSPI or judges.

---

## C. Deduplication Update

The current dedup key in `compute_daily_index.py` is:
```python
dedup_keys = ["origin", "destination", "carrier_code", "flight_num",
              "travel_date", "advance_purchase_days", "fare_class"]
```

Once OTA data is added, this key must be updated to:
```python
dedup_keys = ["origin", "destination", "carrier_code", "flight_num",
              "travel_date", "advance_purchase_days", "fare_class", "source"]
```
This ensures an OTA row and an airline-direct row for the same flight are **preserved as two distinct comparable points**, not collapsed into one.

The index math filter must also explicitly exclude OTA rows:
```python
math_df = daily_df[
    (daily_df['status'] == 'ok') &
    (daily_df['outlier_flag'] == False) &
    (daily_df['carrier_name'] != 'Air India Express') &
    (daily_df['source'] == 'airline_direct')   # NEW: exclude all OTA rows from index math
]
```

---

## D. Dashboard Surface (Proposed — Do Not Build Yet)

Add a new **"Airline Direct vs OTA Price Comparison"** panel to the Live Data tab, positioned below the existing core index panels and above the "Business vs Economy Fare Gap" card. Treatment mirrors the Business/Economy card: secondary metric, clearly labeled as not part of the index.

### Panel design:
- **Route-filtered**: same route selector as the rest of the tab
- **Table layout**: one row per `(flight_num, advance_purchase_days)` pair where both a direct and OTA quote exist on the same day
  - Columns: Flight, Window, Direct Fare, OTA Fare, Delta (₹), Delta (%)
- **Highlight**: rows where |delta| > 5% get a colored flag (orange = OTA more expensive, green = OTA cheaper)
- **Caption**: *"Airline-direct vs OTA fare comparison for the same published flight. OTA quotes are excluded from the Udaan Metrics composite index."*
- **Empty state**: *"No matching airline-direct + OTA pairs for this route today."*

### Badge for OTA rows in fare table:
OTA rows in the existing "Representative Fare Sample" table should carry a `source_name` badge styled like the existing "Unvalidated" badge (orange), labeled `"MakeMyTrip"` or `"EaseMyTrip"` — not "OTA" generically.

---

## Next Steps (Blocked Until Approved)

1. **Share OTA script files** → confirm schema, status enum values, and whether `source` field already exists
2. **Approve this plan** → proceed with schema bump to all 4 direct scrapers + `compute_daily_index.py`
3. **Build cross-validation logic** → add `ota_premium_pct` column to master index
4. **Build dashboard panel** → only after data is confirmed flowing correctly
