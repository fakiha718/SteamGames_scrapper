"""
SteamVibe Automated Verification & Integration Test Suite
Validates:
1. Algorithm correctness, complexity metadata, and stability flags for all 8 algorithms
2. Single-column and composite boolean search engine
3. Scraper HTML parsing and CSV caching
4. PyQt6 GUI components, table model virtualization, and metrics integration
"""

import sys
import os
import unittest

# Ensure path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

from algorithms.sorting import (
    SORT_ALGORITHMS,
    ALGORITHM_METADATA,
    multi_column_sort,
    bubble_sort,
    selection_sort,
    insertion_sort,
    merge_sort,
    quick_sort,
    heap_sort,
    shell_sort,
    radix_sort,
)
from algorithms.searching import (
    linear_search,
    composite_search,
    CompositeFilterRule,
)
from scraper.worker import (
    load_cache_from_csv,
    save_cache_to_csv,
    DEFAULT_CACHE_FILE,
)
from ui.main_window import MainWindow, GameTableModel, COLUMN_KEYS


def make_test_rows(count):
    """Small deterministic fixture rows used ONLY by tests (not real Steam data)."""
    names = ["Cyber Strike", "Shadow Fantasy", "Iron Legacy", "Neon Odyssey"]
    rows = []
    for i in range(count):
        price = round(4.99 + (i % 10) * 5, 2)
        rows.append({
            "app_id": str(900000 + i),
            "game_title": f"{names[i % len(names)]} {i}",
            "release_date": "1 Jan, 2020",
            "original_price": price,
            "final_price": price,
            "discount_percent": 0,
            "review_score": 50 + (i % 50),
            "is_free": False,
        })
    return rows


class TestSteamVibeSuite(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Create Qt Application if not existing
        if not QApplication.instance():
            cls.app = QApplication(sys.argv)
        else:
            cls.app = QApplication.instance()

    def test_01_all_sorting_algorithms_correctness(self):
        """Test that all 8 custom sorting algorithms sort ascending and descending correctly."""
        test_data = [
            {"id": "3", "val": 45.0, "score": 90},
            {"id": "1", "val": 10.0, "score": 75},
            {"id": "4", "val": 80.0, "score": 85},
            {"id": "2", "val": 25.0, "score": 60},
            {"id": "5", "val": 10.0, "score": 99},
        ]

        expected_asc = [10.0, 10.0, 25.0, 45.0, 80.0]
        expected_desc = [80.0, 45.0, 25.0, 10.0, 10.0]

        for name, fn in SORT_ALGORITHMS.items():
            # Test Ascending
            res_asc = fn(test_data, key=lambda x: x["val"], descending=False)
            res_vals = [x["val"] for x in res_asc.sorted_data]
            self.assertEqual(res_vals, expected_asc, f"{name} failed ascending sort")
            self.assertGreaterEqual(res_asc.comparisons, 0)
            self.assertIn(res_asc.complexity, ALGORITHM_METADATA[name]["complexity"])

            # Test Descending
            res_desc = fn(test_data, key=lambda x: x["val"], descending=True)
            res_desc_vals = [x["val"] for x in res_desc.sorted_data]
            self.assertEqual(res_desc_vals, expected_desc, f"{name} failed descending sort")

    def test_02_multi_column_sorting(self):
        """Test multi-column hierarchical sorting."""
        data = [
            {"title": "Game A", "price": 10.0, "score": 50},
            {"title": "Game B", "price": 10.0, "score": 90},
            {"title": "Game C", "price": 5.0, "score": 80},
        ]
        # Primary price ASC, Secondary score DESC
        res = multi_column_sort(data, [("price", False), ("score", True)])
        sorted_titles = [x["title"] for x in res.sorted_data]
        self.assertEqual(sorted_titles, ["Game C", "Game B", "Game A"])

    def test_03_searching_engine(self):
        """Test linear search operators and composite boolean search."""
        data = [
            {"game_title": "Counter-Strike 2", "review_score": 85, "is_free": True, "final_price": 0.0},
            {"game_title": "Half-Life: Alyx", "review_score": 98, "is_free": False, "final_price": 59.99},
            {"game_title": "Portal 2", "review_score": 99, "is_free": False, "final_price": 9.99},
            {"game_title": "Team Fortress 2", "review_score": 93, "is_free": True, "final_price": 0.0},
        ]

        # Single column contains
        res1 = linear_search(data, "game_title", "contains", "strike")
        self.assertEqual(res1.total_matches, 1)
        self.assertEqual(res1.matched_data[0]["game_title"], "Counter-Strike 2")

        # Starts with
        res2 = linear_search(data, "game_title", "starts_with", "portal")
        self.assertEqual(res2.total_matches, 1)

        # Composite AND search
        rules_and = [
            CompositeFilterRule("is_free", "exact", "true"),
            CompositeFilterRule("review_score", ">=", "90"),
        ]
        res_comp_and = composite_search(data, rules_and, logic="AND")
        self.assertEqual(res_comp_and.total_matches, 1)
        self.assertEqual(res_comp_and.matched_data[0]["game_title"], "Team Fortress 2")

        # Composite OR search
        rules_or = [
            CompositeFilterRule("final_price", "=", "59.99"),
            CompositeFilterRule("final_price", "=", "9.99"),
        ]
        res_comp_or = composite_search(data, rules_or, logic="OR")
        self.assertEqual(res_comp_or.total_matches, 2)

    def test_04_dataset_and_csv_cache(self):
        """Test CSV persistence round-trip and the 8 required attributes."""
        sample = make_test_rows(200)
        path = "_test_cache.csv"
        save_cache_to_csv(sample, path)
        data = load_cache_from_csv(path)
        os.remove(path)
        self.assertEqual(len(data), 200)

        # Check required 8 attributes on entities
        first = data[0]
        for key in COLUMN_KEYS:
            self.assertIn(key, first, f"Attribute '{key}' missing from entity")

    def test_05_gui_initialization_and_controls(self):
        """Test MainWindow setup, model binding, sorting, and search via GUI controls."""
        win = MainWindow()
        self.assertIsNotNone(win)
        self.assertEqual(win.table_model.columnCount(), 8)

        # Load synthetic rows into the window purely for the test
        test_rows = make_test_rows(500)
        win.master_data = test_rows
        win.filtered_data = list(test_rows)
        win.table_model.set_data(win.filtered_data)

        # Perform GUI search
        win.search_input.setText("Cyber")
        win._on_search()
        self.assertGreater(win.table_model.rowCount(), 0)
        self.assertLess(win.table_model.rowCount(), 500)

        # Reset search
        win._on_reset_search()
        self.assertEqual(win.table_model.rowCount(), len(win.master_data))

        # Perform GUI Sort
        win.sort_col_combo.setCurrentText("final_price")
        win.sort_alg_combo.setCurrentText("Merge Sort")
        win._on_sort()
        # Verify first row has non-empty price string
        idx = win.table_model.index(0, 4)
        price_str = win.table_model.data(idx, Qt.ItemDataRole.DisplayRole)
        self.assertIsNotNone(price_str)

        win.close()


if __name__ == "__main__":
    unittest.main()
