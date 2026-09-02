import logging
from typing import Optional, Any, Literal
from pydantic import BaseModel, Field, ConfigDict

logger = logging.getLogger(__name__)

CANONICAL_STATUSES = ("ok", "no_flights", "sold_out", "parse_error", "technical_error")

STATUS_MAP = {
    # ok
    "ok": "ok",
    "OK": "ok",
    
    # no_flights
    "no_flights": "no_flights",
    "NO_FLIGHTS": "no_flights",
    "no_flights_or_timeout": "no_flights",
    "NO_CARDS_FOUND": "no_flights",
    "no_cards_found": "no_flights",
    "none": "no_flights",
    
    # sold_out
    "sold_out": "sold_out",
    "SOLD_OUT": "sold_out",
    "unavailable": "sold_out",
    
    # parse_error
    "parse_error": "parse_error",
    "PARSE_ERROR": "parse_error",
    
    # technical_error
    "error": "technical_error",
    "ERROR": "technical_error",
    "scrape_error": "technical_error",
    "SCRAPE_ERROR": "technical_error",
    "BLOCKED": "technical_error",
    "blocked": "technical_error",
    "timeout": "technical_error",
}


class FareQuote(BaseModel):
    """Canonical 16-column Pydantic v2 FareQuote schema plus source provenance fields."""
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    origin: str
    destination: str
    carrier_code: str
    carrier_name: str
    flight_num: str
    travel_date: str
    advance_purchase_days: int
    fare_class: str
    base_fare: Optional[float] = None
    taxes_and_fees: Optional[float] = None
    total_fare: Optional[float] = None
    fare_split_estimated: bool
    departure_time: str
    status: Literal["ok", "no_flights", "sold_out", "parse_error", "technical_error"]
    scraped_at: str
    capture_run: str
    source_scraper: Optional[str] = None
    source_file: Optional[str] = None
    data_source_method: Optional[str] = "regex_parser"
    raw_html_sample_path: Optional[str] = None


def _parse_float(val: Any) -> Optional[float]:
    if val is None:
        return None
    if isinstance(val, (int, float)):
        import math
        if math.isnan(val):
            return None
        return float(val)
    s = str(val).strip()
    if not s or s.lower() in ("none", "null", "nan", "nat", ""):
        return None
    try:
        return float(s)
    except ValueError:
        raise ValueError(f"Could not convert '{val}' to float")


def _parse_bool(val: Any) -> bool:
    if isinstance(val, bool):
        return val
    if val is None:
        return False
    s = str(val).strip().lower()
    if s in ("true", "1", "t", "yes"):
        return True
    if s in ("false", "0", "f", "no", "", "none", "null", "nan"):
        return False
    raise ValueError(f"Could not convert '{val}' to bool")


def normalize_row(raw_dict: dict, source_scraper: str) -> FareQuote:
    """
    Normalizes a raw dictionary row into a validated FareQuote model.
    Coerces total_fare/base_fare/taxes_and_fees to float or None,
    coerces fare_split_estimated to bool, lowercases fare_class, and applies STATUS_MAP.
    Raises a clear ValueError logging the raw row if normalization/validation fails.
    """
    try:
        cleaned = dict(raw_dict)

        # 1. Coerce float fields
        for field in ("total_fare", "base_fare", "taxes_and_fees"):
            cleaned[field] = _parse_float(cleaned.get(field))

        # 2. Coerce fare_split_estimated to bool
        cleaned["fare_split_estimated"] = _parse_bool(cleaned.get("fare_split_estimated"))

        # 3. Lowercase fare_class
        raw_fc = cleaned.get("fare_class")
        cleaned["fare_class"] = str(raw_fc or "").strip().lower()

        # 4. Normalize advance_purchase_days
        raw_adv = cleaned.get("advance_purchase_days")
        if raw_adv is not None:
            cleaned["advance_purchase_days"] = int(float(str(raw_adv).strip()))

        # 5. Apply STATUS_MAP
        raw_status = str(cleaned.get("status") or "").strip()
        mapped_status = STATUS_MAP.get(raw_status) or STATUS_MAP.get(raw_status.lower()) or STATUS_MAP.get(raw_status.upper())
        if not mapped_status:
            raise ValueError(f"Unrecognized status '{raw_status}'. Must be mapped in STATUS_MAP.")
        cleaned["status"] = mapped_status

        # 6. Set source_scraper
        cleaned["source_scraper"] = source_scraper

        # 7. Instantiate Pydantic model
        return FareQuote(**cleaned)
    except Exception as e:
        logger.error(f"Failed to normalize row from scraper '{source_scraper}': {e} | Raw row: {raw_dict}")
        raise ValueError(f"Row normalization failed ({e}) for row: {raw_dict}") from e
