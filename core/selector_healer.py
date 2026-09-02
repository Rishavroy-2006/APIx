import os
import re
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from bs4 import BeautifulSoup

from core.llm_client import LLMClient

logger = logging.getLogger(__name__)

IST = timezone(timedelta(hours=5, minutes=30))

# Absolute paths resolved relative to this file's parent directory (project root)
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SELECTORS_DIR = os.path.join(_PROJECT_ROOT, "selectors")
HEALING_LOG = os.path.join(SELECTORS_DIR, "healing_log.jsonl")

# Regex patterns used to validate that candidate elements look like the expected field.
# NOTE: total_fare/base_fare require a rupee symbol or INR prefix — bare digit strings
# (like flight numbers '6E 2034') must NOT trigger a false positive match.
_FIELD_PATTERNS = {
    "total_fare":      re.compile(r"\u20b9[\d,]+|INR\s*[\d,]+"),
    "base_fare":       re.compile(r"\u20b9[\d,]+|INR\s*[\d,]+"),
    "departure_time":  re.compile(r"\b\d{2}:\d{2}\b"),
    "arrival_time":    re.compile(r"\b\d{2}:\d{2}\b"),
    "flight_num":      re.compile(r"\b[A-Z0-9]{2}[\s-]?\d{2,4}\b"),
    "fare_class":      re.compile(r"economy|business|value|saver|flexi", re.IGNORECASE),
    "fare_card":       re.compile(r"."),          # any non-empty element
    "origin_code":     re.compile(r"\b[A-Z]{3}\b"),
    "destination_code":re.compile(r"\b[A-Z]{3}\b"),
    "fare_split_estimated": re.compile(r"true|false", re.IGNORECASE),
}

VALID_MATCH_MIN = 2
VALID_MATCH_MAX = 20


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _selector_file(site: str) -> str:
    return os.path.join(SELECTORS_DIR, f"{site}.json")


