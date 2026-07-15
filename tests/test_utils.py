import tempfile
import unittest
from pathlib import Path

from utils import load_json, pop_one_based, save_json, truncate_text


class JsonHelpersTests(unittest.TestCase):
    def test_load_and_save_json(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            data = {"enabled": True, "targets": ["https://example.com"]}

            self.assertTrue(save_json(str(path), data, "save failed"))
            self.assertEqual(load_json(str(path), {}), data)

    def test_load_json_returns_fallback_for_invalid_json(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text("{invalid", encoding="utf-8")

            self.assertEqual(load_json(str(path), []), [])


class CollectionHelpersTests(unittest.TestCase):
    def test_pop_one_based_removes_selected_item(self):
        items = ["first", "second", "third"]

        removed, error = pop_one_based(items, "2")

        self.assertEqual(removed, "second")
        self.assertIsNone(error)
        self.assertEqual(items, ["first", "third"])

    def test_pop_one_based_reports_invalid_input(self):
        items = ["first"]

        removed, error = pop_one_based(items, "not-a-number")

        self.assertIsNone(removed)
        self.assertEqual(error, "❌ Please send a valid number!")
        self.assertEqual(items, ["first"])

    def test_pop_one_based_reports_out_of_range_input(self):
        removed, error = pop_one_based(["first"], "2")

        self.assertIsNone(removed)
        self.assertEqual(error, "❌ Invalid number! Choose 1-1")


class DisplayHelpersTests(unittest.TestCase):
    def test_truncate_text_preserves_maximum_length(self):
        self.assertEqual(truncate_text("abcdefghij", 8), "abcde...")
        self.assertEqual(truncate_text("short", 8), "short")


if __name__ == "__main__":
    unittest.main()
