import unittest
import json
import os
import tempfile
import shutil
from unittest.mock import MagicMock, patch

from core.selector_healer import (
    propose_selector_fix,
    validate_selector,
    attempt_selector_healing,
    promote_pending_selector,
    get_live_selector,
    SELECTORS_DIR,
    HEALING_LOG,
)

# Minimal HTML fixture with 4 price elements for testing
_FIXTURE_HTML = """
<html><body>
  <div class="flight-card">
    <span class="price">₹5,432</span>
    <span class="time">08:55</span>
    <span class="flight">6E 2034</span>
  </div>
  <div class="flight-card">
    <span class="price">₹6,200</span>
    <span class="time">10:30</span>
    <span class="flight">6E 2076</span>
  </div>
  <div class="flight-card">
    <span class="price">₹7,800</span>
    <span class="time">14:15</span>
    <span class="flight">6E 2099</span>
  </div>
</body></html>
"""

_EMPTY_HTML = "<html><body><p>No flights found.</p></body></html>"

_KNOWN_GOOD_PRICES = ["₹5,432", "₹6,200", "₹7,800"]


class TestValidateSelector(unittest.TestCase):
    """Tests for validate_selector — the empirical gate — no LLM calls needed."""

    def test_valid_selector_price(self):
        valid, reason, count = validate_selector(_FIXTURE_HTML, "span.price", "total_fare")
        self.assertTrue(valid, f"Expected valid but got: {reason}")
        self.assertEqual(count, 3)

    def test_valid_selector_time(self):
        valid, reason, count = validate_selector(_FIXTURE_HTML, "span.time", "departure_time")
        self.assertTrue(valid, f"Expected valid but got: {reason}")
        self.assertEqual(count, 3)

    def test_too_few_matches(self):
        valid, reason, count = validate_selector(_FIXTURE_HTML, "div.nonexistent", "total_fare")
        self.assertFalse(valid)
        self.assertIn("Too few", reason)
        self.assertEqual(count, 0)

    def test_too_many_matches(self):
        # Build HTML with 25 matching spans
        html = "<html><body>" + "<span class='x'>foo</span>" * 25 + "</body></html>"
        valid, reason, count = validate_selector(html, "span.x", "total_fare")
        self.assertFalse(valid)
        self.assertIn("Too many", reason)
        self.assertEqual(count, 25)

    def test_wrong_text_pattern(self):
        # Selector returns elements but text doesn't match price pattern
        valid, reason, count = validate_selector(_FIXTURE_HTML, "span.flight", "total_fare")
        self.assertFalse(valid)
        self.assertIn("pattern", reason)

    def test_broken_selector_raises_gracefully(self):
        valid, reason, count = validate_selector(_FIXTURE_HTML, "[[[broken selector!!", "total_fare")
        self.assertFalse(valid)
        self.assertIn("error", reason.lower())


class TestProposeSelectorFix(unittest.TestCase):
    """Tests for propose_selector_fix with mocked LLMClient."""

    def test_valid_proposal_returned(self):
        mock_client = MagicMock()
        mock_client.extract_json.return_value = {
            "selector":   "span.price",
            "confidence": 0.9,
            "reasoning":  "Price spans are clearly labelled with class 'price'.",
        }
        result = propose_selector_fix(
            _FIXTURE_HTML, "spicejet", "total_fare", _KNOWN_GOOD_PRICES,
            llm_client=mock_client
        )
        self.assertEqual(result["selector"], "span.price")
        self.assertAlmostEqual(result["confidence"], 0.9)
        self.assertIn("reasoning", result)

    def test_empty_selector_raises(self):
        mock_client = MagicMock()
        mock_client.extract_json.return_value = {"selector": "", "confidence": 0.5, "reasoning": ""}
        with self.assertRaises(ValueError):
            propose_selector_fix(_FIXTURE_HTML, "spicejet", "total_fare", [], llm_client=mock_client)

    def test_missing_selector_key_raises(self):
        mock_client = MagicMock()
        mock_client.extract_json.return_value = {"confidence": 0.3, "reasoning": "oops"}
        with self.assertRaises(ValueError):
            propose_selector_fix(_FIXTURE_HTML, "spicejet", "total_fare", [], llm_client=mock_client)


