import os
import re
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from bs4 import BeautifulSoup, Comment

from core.fare_schema import normalize_row, FareQuote
from core.llm_client import LLMClient

logger = logging.getLogger(__name__)

# Module-level call tracking per run
_CALL_COUNTER = 0
IST = timezone(timedelta(hours=5, minutes=30))


def get_call_counter() -> int:
    """Return current count of LLM fallback calls made in this process."""
    return _CALL_COUNTER


def reset_call_counter():
    """Reset the call counter (useful for test isolation)."""
    global _CALL_COUNTER
    _CALL_COUNTER = 0


def clean_and_trim_html(html_str: str, max_chars: int = 15000) -> str:
    """
    Strips script, style, svg, link, meta tags, and HTML comments.
    If cleaned HTML exceeds max_chars, extracts candidate elements containing
    both a time pattern (HH:MM) and a currency symbol (₹ or INR).
    """
    if not html_str:
        return ""

    soup = BeautifulSoup(html_str, "html.parser")

    # Remove non-content / heavy tags
    for tag in soup(["script", "style", "svg", "link", "meta", "noscript", "head", "header", "footer"]):
        tag.decompose()

    # Remove HTML comments
    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        comment.extract()

    cleaned_str = str(soup)

    if len(cleaned_str) <= max_chars:
        return cleaned_str

    # If exceeding max_chars, extract container nodes containing time pattern and currency
    time_re = re.compile(r"\b\d{2}:\d{2}\b")
    currency_re = re.compile(r"[₹]|INR", re.IGNORECASE)

    candidate_cards = []
    for el in soup.find_all(["div", "section", "article", "tr", "li"]):
        text = el.text
        if time_re.search(text) and currency_re.search(text):
            # Check length to ensure we get compact cards, not large parent wrappers
            if 50 <= len(text) <= 1500:
                candidate_cards.append(str(el))

    if candidate_cards:
        trimmed = "\n".join(candidate_cards)
        if len(trimmed) > max_chars:
            trimmed = trimmed[:max_chars]
        return trimmed

    # Fallback if specific cards could not be isolated
    return cleaned_str[:max_chars]


def save_raw_html_sample(
    trimmed_html: str, origin: str, destination: str, travel_date: str, source_scraper: str
) -> str:
    """
    Saves trimmed HTML sample to disk under apix_data/raw_html_samples/
    and returns relative path.
    """
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    samples_dir = os.path.join(base_dir, "apix_data", "raw_html_samples")
    os.makedirs(samples_dir, exist_ok=True)

    timestamp = datetime.now(IST).strftime("%Y%m%d_%H%M%S")
    filename = f"{source_scraper}_{origin}_{destination}_{travel_date}_{timestamp}.html"
    filepath = os.path.join(samples_dir, filename)

    try:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(trimmed_html)
        return os.path.relpath(filepath, start=base_dir)
    except Exception as e:
        logger.warning(f"Could not save HTML sample: {e}")
        return filepath


def _infer_carrier_info(source_scraper: str) -> tuple[str, str]:
    s = source_scraper.lower()
    if "indigo" in s or "6e" in s:
        return "6E", "IndiGo"
    elif "air_india" in s or "ai" in s:
        return "AI", "Air India"
    elif "spicejet" in s or "sg" in s:
        return "SG", "SpiceJet"
    elif "akasa" in s or "qp" in s:
        return "QP", "Akasa Air"
    elif "makemytrip" in s or "mmt" in s:
        return "MMT", "MakeMyTrip"
    elif "goibibo" in s:
        return "IB", "Goibibo"
    return "XX", source_scraper.title()