def _load_selector_registry(site: str) -> dict:
    path = _selector_file(site)
    if not os.path.exists(path):
        raise FileNotFoundError(f"Selector registry not found for site '{site}': {path}")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _save_selector_registry(site: str, data: dict) -> None:
    path = _selector_file(site)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _append_healing_log(entry: dict) -> None:
    os.makedirs(SELECTORS_DIR, exist_ok=True)
    with open(HEALING_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _now_iso() -> str:
    return datetime.now(IST).isoformat()


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def propose_selector_fix(
    html: str,
    site: str,
    target_field: str,
    known_good_examples: list[str],
    llm_client: Optional[LLMClient] = None,
) -> dict:
    """
    Ask the LLM to inspect the DOM HTML and propose a CSS selector (or XPath)
    that would directly select the element type containing `target_field` values.

    Returns:
        {"selector": str, "confidence": float 0-1, "reasoning": str}

    Raises:
        ValueError if LLM extraction fails or returns invalid structure.
    """
    client = llm_client or LLMClient()

    examples_str = ", ".join(f'"{e}"' for e in known_good_examples[:5])
    system_prompt = (
        f"You are a DOM expert helping maintain a flight price scraper. "
        f"You are given the HTML of a search results page from the website '{site}'. "
        f"We know that the following values of the field '{target_field}' appear somewhere in the DOM: {examples_str}.\n\n"
        f"Propose a single CSS selector that reliably selects ALL elements containing '{target_field}' values "
        f"across the page (e.g. all price cells, or all departure time cells). "
        f"The selector must:\n"
        f"1. Target 2–20 elements on a typical search result page (not 0, not hundreds).\n"
        f"2. Match elements whose text content contains the pattern for '{target_field}' "
        f"   (e.g. prices look like '₹5,432', times look like '08:55', flight numbers like '6E 2034').\n"
        f"3. Be a valid CSS selector (not XPath) usable with BeautifulSoup's select().\n\n"
        f"Return ONLY the JSON object with keys: selector, confidence (0.0-1.0), reasoning."
    )

    schema_hint = {
        "type": "object",
        "properties": {
            "selector":   {"type": "string"},
            "confidence": {"type": "number"},
            "reasoning":  {"type": "string"},
        },
        "required": ["selector", "confidence", "reasoning"],
    }

    result = client.extract_json(system_prompt, html[:12000], schema_hint)

    if not isinstance(result.get("selector"), str) or not result["selector"].strip():
        raise ValueError(f"LLM returned empty or missing selector: {result}")
    if not isinstance(result.get("confidence"), (int, float)):
        result["confidence"] = 0.5

    return {
        "selector":   result["selector"].strip(),
        "confidence": float(result["confidence"]),
        "reasoning":  str(result.get("reasoning", "")),
    }


def validate_selector(
    html: str,
    selector: str,
    target_field: str,
) -> tuple[bool, str, int]:
    """
    Execute `selector` against `html` using BeautifulSoup.
    Returns (is_valid: bool, reason: str, match_count: int).

    Validity criteria:
      - VALID_MATCH_MIN <= match_count <= VALID_MATCH_MAX
      - At least one match's text matches the expected regex pattern for `target_field`
    """
    try:
        soup = BeautifulSoup(html, "html.parser")
        matches = soup.select(selector)
    except Exception as e:
        return False, f"BeautifulSoup select() raised an error: {e}", 0

    count = len(matches)
    if count < VALID_MATCH_MIN:
        return False, f"Too few matches: {count} (need {VALID_MATCH_MIN}–{VALID_MATCH_MAX})", count
    if count > VALID_MATCH_MAX:
        return False, f"Too many matches: {count} (need {VALID_MATCH_MIN}–{VALID_MATCH_MAX})", count

    pattern = _FIELD_PATTERNS.get(target_field)
    if pattern:
        text_samples = [m.get_text(strip=True) for m in matches[:10]]
        matching_texts = [t for t in text_samples if pattern.search(t)]
        if not matching_texts:
            return (
                False,
                f"None of the {count} matched elements have text matching pattern for '{target_field}'. "
                f"Samples: {text_samples[:5]}",
                count,
            )

    return True, f"OK: {count} match(es), text pattern confirmed.", count


def attempt_selector_healing(
    html: str,
    site: str,
    target_field: str,
    known_good_examples: list[str],
    llm_client: Optional[LLMClient] = None,
) -> dict:
    """
    Coordinates full healing attempt:
      1. Propose selector via LLM.
      2. Validate against current DOM.
      3. Write to pending_review in selectors/<site>.json if valid.
      4. Log every attempt (success or fail) to selectors/healing_log.jsonl.

    Returns a summary dict with keys: success, site, target_field, selector,
    confidence, validation_reason, match_count, timestamp.
    """
    timestamp = _now_iso()
    summary = {
        "timestamp":         timestamp,
        "site":              site,
        "target_field":      target_field,
        "known_good_examples": known_good_examples,
        "success":           False,
        "selector":          None,
        "confidence":        None,
        "validation_reason": None,
        "match_count":       0,
        "error":             None,
    }

    # 1. Propose
    try:
        proposal = propose_selector_fix(html, site, target_field, known_good_examples, llm_client=llm_client)
        summary["selector"]   = proposal["selector"]
        summary["confidence"] = proposal["confidence"]
        summary["reasoning"]  = proposal.get("reasoning", "")
        logger.info(f"[Healer] {site}/{target_field}: LLM proposed selector '{proposal['selector']}' (confidence={proposal['confidence']:.2f})")
    except Exception as e:
        summary["error"] = f"Proposal failed: {e}"
        logger.error(f"[Healer] {site}/{target_field}: Proposal failed: {e}")
        _append_healing_log(summary)
        return summary

    # 2. Validate
    is_valid, reason, count = validate_selector(html, proposal["selector"], target_field)
    summary["validation_reason"] = reason
    summary["match_count"] = count

    if not is_valid:
        summary["error"] = f"Validation failed: {reason}"
        logger.warning(f"[Healer] {site}/{target_field}: Validation FAILED — {reason}")
        _append_healing_log(summary)
        return summary

    # 3. Write to pending_review (never overwrite live selector)
    try:
        registry = _load_selector_registry(site)
        registry.setdefault("pending_review", {})[target_field] = {
            "value":           proposal["selector"],
            "confidence":      proposal["confidence"],
            "reasoning":       proposal.get("reasoning", ""),
            "proposed_at":     timestamp,
            "match_count":     count,
            "verified_by":     "llm_healed",
            "validation_note": reason,
        }
        _save_selector_registry(site, registry)
        summary["success"] = True
        logger.info(f"[Healer] {site}/{target_field}: Selector written to pending_review. Run promote_pending_selector() to go live.")
    except Exception as e:
        summary["error"] = f"Registry write failed: {e}"
        logger.error(f"[Healer] {site}/{target_field}: Registry write failed: {e}")

    _append_healing_log(summary)
    return summary


def promote_pending_selector(site: str, target_field: str) -> bool:
    """
    Promotes a validated pending selector to live status in selectors/<site>.json.
    Sets verified_by='llm_healed' and last_verified_at to now.
    Returns True on success, False if no pending entry exists.
    """
    try:
        registry = _load_selector_registry(site)
        pending = registry.get("pending_review", {})

        if target_field not in pending:
            logger.warning(f"[Healer] No pending selector for {site}/{target_field}.")
            return False

        entry = pending.pop(target_field)
        registry.setdefault("selectors", {})[target_field] = {
            "value":            entry["value"],
            "last_verified_at": _now_iso(),
            "verified_by":      "llm_healed",
            "confidence":       entry.get("confidence"),
            "reasoning":        entry.get("reasoning", ""),
        }
        registry["pending_review"] = pending
        _save_selector_registry(site, registry)

        _append_healing_log({
            "timestamp":    _now_iso(),
            "event":        "promoted",
            "site":         site,
            "target_field": target_field,
            "selector":     entry["value"],
        })
        logger.info(f"[Healer] {site}/{target_field}: Promoted to live selector.")
        return True

    except Exception as e:
        logger.error(f"[Healer] promote_pending_selector failed for {site}/{target_field}: {e}")
        return False


def get_live_selector(site: str, target_field: str) -> Optional[str]:
    """Return the live selector value for a site/field, or None if not found."""
    try:
        registry = _load_selector_registry(site)
        entry = registry.get("selectors", {}).get(target_field)
        return entry["value"] if entry else None
    except Exception:
        return None