class TestAttemptSelectorHealing(unittest.TestCase):
    """Integration tests for the full healing flow using a temporary directory."""

    def setUp(self):
        # Work in a temp dir so we don't pollute real selectors/
        self.tmp_dir = tempfile.mkdtemp()
        # Patch SELECTORS_DIR and HEALING_LOG inside the healer module
        self.patch_sdir = patch("core.selector_healer.SELECTORS_DIR", self.tmp_dir)
        self.patch_hlog = patch("core.selector_healer.HEALING_LOG",
                                os.path.join(self.tmp_dir, "healing_log.jsonl"))
        self.patch_sdir.start()
        self.patch_hlog.start()

        # Write a minimal registry for "test_site"
        registry = {
            "site": "test_site",
            "selectors": {
                "total_fare": {"value": "span.old-price", "last_verified_at": "2026-01-01T00:00:00+05:30", "verified_by": "manual"}
            },
            "pending_review": {}
        }
        with open(os.path.join(self.tmp_dir, "test_site.json"), "w") as f:
            json.dump(registry, f)

    def tearDown(self):
        self.patch_sdir.stop()
        self.patch_hlog.stop()
        shutil.rmtree(self.tmp_dir)

    def _mock_client(self, selector="span.price"):
        m = MagicMock()
        m.extract_json.return_value = {
            "selector": selector, "confidence": 0.88, "reasoning": "Matches price spans.",
        }
        return m

    def test_successful_healing_writes_to_pending(self):
        result = attempt_selector_healing(
            _FIXTURE_HTML, "test_site", "total_fare", _KNOWN_GOOD_PRICES,
            llm_client=self._mock_client("span.price")
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["selector"], "span.price")
        self.assertEqual(result["match_count"], 3)

        # Check pending_review was updated in file
        with open(os.path.join(self.tmp_dir, "test_site.json")) as f:
            updated = json.load(f)
        self.assertIn("total_fare", updated["pending_review"])
        self.assertEqual(updated["pending_review"]["total_fare"]["value"], "span.price")
        # Live selector must NOT have changed
        self.assertEqual(updated["selectors"]["total_fare"]["value"], "span.old-price")

    def test_failed_validation_does_not_update_pending(self):
        # LLM proposes selector that matches 0 elements
        result = attempt_selector_healing(
            _FIXTURE_HTML, "test_site", "total_fare", _KNOWN_GOOD_PRICES,
            llm_client=self._mock_client("div.nonexistent")
        )
        self.assertFalse(result["success"])
        with open(os.path.join(self.tmp_dir, "test_site.json")) as f:
            updated = json.load(f)
        self.assertEqual(updated["pending_review"], {})

    def test_healing_log_appended(self):
        attempt_selector_healing(
            _FIXTURE_HTML, "test_site", "total_fare", _KNOWN_GOOD_PRICES,
            llm_client=self._mock_client("span.price")
        )
        log_path = os.path.join(self.tmp_dir, "healing_log.jsonl")
        self.assertTrue(os.path.exists(log_path))
        with open(log_path) as f:
            lines = f.readlines()
        self.assertEqual(len(lines), 1)
        entry = json.loads(lines[0])
        self.assertEqual(entry["site"], "test_site")
        self.assertEqual(entry["target_field"], "total_fare")

    def test_promote_pending_selector(self):
        # First do a successful heal
        attempt_selector_healing(
            _FIXTURE_HTML, "test_site", "total_fare", _KNOWN_GOOD_PRICES,
            llm_client=self._mock_client("span.price")
        )
        # Now promote
        promoted = promote_pending_selector("test_site", "total_fare")
        self.assertTrue(promoted)

        with open(os.path.join(self.tmp_dir, "test_site.json")) as f:
            updated = json.load(f)

        # Live selector must now be the new one
        self.assertEqual(updated["selectors"]["total_fare"]["value"], "span.price")
        self.assertEqual(updated["selectors"]["total_fare"]["verified_by"], "llm_healed")
        # pending_review must be cleared
        self.assertEqual(updated["pending_review"], {})

    def test_promote_nonexistent_returns_false(self):
        result = promote_pending_selector("test_site", "nonexistent_field")
        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