def llm_extract_flights(
    html_or_text: str,
    origin: str,
    destination: str,
    travel_date: str,
    advance_days: int,
    source_scraper: str,
    llm_client: Optional[LLMClient] = None,
) -> List[FareQuote]:
    """
    LLM-assisted fallback flight fare extraction.
    Cleans/trims input HTML, calls LLMClient for structured output,
    validates returned quotes against canonical schema, and tags provenance.
    Respects LLM_FALLBACK_MAX_CALLS_PER_RUN budget cap.
    """
    global _CALL_COUNTER

    # Enforce hard per-run budget cap
    max_calls_str = os.getenv("LLM_FALLBACK_MAX_CALLS_PER_RUN", "20")
    try:
        max_calls = int(max_calls_str)
    except ValueError:
        max_calls = 20

    if _CALL_COUNTER >= max_calls:
        logger.warning(
            f"[LLM Fallback] Per-run budget cap reached ({_CALL_COUNTER}/{max_calls} calls). Skipping LLM call."
        )
        return []

    # Clean HTML and save sample
    trimmed_html = clean_and_trim_html(html_or_text)
    sample_path = save_raw_html_sample(trimmed_html, origin, destination, travel_date, source_scraper)

    # Increment counter
    _CALL_COUNTER += 1

    # Prepare LLM client
    client = llm_client or LLMClient()

    system_prompt = (
        f"You are a strict data extraction assistant. Extract all flight fare quotes from the provided Indian "
        f"airline/OTA search results HTML for route {origin} to {destination} on travel date {travel_date}.\n"
        f"Return a JSON object with key 'quotes' containing an array of objects with fields:\n"
        f"  - flight_num (string, e.g. '6E 2034', 'AI 865', 'SG 101')\n"
        f"  - carrier_code (string, e.g. '6E', 'AI', 'SG', 'QP')\n"
        f"  - carrier_name (string, e.g. 'IndiGo', 'Air India', 'SpiceJet', 'Akasa Air')\n"
        f"  - departure_time (string HH:MM 24hr format, e.g. '08:55')\n"
        f"  - total_fare (number/float, all-in total price in INR)\n"
        f"  - fare_class (string, 'economy' or 'business')\n\n"
        f"STRICT RULES:\n"
        f"1. DO NOT invent or fabricate any flights not present in the HTML.\n"
        f"2. If no valid flight fares are found, return {{\"quotes\": []}}.\n"
        f"3. Only extract non-stop direct flights if possible."
    )

    schema_hint = {
        "type": "object",
        "properties": {
            "quotes": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "flight_num": {"type": "string"},
                        "carrier_code": {"type": "string"},
                        "carrier_name": {"type": "string"},
                        "departure_time": {"type": "string"},
                        "total_fare": {"type": "number"},
                        "fare_class": {"type": "string"},
                    },
                    "required": ["flight_num", "departure_time", "total_fare"],
                },
            }
        },
        "required": ["quotes"],
    }

    try:
        response_dict = client.extract_json(system_prompt, trimmed_html, schema_hint)
    except Exception as e:
        logger.error(f"[LLM Fallback] Extraction failed for {origin}->{destination}: {e}")
        return []

    raw_quotes = response_dict.get("quotes", [])
    if not isinstance(raw_quotes, list):
        logger.warning(f"[LLM Fallback] Expected list in 'quotes', got {type(raw_quotes).__name__}")
        return []

    now_ist = datetime.now(IST)
    now_iso = now_ist.isoformat()
    capture_run = now_ist.strftime("%Y-%m-%d_%H%MIST")
    default_code, default_name = _infer_carrier_info(source_scraper)

    validated_quotes: List[FareQuote] = []

    for item in raw_quotes:
        if not isinstance(item, dict):
            continue

        raw_item_dict = {
            "origin": origin,
            "destination": destination,
            "carrier_code": item.get("carrier_code") or default_code,
            "carrier_name": item.get("carrier_name") or default_name,
            "flight_num": item.get("flight_num") or "unknown",
            "travel_date": travel_date,
            "advance_purchase_days": advance_days,
            "fare_class": item.get("fare_class") or "economy",
            "base_fare": None,
            "taxes_and_fees": None,
            "total_fare": item.get("total_fare"),
            "fare_split_estimated": False,
            "departure_time": item.get("departure_time") or "unknown",
            "status": "ok",
            "scraped_at": now_iso,
            "capture_run": capture_run,
        }

        try:
            quote = normalize_row(raw_item_dict, source_scraper=source_scraper)
            # Tag extra provenance metadata
            quote.data_source_method = "llm_fallback"
            quote.raw_html_sample_path = sample_path
            validated_quotes.append(quote)
        except Exception as ve:
            logger.warning(f"[LLM Fallback] Dropping invalid LLM quote candidate: {ve} | Raw item: {item}")

    logger.info(
        f"[LLM Fallback] Successfully extracted {len(validated_quotes)} quote(s) for {origin}->{destination} on {travel_date}"
    )
    return validated_quotes
