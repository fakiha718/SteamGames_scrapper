"""
SteamVibe - Video Game Analytics & DSA Benchmarking Suite
High-Performance PyQt6 Desktop GUI with Virtualized Table, Live Scraper Controls,
Interactive Searching, Instrumented Sorting, and Multi-Algorithm Benchmarking.
"""

import os
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

from PyQt6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QObject,
    Qt,
    QThread,
    pyqtSignal,
)
from PyQt6.QtGui import QColor, QFont, QIcon
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QSplitter,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from algorithms.searching import (
    CompositeFilterRule,
    SearchResult,
    composite_search,
    linear_search,
)
from algorithms.sorting import (
    ALGORITHM_METADATA,
    SORT_ALGORITHMS,
    SortResult,
    multi_column_sort,
)
from scraper.worker import (
    DEFAULT_CACHE_FILE,
    DEFAULT_START_URL,
    DEFAULT_TARGET_COUNT,
    SteamScraperWorker,
    load_cache_from_csv,
    save_cache_to_csv,
)

# Column configurations
COLUMN_KEYS = [
    "app_id",
    "game_title",
    "release_date",
    "original_price",
    "final_price",
    "discount_percent",
    "review_score",
    "is_free",
]

COLUMN_HEADERS = [
    "App ID",
    "Game Title",
    "Release Date",
    "Original Price",
    "Final Price",
    "Discount",
    "Review Score",
    "Free to Play",
]


# ==============================================================================
# VIRTUALIZED QABSTRACTTABLEMODEL FOR ZERO-LATENCY SCROLLING (15,000+ ROWS)
# ==============================================================================
class GameTableModel(QAbstractTableModel):
    """
    High-performance virtualized table model.
    Only cells rendered on screen query data(), allowing instantaneous scrolling
    through 15,000+ items without memory duplication or UI stutter.
    """

    def __init__(self, data: Optional[List[Dict[str, Any]]] = None) -> None:
        super().__init__()
        self._data: List[Dict[str, Any]] = data or []

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._data)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(COLUMN_HEADERS)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid() or not (0 <= index.row() < len(self._data)):
            return None

        row_item = self._data[index.row()]
        col_key = COLUMN_KEYS[index.column()]
        val = row_item.get(col_key)

        if role == Qt.ItemDataRole.DisplayRole:
            if col_key in ("original_price", "final_price"):
                num_val = float(val) if val is not None else 0.0
                return "Free" if num_val == 0.0 else f"${num_val:.2f}"
            if col_key == "discount_percent":
                num_val = int(val) if val is not None else 0
                return f"-{num_val}%" if num_val > 0 else "-"
            if col_key == "review_score":
                return f"{val}%" if val is not None else "N/A"
            if col_key == "is_free":
                return "Yes" if val else "No"
            return str(val) if val is not None else ""

        if role == Qt.ItemDataRole.TextAlignmentRole:
            if col_key in ("original_price", "final_price", "discount_percent", "review_score"):
                return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            if col_key in ("app_id", "release_date", "is_free"):
                return int(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
            return int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        if role == Qt.ItemDataRole.ForegroundRole:
            if col_key == "discount_percent" and int(row_item.get("discount_percent", 0)) > 0:
                return QColor("#a3cf5b")  # Steam green for discounts
            if col_key == "final_price" and float(row_item.get("final_price", 0.0)) == 0.0:
                return QColor("#66c0f4")  # Steam blue for Free
            if col_key == "review_score":
                score = int(row_item.get("review_score", 50))
                if score >= 80:
                    return QColor("#66c0f4")  # Positive
                if score >= 60:
                    return QColor("#ffc83b")  # Mixed
                return QColor("#e05353")      # Negative

        return None

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            if 0 <= section < len(COLUMN_HEADERS):
                return COLUMN_HEADERS[section]
        if orientation == Qt.Orientation.Vertical and role == Qt.ItemDataRole.DisplayRole:
            return str(section + 1)
        return None

    def set_data(self, new_data: List[Dict[str, Any]]) -> None:
        self.beginResetModel()
        self._data = new_data
        self.endResetModel()

    def get_data(self) -> List[Dict[str, Any]]:
        return self._data


# ==============================================================================
# BENCHMARK THREAD WORKER
# ==============================================================================
class BenchmarkWorker(QThread):
    """Executes all 8 sorting algorithms on identical copies in a background thread."""
    step_finished = pyqtSignal(dict)    # Emitted when single algorithm completes
    all_finished = pyqtSignal(list)     # Emitted when entire benchmark suite finishes

    def __init__(
        self,
        dataset: List[Dict[str, Any]],
        column: str,
        descending: bool = False,
        sample_size: int = 1500,
        parent: Optional[QObject] = None
    ) -> None:
        super().__init__(parent)
        self.dataset = list(dataset[:sample_size])
        self.column = column
        self.descending = descending

    def run(self) -> None:
        results: List[Dict[str, Any]] = []

        for name, fn in SORT_ALGORITHMS.items():
            # Create fresh identical copy for fair benchmarking
            data_copy = list(self.dataset)
            res: SortResult = fn(
                data_copy,
                key=lambda x, col=self.column: x.get(col),
                descending=self.descending
            )
            item = {
                "algorithm": res.algorithm_name,
                "elapsed_ms": res.elapsed_ms,
                "comparisons": res.comparisons,
                "swaps": res.swaps,
                "complexity": res.complexity,
                "stability": res.stability,
            }
            results.append(item)
            self.step_finished.emit(item)

        # Sort results by execution time
        results.sort(key=lambda x: x["elapsed_ms"])
        self.all_finished.emit(results)


# ==============================================================================
# MODAL DIALOG: BENCHMARK SUITE
# ==============================================================================
class BenchmarkDialog(QDialog):
    """Modal dialog displaying comparison matrix across all 8 sorting algorithms."""

    def __init__(
        self,
        dataset: List[Dict[str, Any]],
        column: str,
        descending: bool = False,
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self.dataset = dataset
        self.column = column
        self.descending = descending
        self.worker: Optional[BenchmarkWorker] = None

        self.setWindowTitle("SteamVibe DSA Benchmark Suite - 8 Sorting Algorithms")
        self.resize(880, 560)
        self._setup_ui()
        self._start_benchmark()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Title Header
        header_frame = QFrame()
        header_frame.setStyleSheet("background-color: #1b2838; border-radius: 6px; padding: 10px;")
        h_layout = QVBoxLayout(header_frame)
        title_lbl = QLabel(f"⚡ Sorting Algorithm Benchmark Matrix (Target: '{self.column}')")
        title_lbl.setStyleSheet("font-size: 16px; font-weight: bold; color: #66c0f4;")
        h_layout.addWidget(title_lbl)

        sample_size = min(1500, len(self.dataset))
        sub_lbl = QLabel(
            f"Testing {len(SORT_ALGORITHMS)} custom-built algorithms from scratch on {sample_size:,} identical records. "
            f"Ordering: {'Descending' if self.descending else 'Ascending'}."
        )
        sub_lbl.setStyleSheet("color: #c7d5e0; font-size: 12px;")
        h_layout.addWidget(sub_lbl)
        layout.addWidget(header_frame)

        # Progress bar
        self.prog_bar = QProgressBar()
        self.prog_bar.setRange(0, len(SORT_ALGORITHMS))
        self.prog_bar.setValue(0)
        self.prog_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #2a475e;
                border-radius: 4px;
                text-align: center;
                background-color: #171a21;
                color: #c7d5e0;
                height: 20px;
            }
            QProgressBar::chunk {
                background-color: #66c0f4;
                border-radius: 3px;
            }
        """)
        layout.addWidget(self.prog_bar)

        # Results Table
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels([
            "Rank", "Algorithm", "Time (ms)", "Comparisons", "Swaps / Shifts", "Theoretical O", "Stability"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setStyleSheet("""
            QTableWidget {
                background-color: #16202d;
                gridline-color: #243447;
                color: #e1e7ec;
                border: 1px solid #2a475e;
                border-radius: 6px;
                font-size: 13px;
            }
            QHeaderView::section {
                background-color: #1b2838;
                color: #66c0f4;
                font-weight: bold;
                padding: 6px;
                border: 1px solid #2a475e;
            }
        """)
        layout.addWidget(self.table)

        # Insight Summary
        self.insight_lbl = QLabel("Running benchmarks... Please wait.")
        self.insight_lbl.setStyleSheet("color: #a3cf5b; font-weight: bold; font-size: 13px; padding: 4px;")
        layout.addWidget(self.insight_lbl)

        # Close button
        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def _start_benchmark(self) -> None:
        sample_size = min(1500, len(self.dataset))
        self.worker = BenchmarkWorker(
            dataset=self.dataset,
            column=self.column,
            descending=self.descending,
            sample_size=sample_size,
            parent=self
        )
        self.worker.step_finished.connect(self._on_step)
        self.worker.all_finished.connect(self._on_complete)
        self.worker.start()

    def _on_step(self, item: Dict[str, Any]) -> None:
        self.prog_bar.setValue(self.prog_bar.value() + 1)

    def _on_complete(self, results: List[Dict[str, Any]]) -> None:
        self.table.setRowCount(len(results))
        for row, item in enumerate(results):
            # Rank
            r_item = QTableWidgetItem(f"#{row + 1}")
            r_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if row == 0:
                r_item.setForeground(QColor("#a3cf5b"))
                r_item.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
            self.table.setItem(row, 0, r_item)

            # Algorithm
            alg_item = QTableWidgetItem(item["algorithm"])
            alg_item.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold if row == 0 else QFont.Weight.Normal))
            self.table.setItem(row, 1, alg_item)

            # Time
            time_item = QTableWidgetItem(f"{item['elapsed_ms']:.2f}")
            time_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            if row == 0:
                time_item.setForeground(QColor("#a3cf5b"))
            self.table.setItem(row, 2, time_item)

            # Comparisons
            cmp_item = QTableWidgetItem(f"{item['comparisons']:,}")
            cmp_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.table.setItem(row, 3, cmp_item)

            # Swaps
            swap_item = QTableWidgetItem(f"{item['swaps']:,}")
            swap_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.table.setItem(row, 4, swap_item)

            # Complexity
            cx_item = QTableWidgetItem(item["complexity"])
            cx_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 5, cx_item)

            # Stability
            st_item = QTableWidgetItem(item["stability"])
            st_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            st_item.setForeground(QColor("#a3cf5b" if item["stability"] == "Stable" else "#ff9d3b"))
            self.table.setItem(row, 6, st_item)

        winner = results[0]["algorithm"]
        winner_time = results[0]["elapsed_ms"]
        self.insight_lbl.setText(
            f"🏆 Benchmark Winner: {winner} ({winner_time:.2f} ms). "
            f"Empirical results match theoretical asymptotic bounds O(n log n) & O(d·(n+k)) vs quadratic O(n²)."
        )


# ==============================================================================
# MODAL DIALOG: MULTI-LEVEL SORT
# ==============================================================================
class MultiLevelSortDialog(QDialog):
    """Configures multi-column sorting (Primary, Secondary, Tertiary)."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Multi-Column Sort Configuration")
        self.resize(480, 260)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        info_lbl = QLabel(
            "Configure hierarchical multi-level sorting rules.\n"
            "Secondary columns break ties when primary keys are equal."
        )
        info_lbl.setStyleSheet("color: #66c0f4; font-weight: bold;")
        layout.addWidget(info_lbl)

        form = QFormLayout()

        # Primary
        self.pri_col = QComboBox()
        self.pri_col.addItems(COLUMN_KEYS)
        self.pri_col.setCurrentText("final_price")
        self.pri_desc = QCheckBox("Descending")
        h1 = QHBoxLayout()
        h1.addWidget(self.pri_col, 2)
        h1.addWidget(self.pri_desc, 1)
        form.addRow("Primary Key:", h1)

        # Secondary
        self.sec_col = QComboBox()
        self.sec_col.addItems(["(None)"] + COLUMN_KEYS)
        self.sec_col.setCurrentText("review_score")
        self.sec_desc = QCheckBox("Descending")
        self.sec_desc.setChecked(True)
        h2 = QHBoxLayout()
        h2.addWidget(self.sec_col, 2)
        h2.addWidget(self.sec_desc, 1)
        form.addRow("Secondary Key:", h2)

        # Tertiary
        self.ter_col = QComboBox()
        self.ter_col.addItems(["(None)"] + COLUMN_KEYS)
        self.ter_desc = QCheckBox("Descending")
        h3 = QHBoxLayout()
        h3.addWidget(self.ter_col, 2)
        h3.addWidget(self.ter_desc, 1)
        form.addRow("Tertiary Key:", h3)

        layout.addLayout(form)

        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def get_specs(self) -> List[Tuple[str, bool]]:
        specs: List[Tuple[str, bool]] = []
        pri = self.pri_col.currentText()
        if pri and pri != "(None)":
            specs.append((pri, self.pri_desc.isChecked()))

        sec = self.sec_col.currentText()
        if sec and sec != "(None)":
            specs.append((sec, self.sec_desc.isChecked()))

        ter = self.ter_col.currentText()
        if ter and ter != "(None)":
            specs.append((ter, self.ter_desc.isChecked()))

        return specs


# ==============================================================================
# MODAL DIALOG: COMPOSITE BOOLEAN SEARCH
# ==============================================================================
class CompositeSearchDialog(QDialog):
    """Configures composite multi-column search with AND, OR, and NOT logic."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Composite Boolean Search Engine (AND / OR / NOT)")
        self.resize(600, 320)
        self.rule_rows: List[Tuple[QComboBox, QComboBox, QLineEdit, QCheckBox]] = []
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        header = QLabel("Combine multiple criteria using boolean operators (AND / OR) with NOT support:")
        header.setStyleSheet("color: #66c0f4; font-weight: bold;")
        layout.addWidget(header)

        # Logic selector
        logic_box = QHBoxLayout()
        logic_box.addWidget(QLabel("Match Condition:"))
        self.logic_combo = QComboBox()
        self.logic_combo.addItems(["AND (All conditions must be met)", "OR (Any condition matches)"])
        logic_box.addWidget(self.logic_combo)
        layout.addLayout(logic_box)

        # Rules container
        self.rules_layout = QVBoxLayout()
        layout.addLayout(self.rules_layout)

        # Pre-populate with 2 default rule rows
        self._add_rule_row("final_price", "<=", "10.0", False)
        self._add_rule_row("review_score", ">=", "80", False)

        add_btn = QPushButton("+ Add Another Filter Rule")
        add_btn.clicked.connect(lambda: self._add_rule_row("game_title", "contains", "", False))
        layout.addWidget(add_btn)

        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def _add_rule_row(self, col: str, op: str, val: str, negate: bool) -> None:
        row_widget = QWidget()
        row_h = QHBoxLayout(row_widget)
        row_h.setContentsMargins(0, 2, 0, 2)

        c_box = QComboBox()
        c_box.addItems(COLUMN_KEYS)
        c_box.setCurrentText(col)

        op_box = QComboBox()
        op_box.addItems(["contains", "starts_with", "ends_with", "exact", ">", "<", ">=", "<=", "="])
        op_box.setCurrentText(op)

        val_edit = QLineEdit(val)
        val_edit.setPlaceholderText("Filter value...")

        not_chk = QCheckBox("NOT")
        not_chk.setChecked(negate)

        row_h.addWidget(c_box, 2)
        row_h.addWidget(op_box, 2)
        row_h.addWidget(val_edit, 3)
        row_h.addWidget(not_chk, 1)

        self.rules_layout.addWidget(row_widget)
        self.rule_rows.append((c_box, op_box, val_edit, not_chk))

    def get_query(self) -> Tuple[List[CompositeFilterRule], str]:
        rules: List[CompositeFilterRule] = []
        for c_box, op_box, val_edit, not_chk in self.rule_rows:
            val = val_edit.text().strip()
            if val:
                rules.append(CompositeFilterRule(
                    column=c_box.currentText(),
                    operator=op_box.currentText(),
                    value=val,
                    negate=not_chk.isChecked()
                ))
        logic = "AND" if "AND" in self.logic_combo.currentText() else "OR"
        return rules, logic


# ==============================================================================
# MODAL DIALOG: ADD / EDIT GAME RECORD (CRUD)
# ==============================================================================
class AddEditGameDialog(QDialog):
    """Dialog for manually adding a new game or editing an existing game record."""

    def __init__(
        self,
        game_data: Optional[Dict[str, Any]] = None,
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self.is_edit = game_data is not None
        self.setWindowTitle("Edit Game Record" if self.is_edit else "Add New Game Record")
        self.resize(500, 420)
        self._setup_ui(game_data or {})

    def _setup_ui(self, data: Dict[str, Any]) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        header = QLabel("✏️  Edit Game Record" if self.is_edit else "➕  Add New Game Record")
        header.setStyleSheet(
            "font-size: 15px; font-weight: bold; color: #66c0f4; "
            "background-color: #1b2838; border-radius: 6px; padding: 8px;"
        )
        layout.addWidget(header)

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        # App ID
        self.app_id_edit = QLineEdit(str(data.get("app_id", "")))
        self.app_id_edit.setPlaceholderText("e.g. 730")
        if self.is_edit:
            self.app_id_edit.setReadOnly(True)
            self.app_id_edit.setToolTip("App ID is locked when editing an existing record.")
        form.addRow("App ID *:", self.app_id_edit)

        # Game Title
        self.title_edit = QLineEdit(str(data.get("game_title", "")))
        self.title_edit.setPlaceholderText("e.g. Counter-Strike 2")
        form.addRow("Game Title *:", self.title_edit)

        # Release Date
        self.date_edit = QLineEdit(str(data.get("release_date", "")))
        self.date_edit.setPlaceholderText("e.g. 27 Sep, 2023")
        form.addRow("Release Date:", self.date_edit)

        # Original Price
        self.orig_price_spin = QDoubleSpinBox()
        self.orig_price_spin.setRange(0.0, 9999.99)
        self.orig_price_spin.setDecimals(2)
        self.orig_price_spin.setPrefix("$ ")
        self.orig_price_spin.setValue(float(data.get("original_price", 0.0)))
        form.addRow("Original Price:", self.orig_price_spin)

        # Final Price
        self.final_price_spin = QDoubleSpinBox()
        self.final_price_spin.setRange(0.0, 9999.99)
        self.final_price_spin.setDecimals(2)
        self.final_price_spin.setPrefix("$ ")
        self.final_price_spin.setValue(float(data.get("final_price", 0.0)))
        form.addRow("Final Price:", self.final_price_spin)

        # Discount
        self.discount_spin = QSpinBox()
        self.discount_spin.setRange(0, 100)
        self.discount_spin.setSuffix(" %")
        self.discount_spin.setValue(int(data.get("discount_percent", 0)))
        form.addRow("Discount:", self.discount_spin)

        # Review Score
        self.review_spin = QSpinBox()
        self.review_spin.setRange(0, 100)
        self.review_spin.setSuffix(" %")
        self.review_spin.setValue(int(data.get("review_score", 50)))
        form.addRow("Review Score:", self.review_spin)

        # Is Free
        self.is_free_chk = QCheckBox("Free to Play")
        self.is_free_chk.setChecked(bool(data.get("is_free", False)))
        form.addRow("Status:", self.is_free_chk)

        layout.addLayout(form)

        note = QLabel("* Required fields")
        note.setStyleSheet("color: #8f98a0; font-size: 11px;")
        layout.addWidget(note)

        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.accepted.connect(self._validate_and_accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def _validate_and_accept(self) -> None:
        if not self.app_id_edit.text().strip():
            QMessageBox.warning(self, "Validation Error", "App ID cannot be empty.")
            return
        if not self.title_edit.text().strip():
            QMessageBox.warning(self, "Validation Error", "Game Title cannot be empty.")
            return
        self.accept()

    def get_data(self) -> Dict[str, Any]:
        return {
            "app_id": self.app_id_edit.text().strip(),
            "game_title": self.title_edit.text().strip(),
            "release_date": self.date_edit.text().strip() or "Unknown",
            "original_price": round(self.orig_price_spin.value(), 2),
            "final_price": round(self.final_price_spin.value(), 2),
            "discount_percent": self.discount_spin.value(),
            "review_score": self.review_spin.value(),
            "is_free": self.is_free_chk.isChecked(),
        }


# ==============================================================================
# MAIN APPLICATION WINDOW
# ==============================================================================
class MainWindow(QMainWindow):
    """Main window of the SteamVibe Video Game Analytics & DSA Suite."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("SteamVibe - Video Game Analytics & DSA Benchmarking Suite")
        self.resize(1340, 860)
        self.setMinimumSize(1000, 680)

        # Master dataset & filtered dataset
        self.master_data: List[Dict[str, Any]] = []
        self.filtered_data: List[Dict[str, Any]] = []

        # Scraper worker reference
        self.scraper_worker: Optional[SteamScraperWorker] = None

        self._setup_ui()
        self._load_initial_cache()

    # ==========================================================================
    # UI SETUP
    # ==========================================================================
    def _setup_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(14, 14, 14, 10)
        main_layout.setSpacing(10)

        # Top Header Brand
        main_layout.addWidget(self._build_header_widget())

        # Top Control Panels
        main_layout.addWidget(self._build_scraper_bar())
        main_layout.addWidget(self._build_search_bar())
        main_layout.addWidget(self._build_sorting_bar())
        main_layout.addWidget(self._build_crud_bar())

        # Central Virtualized Table View
        self.table_view = QTableView()
        self.table_model = GameTableModel([])
        self.table_view.setModel(self.table_model)
        self.table_view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_view.setAlternatingRowColors(True)
        self.table_view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table_view.horizontalHeader().setStretchLastSection(True)
        self.table_view.verticalHeader().setDefaultSectionSize(28)
        self.table_view.setShowGrid(True)
        # Right-click context menu + double-click to edit
        self.table_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table_view.customContextMenuRequested.connect(self._on_context_menu)
        self.table_view.doubleClicked.connect(self._on_edit_game)
        main_layout.addWidget(self.table_view, 1)

        # Metrics Panel
        main_layout.addWidget(self._build_metrics_panel())

        # Status Bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_msg_lbl = QLabel("Ready")
        self.status_bar.addWidget(self.status_msg_lbl, 1)

        self.row_count_lbl = QLabel("Entities: 0")
        self.row_count_lbl.setStyleSheet("font-weight: bold; color: #66c0f4; margin-right: 12px;")
        self.status_bar.addPermanentWidget(self.row_count_lbl)

        # Apply Global Dark Stylesheet
        self._apply_theme()

    def _build_header_widget(self) -> QWidget:
        header = QFrame()
        header.setObjectName("headerCard")
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(12, 8, 12, 8)

        brand_layout = QVBoxLayout()
        title = QLabel("🎮 SteamVibe Analytics & DSA Benchmarking Suite")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #66c0f4;")
        subtitle = QLabel("Pure HTML DOM Scraping & In-Memory Algorithmic Analysis (15,000+ PC Games)")
        subtitle.setStyleSheet("font-size: 12px; color: #8f98a0;")
        brand_layout.addWidget(title)
        brand_layout.addWidget(subtitle)
        h_layout.addLayout(brand_layout)
        h_layout.addStretch(1)

        return header

    def _build_crud_bar(self) -> QWidget:
        box = QGroupBox("4. CRUD Operations — Manage Game Records")
        layout = QHBoxLayout(box)

        self.btn_add_game = QPushButton("➕  Add Game")
        self.btn_add_game.setObjectName("btnAdd")
        self.btn_add_game.setToolTip("Manually add a new game record to the catalog")
        self.btn_add_game.clicked.connect(self._on_add_game)
        layout.addWidget(self.btn_add_game)

        self.btn_edit_game = QPushButton("✏️  Edit Selected")
        self.btn_edit_game.setObjectName("btnEdit")
        self.btn_edit_game.setToolTip("Edit the selected row  (or just double-click any row)")
        self.btn_edit_game.clicked.connect(self._on_edit_game)
        layout.addWidget(self.btn_edit_game)

        self.btn_delete_game = QPushButton("🗑  Delete Selected")
        self.btn_delete_game.setObjectName("btnDelete")
        self.btn_delete_game.setToolTip("Permanently delete the selected game row")
        self.btn_delete_game.clicked.connect(self._on_delete_game)
        layout.addWidget(self.btn_delete_game)

        layout.addStretch(1)

        hint = QLabel("💡 Right-click any row for quick actions  |  Double-click a row to edit")
        hint.setStyleSheet("color: #8f98a0; font-size: 11px;")
        layout.addWidget(hint)

        return box

    def _build_scraper_bar(self) -> QWidget:
        box = QGroupBox("1. Scraper Engine (Pure HTML DOM via BeautifulSoup)")
        layout = QVBoxLayout(box)
        layout.setSpacing(8)

        # Top row: URL input (Bonus) + Action buttons
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Catalog URL:"))
        self.url_input = QLineEdit(DEFAULT_START_URL)
        self.url_input.setToolTip("Target pagination URL for HTML DOM scraping (Bonus feature)")
        row1.addWidget(self.url_input, 3)

        self.btn_start = QPushButton("▶ Start Scraper")
        self.btn_start.setObjectName("btnPrimary")
        self.btn_start.clicked.connect(self._on_start_scraper)
        row1.addWidget(self.btn_start)

        self.btn_pause = QPushButton("⏸ Pause")
        self.btn_pause.setEnabled(False)
        self.btn_pause.clicked.connect(self._on_pause_scraper)
        row1.addWidget(self.btn_pause)

        self.btn_resume = QPushButton("⏯ Resume")
        self.btn_resume.setEnabled(False)
        self.btn_resume.clicked.connect(self._on_resume_scraper)
        row1.addWidget(self.btn_resume)

        self.btn_stop = QPushButton("⏹ Stop")
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self._on_stop_scraper)
        row1.addWidget(self.btn_stop)

        self.btn_seed = QPushButton("🗑 Clear Data")
        self.btn_seed.setToolTip("Delete all scraped games (table and saved CSV) to start a fresh scrape")
        self.btn_seed.clicked.connect(self._on_clear_data)
        row1.addWidget(self.btn_seed)

        layout.addLayout(row1)

        # Bottom row: Live progress bar and indicator
        row2 = QHBoxLayout()
        self.scraper_progress = QProgressBar()
        self.scraper_progress.setRange(0, DEFAULT_TARGET_COUNT)
        self.scraper_progress.setValue(0)
        row2.addWidget(self.scraper_progress, 4)

        self.scraper_count_lbl = QLabel(f"Scraped: 0 / {DEFAULT_TARGET_COUNT:,}")
        self.scraper_count_lbl.setStyleSheet("font-weight: bold; color: #a3cf5b;")
        row2.addWidget(self.scraper_count_lbl, 1)
        layout.addLayout(row2)

        return box

    def _build_search_bar(self) -> QWidget:
        box = QGroupBox("2. Searching & Filtering Engine")
        layout = QHBoxLayout(box)

        layout.addWidget(QLabel("Column:"))
        self.search_col_combo = QComboBox()
        self.search_col_combo.addItems(COLUMN_KEYS)
        self.search_col_combo.setCurrentText("game_title")
        layout.addWidget(self.search_col_combo)

        layout.addWidget(QLabel("Operator:"))
        self.search_op_combo = QComboBox()
        self.search_op_combo.addItems(["contains", "starts_with", "ends_with", "exact", ">", "<", ">=", "<=", "="])
        layout.addWidget(self.search_op_combo)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search query (e.g. Strike, Cyber, 19.99)...")
        self.search_input.returnPressed.connect(self._on_search)
        layout.addWidget(self.search_input, 2)

        self.btn_search = QPushButton("🔍 Search")
        self.btn_search.clicked.connect(self._on_search)
        layout.addWidget(self.btn_search)

        self.btn_reset_search = QPushButton("↺ Reset")
        self.btn_reset_search.clicked.connect(self._on_reset_search)
        layout.addWidget(self.btn_reset_search)

        self.btn_composite_search = QPushButton("🧩 Composite (AND/OR)...")
        self.btn_composite_search.setToolTip("Build multi-column boolean queries with AND/OR/NOT")
        self.btn_composite_search.clicked.connect(self._on_open_composite_search)
        layout.addWidget(self.btn_composite_search)

        return box

    def _build_sorting_bar(self) -> QWidget:
        box = QGroupBox("3. Sorting Algorithms & Benchmarking Engine")
        layout = QHBoxLayout(box)

        layout.addWidget(QLabel("Column:"))
        self.sort_col_combo = QComboBox()
        self.sort_col_combo.addItems(COLUMN_KEYS)
        self.sort_col_combo.setCurrentText("final_price")
        layout.addWidget(self.sort_col_combo)

        layout.addWidget(QLabel("Algorithm:"))
        self.sort_alg_combo = QComboBox()
        self.sort_alg_combo.addItems(list(SORT_ALGORITHMS.keys()))
        self.sort_alg_combo.setCurrentText("Quick Sort")
        layout.addWidget(self.sort_alg_combo)

        self.sort_desc_chk = QCheckBox("Descending")
        layout.addWidget(self.sort_desc_chk)

        self.sort_filtered_only_chk = QCheckBox("Sort Only Filtered")
        self.sort_filtered_only_chk.setToolTip("Sort only the currently active search results instead of all entities")
        layout.addWidget(self.sort_filtered_only_chk)

        self.btn_sort = QPushButton("📊 Sort")
        self.btn_sort.setObjectName("btnSort")
        self.btn_sort.clicked.connect(self._on_sort)
        layout.addWidget(self.btn_sort)

        self.btn_multi_sort = QPushButton("🔀 Multi-Level Sort...")
        self.btn_multi_sort.clicked.connect(self._on_open_multi_sort)
        layout.addWidget(self.btn_multi_sort)

        self.btn_benchmark = QPushButton("⚡ Benchmark All (8)")
        self.btn_benchmark.setObjectName("btnBenchmark")
        self.btn_benchmark.clicked.connect(self._on_open_benchmark)
        layout.addWidget(self.btn_benchmark)

        return box

    def _build_metrics_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("metricsPanel")
        layout = QHBoxLayout(panel)
        layout.setContentsMargins(12, 8, 12, 8)

        self.metrics_label = QLabel("🚀 Select an algorithm or search operation above to inspect live DSA performance metrics.")
        self.metrics_label.setStyleSheet("font-size: 13px; font-weight: bold; color: #a3cf5b;")
        layout.addWidget(self.metrics_label, 1)

        return panel

    def _apply_theme(self) -> None:
        self.setStyleSheet("""
            QMainWindow, QWidget {
                background-color: #171a21;
                color: #c7d5e0;
                font-family: 'Segoe UI', 'Roboto', 'Arial', sans-serif;
                font-size: 12px;
            }
            QGroupBox {
                border: 1px solid #2a475e;
                border-radius: 6px;
                margin-top: 6px;
                padding-top: 10px;
                font-weight: bold;
                color: #66c0f4;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
            }
            #headerCard {
                background-color: #1b2838;
                border: 1px solid #2a475e;
                border-radius: 6px;
            }
            #metricsPanel {
                background-color: #16202d;
                border: 1px solid #2a475e;
                border-radius: 6px;
            }
            QLineEdit, QComboBox, QSpinBox {
                background-color: #1b2838;
                border: 1px solid #2a475e;
                border-radius: 4px;
                padding: 5px 8px;
                color: #ffffff;
                selection-background-color: #66c0f4;
            }
            QLineEdit:focus, QComboBox:focus {
                border: 1px solid #66c0f4;
            }
            QPushButton {
                background-color: #213247;
                border: 1px solid #2a475e;
                border-radius: 4px;
                padding: 6px 12px;
                color: #c7d5e0;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2a475e;
                color: #ffffff;
                border-color: #66c0f4;
            }
            QPushButton:pressed {
                background-color: #171a21;
            }
            QPushButton:disabled {
                background-color: #16202d;
                color: #4f5a66;
                border-color: #202b38;
            }
            #btnPrimary {
                background-color: #1999ff;
                color: #ffffff;
                border: none;
            }
            #btnPrimary:hover {
                background-color: #40b0ff;
            }
            #btnSort {
                background-color: #2a7a40;
                color: #ffffff;
                border: none;
            }
            #btnSort:hover {
                background-color: #389d54;
            }
            #btnBenchmark {
                background-color: #7934a3;
                color: #ffffff;
                border: none;
            }
            #btnBenchmark:hover {
                background-color: #9343c4;
            }
            #btnAdd {
                background-color: #1a7a1a;
                color: #ffffff;
                border: none;
            }
            #btnAdd:hover {
                background-color: #28a428;
            }
            #btnEdit {
                background-color: #7a6000;
                color: #ffffff;
                border: none;
            }
            #btnEdit:hover {
                background-color: #b38800;
            }
            #btnDelete {
                background-color: #7a1a1a;
                color: #ffffff;
                border: none;
            }
            #btnDelete:hover {
                background-color: #a42828;
            }
            QTableView {
                background-color: #16202d;
                alternate-background-color: #1b2838;
                border: 1px solid #2a475e;
                border-radius: 6px;
                gridline-color: #223042;
                selection-background-color: #2a475e;
                selection-color: #ffffff;
                color: #c7d5e0;
            }
            QHeaderView::section {
                background-color: #1b2838;
                color: #66c0f4;
                font-weight: bold;
                padding: 5px;
                border: 1px solid #243447;
            }
            QProgressBar {
                border: 1px solid #2a475e;
                border-radius: 4px;
                text-align: center;
                background-color: #16202d;
                color: #ffffff;
                font-weight: bold;
                height: 18px;
            }
            QProgressBar::chunk {
                background-color: #66c0f4;
                border-radius: 3px;
            }
            QCheckBox {
                spacing: 6px;
                color: #c7d5e0;
            }
            QCheckBox::indicator {
                width: 14px;
                height: 14px;
                background-color: #1b2838;
                border: 1px solid #2a475e;
                border-radius: 3px;
            }
            QCheckBox::indicator:checked {
                background-color: #66c0f4;
                border-color: #66c0f4;
            }
            QStatusBar {
                background-color: #171a21;
                border-top: 1px solid #243447;
                color: #8f98a0;
            }
        """)

    # ==========================================================================
    # DATASET MANAGEMENT & CACHING
    # ==========================================================================
    def _load_initial_cache(self) -> None:
        """Loads previously scraped records from the CSV cache (real data only, no auto-seeding)."""
        data = load_cache_from_csv(DEFAULT_CACHE_FILE)

        self.master_data = data[:DEFAULT_TARGET_COUNT]
        self.filtered_data = list(self.master_data)
        self.table_model.set_data(self.filtered_data)
        self._update_counts_display()
        if self.master_data:
            self.status_msg_lbl.setText(f"Loaded {len(self.master_data):,} scraped games from cache '{DEFAULT_CACHE_FILE}'.")
            self.metrics_label.setText(
                f"✅ {len(self.master_data):,} scraped games loaded. "
                f"Click 'Start Scraper' to collect more, or 'Sort' / 'Benchmark' to analyze."
            )
        else:
            self.status_msg_lbl.setText("No cached data yet. Click 'Start Scraper' to collect games from Steam.")
            self.metrics_label.setText("👋 No data yet. Click 'Start Scraper' to scrape real games from Steam.")

    def _update_counts_display(self) -> None:
        total = len(self.master_data)
        shown = len(self.filtered_data)
        self.scraper_progress.setValue(min(total, DEFAULT_TARGET_COUNT))
        self.scraper_count_lbl.setText(f"Entities: {total:,} / {DEFAULT_TARGET_COUNT:,}")
        if shown == total:
            self.row_count_lbl.setText(f"Showing all {total:,} games")
        else:
            self.row_count_lbl.setText(f"Showing {shown:,} of {total:,} games")

    # ==========================================================================
    # SCRAPER CONTROLS (THREAD SAFE VIA QMUTEX / QWAITCONDITION)
    # ==========================================================================
    def _on_start_scraper(self) -> None:
        url = self.url_input.text().strip()
        if not url:
            url = DEFAULT_START_URL

        # Resume: keep games already collected and continue from roughly where we stopped
        existing = list(self.master_data)
        if len(existing) >= DEFAULT_TARGET_COUNT:
            QMessageBox.information(
                self,
                "Target reached",
                f"You already have {len(existing):,} scraped games (target {DEFAULT_TARGET_COUNT:,}).\n"
                "Use 'Clear Data' if you want to start over."
            )
            return
        resume_page = max(1, len(existing) // 25 - 1)  # small overlap; duplicates are skipped
        self._status_history = []

        self.scraper_worker = SteamScraperWorker(
            start_url=url,
            target_count=DEFAULT_TARGET_COUNT,
            cache_filepath=DEFAULT_CACHE_FILE,
            parent=self,
            initial_data=existing,
            start_page=resume_page
        )
        self.scraper_worker.progress_updated.connect(self._on_scraper_progress)
        self.scraper_worker.batch_scraped.connect(self._on_scraper_batch)
        self.scraper_worker.status_message.connect(self._on_scraper_status)
        self.scraper_worker.finished_signal.connect(self._on_scraper_finished)
        self.scraper_worker.error_occurred.connect(self._on_scraper_error)

        self.btn_start.setEnabled(False)
        self.btn_pause.setEnabled(True)
        self.btn_resume.setEnabled(False)
        self.btn_stop.setEnabled(True)

        self.status_msg_lbl.setText("Scraper started...")
        self.scraper_worker.start()

    def _on_pause_scraper(self) -> None:
        if self.scraper_worker:
            self.scraper_worker.pause()
            self.btn_pause.setEnabled(False)
            self.btn_resume.setEnabled(True)

    def _on_resume_scraper(self) -> None:
        if self.scraper_worker:
            self.scraper_worker.resume()
            self.btn_pause.setEnabled(True)
            self.btn_resume.setEnabled(False)

    def _on_stop_scraper(self) -> None:
        if self.scraper_worker:
            self.scraper_worker.stop()
            self.btn_start.setEnabled(True)
            self.btn_pause.setEnabled(False)
            self.btn_resume.setEnabled(False)
            self.btn_stop.setEnabled(False)

    def _on_clear_data(self) -> None:
        """Deletes all scraped games (table + CSV cache) so a fresh scrape can start."""
        if self.scraper_worker and self.scraper_worker.isRunning():
            QMessageBox.warning(self, "Scraper running", "Stop the scraper before clearing data.")
            return
        reply = QMessageBox.question(
            self,
            "Clear Data",
            "Delete all scraped games (table and saved CSV)?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self.master_data = []
        self.filtered_data = []
        self.table_model.set_data(self.filtered_data)
        try:
            if os.path.exists(DEFAULT_CACHE_FILE):
                os.remove(DEFAULT_CACHE_FILE)
        except OSError:
            pass
        self._update_counts_display()
        self.status_msg_lbl.setText("Data cleared.")
        self.metrics_label.setText("Data cleared. Click 'Start Scraper' to scrape real games from Steam.")

    def _on_scraper_progress(self, current: int, target: int) -> None:
        self.scraper_progress.setValue(current)
        self.scraper_count_lbl.setText(f"Scraped: {current:,} / {target:,}")

    def _on_scraper_batch(self, batch: List[Dict[str, Any]]) -> None:
        existing_ids = {x["app_id"] for x in self.master_data}
        added = False
        for item in batch:
            if item["app_id"] not in existing_ids:
                self.master_data.append(item)
                existing_ids.add(item["app_id"])
                added = True
        if added:
            self.filtered_data = list(self.master_data)
            self.table_model.set_data(self.filtered_data)
            self._update_counts_display()

    def _on_scraper_status(self, msg: str) -> None:
        self._status_history = (getattr(self, "_status_history", []) + [msg])[-5:]
        self.status_msg_lbl.setText(msg)

    def _on_scraper_error(self, err: str) -> None:
        self._status_history = (getattr(self, "_status_history", []) + [err])[-5:]
        self.status_msg_lbl.setText(f"Scraper Error: {err}")

    def _on_scraper_finished(self, data: List[Dict[str, Any]]) -> None:
        self.btn_start.setEnabled(True)
        self.btn_pause.setEnabled(False)
        self.btn_resume.setEnabled(False)
        self.btn_stop.setEnabled(False)
        self.status_msg_lbl.setText(f"Scraping run completed. Total managed: {len(self.master_data):,}")
        if not self.master_data:
            reasons = "\n".join(getattr(self, "_status_history", [])[:-1]) or "No details available."
            QMessageBox.warning(
                self,
                "No games scraped",
                "0 games were scraped.\n\n"
                "Check that the Catalog URL is a Steam search link, for example:\n"
                f"{DEFAULT_START_URL}\n\n"
                f"What happened:\n{reasons}"
            )
            return
        QMessageBox.information(
            self,
            "Scraping Complete",
            f"Successfully finished scraping run!\nTotal catalog size: {len(self.master_data):,} games."
        )

    # ==========================================================================
    # SEARCHING & FILTERING
    # ==========================================================================
    def _on_search(self) -> None:
        query = self.search_input.text().strip()
        col = self.search_col_combo.currentText()
        op = self.search_op_combo.currentText()

        if not query:
            self._on_reset_search()
            return

        res: SearchResult = linear_search(self.master_data, col, op, query)
        self.filtered_data = res.matched_data
        self.table_model.set_data(self.filtered_data)
        self._update_counts_display()

        self.metrics_label.setText(
            f"🔍 [Search] {res.query_summary} | Matches: {res.total_matches:,} | "
            f"Comparisons: {res.comparisons:,} | Time: {res.elapsed_ms:.2f} ms"
        )
        self.status_msg_lbl.setText(res.summary())

    def _on_reset_search(self) -> None:
        self.search_input.clear()
        self.filtered_data = list(self.master_data)
        self.table_model.set_data(self.filtered_data)
        self._update_counts_display()
        self.metrics_label.setText("Search filters cleared. Displaying all catalog entities.")
        self.status_msg_lbl.setText("Showing all records.")

    def _on_open_composite_search(self) -> None:
        dlg = CompositeSearchDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            rules, logic = dlg.get_query()
            res = composite_search(self.master_data, rules, logic=logic)
            self.filtered_data = res.matched_data
            self.table_model.set_data(self.filtered_data)
            self._update_counts_display()
            self.metrics_label.setText(
                f"🧩 [Composite Search ({logic})] {res.query_summary} | "
                f"Matches: {res.total_matches:,} | Comparisons: {res.comparisons:,} | Time: {res.elapsed_ms:.2f} ms"
            )
            self.status_msg_lbl.setText(res.summary())

    # ==========================================================================
    # SORTING & BENCHMARKING
    # ==========================================================================
    def _on_sort(self) -> None:
        alg_name = self.sort_alg_combo.currentText()
        col = self.sort_col_combo.currentText()
        desc = self.sort_desc_chk.isChecked()
        only_filtered = self.sort_filtered_only_chk.isChecked()

        target_list = self.filtered_data if only_filtered else self.master_data
        if not target_list:
            QMessageBox.warning(self, "No Data", "No game data available to sort.")
            return

        # Warning for O(n^2) algorithms on 15,000 items
        if len(target_list) > 3000 and alg_name in ("Bubble Sort", "Selection Sort", "Insertion Sort"):
            reply = QMessageBox.question(
                self,
                "Slow Algorithm Warning",
                f"{alg_name} has O(n²) theoretical complexity.\n"
                f"Sorting {len(target_list):,} records may take 20-40 seconds in pure Python.\n"
                "For instantaneous sorting, Merge Sort, Quick Sort, or Radix Sort are recommended.\n\n"
                "Do you wish to proceed?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            sort_fn = SORT_ALGORITHMS[alg_name]
            res: SortResult = sort_fn(
                target_list,
                key=lambda x: x.get(col),
                descending=desc
            )

            if only_filtered:
                self.filtered_data = res.sorted_data
            else:
                self.master_data = res.sorted_data
                self.filtered_data = list(self.master_data)

            self.table_model.set_data(self.filtered_data)
            self._update_counts_display()

            # Display Prominent Status & Metrics
            metrics_text = (
                f"[{res.algorithm_name}] Time: {res.elapsed_ms:.2f} ms | "
                f"Comparisons: {res.comparisons:,} | Swaps: {res.swaps:,} | "
                f"Complexity: {res.complexity} | Stability: {res.stability}"
            )
            self.metrics_label.setText(metrics_text)
            self.status_msg_lbl.setText(f"Sorted {len(res.sorted_data):,} records by '{col}'. {metrics_text}")

        finally:
            QApplication.restoreOverrideCursor()

    def _on_open_multi_sort(self) -> None:
        dlg = MultiLevelSortDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            specs = dlg.get_specs()
            if not specs:
                return

            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            try:
                res = multi_column_sort(self.filtered_data, specs, algorithm_name="Merge Sort")
                self.filtered_data = res.sorted_data
                self.table_model.set_data(self.filtered_data)
                self._update_counts_display()

                spec_summary = ", ".join([f"{col} ({'DESC' if desc else 'ASC'})" for col, desc in specs])
                metrics_text = (
                    f"[Multi-Level Sort: {spec_summary}] Time: {res.elapsed_ms:.2f} ms | "
                    f"Comparisons: {res.comparisons:,} | Swaps: {res.swaps:,} | "
                    f"Complexity: {res.complexity} | Stability: {res.stability}"
                )
                self.metrics_label.setText(metrics_text)
                self.status_msg_lbl.setText(metrics_text)
            finally:
                QApplication.restoreOverrideCursor()

    def _on_open_benchmark(self) -> None:
        col = self.sort_col_combo.currentText()
        desc = self.sort_desc_chk.isChecked()
        target_list = self.filtered_data if self.filtered_data else self.master_data
        if not target_list:
            QMessageBox.warning(self, "No Data", "No records available for benchmark.")
            return

        dlg = BenchmarkDialog(
            dataset=target_list,
            column=col,
            descending=desc,
            parent=self
        )
        dlg.exec()

    # ==========================================================================
    # CRUD OPERATIONS — CREATE / UPDATE / DELETE
    # ==========================================================================
    def _on_add_game(self) -> None:
        """CREATE: Opens dialog to manually add a new game record."""
        dlg = AddEditGameDialog(game_data=None, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            new_game = dlg.get_data()

            # Guard: duplicate App ID check
            existing_ids = {x["app_id"] for x in self.master_data}
            if new_game["app_id"] in existing_ids:
                QMessageBox.warning(
                    self,
                    "Duplicate App ID",
                    f"A game with App ID '{new_game['app_id']}' already exists.\n"
                    "Please use a unique App ID."
                )
                return

            self.master_data.append(new_game)
            self.filtered_data = list(self.master_data)
            self.table_model.set_data(self.filtered_data)
            self._update_counts_display()
            save_cache_to_csv(self.master_data, DEFAULT_CACHE_FILE)

            self.status_msg_lbl.setText(
                f"✅ [CREATE] Added '{new_game['game_title']}' (App ID: {new_game['app_id']})"
            )
            self.metrics_label.setText(
                f"➕ [CREATE] '{new_game['game_title']}' added. "
                f"Total records: {len(self.master_data):,}. Changes saved to CSV."
            )

    def _on_edit_game(self, index=None) -> None:
        """UPDATE: Opens dialog to edit the currently selected game row."""
        selected = self.table_view.selectionModel().selectedRows()
        if not selected:
            QMessageBox.information(
                self, "No Row Selected",
                "Please click on a row in the table to select it, then press Edit."
            )
            return

        row_idx = selected[0].row()
        if row_idx < 0 or row_idx >= len(self.filtered_data):
            return

        current_data = dict(self.filtered_data[row_idx])
        dlg = AddEditGameDialog(game_data=current_data, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            updated = dlg.get_data()
            app_id = updated["app_id"]

            # Update in filtered_data
            self.filtered_data[row_idx] = updated

            # Update in master_data (match by app_id)
            for i, item in enumerate(self.master_data):
                if item["app_id"] == app_id:
                    self.master_data[i] = updated
                    break

            self.table_model.set_data(self.filtered_data)
            save_cache_to_csv(self.master_data, DEFAULT_CACHE_FILE)

            self.status_msg_lbl.setText(
                f"✅ [UPDATE] Updated '{updated['game_title']}' (App ID: {app_id})"
            )
            self.metrics_label.setText(
                f"✏️ [UPDATE] '{updated['game_title']}' (ID: {app_id}) edited successfully. "
                f"Changes saved to CSV."
            )

    def _on_delete_game(self) -> None:
        """DELETE: Removes the selected game row after user confirmation."""
        selected = self.table_view.selectionModel().selectedRows()
        if not selected:
            QMessageBox.information(
                self, "No Row Selected",
                "Please click on a row in the table to select it, then press Delete."
            )
            return

        row_idx = selected[0].row()
        if row_idx < 0 or row_idx >= len(self.filtered_data):
            return

        game = self.filtered_data[row_idx]
        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Are you sure you want to permanently delete:\n\n"
            f"  '{game['game_title']}'  (App ID: {game['app_id']})\n\n"
            "This will also remove it from the saved CSV file.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        app_id = game["app_id"]
        title = game["game_title"]

        self.filtered_data.pop(row_idx)
        self.master_data = [x for x in self.master_data if x["app_id"] != app_id]

        self.table_model.set_data(self.filtered_data)
        self._update_counts_display()
        save_cache_to_csv(self.master_data, DEFAULT_CACHE_FILE)

        self.status_msg_lbl.setText(f"🗑 [DELETE] Deleted '{title}' (App ID: {app_id})")
        self.metrics_label.setText(
            f"🗑 [DELETE] '{title}' (ID: {app_id}) removed. "
            f"Remaining records: {len(self.master_data):,}. Changes saved to CSV."
        )

    def _on_context_menu(self, position) -> None:
        """Shows a right-click context menu on the table with CRUD quick actions."""
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background-color: #1b2838; color: #c7d5e0; border: 1px solid #2a475e; }"
            "QMenu::item:selected { background-color: #2a475e; color: #ffffff; }"
            "QMenu::separator { background-color: #2a475e; height: 1px; margin: 3px 6px; }"
        )

        add_action = menu.addAction("➕  Add New Game")
        add_action.triggered.connect(self._on_add_game)

        selected = self.table_view.selectionModel().selectedRows()
        if selected:
            row_idx = selected[0].row()
            if 0 <= row_idx < len(self.filtered_data):
                game = self.filtered_data[row_idx]
                short_title = game['game_title'][:35] + ("…" if len(game['game_title']) > 35 else "")

                menu.addSeparator()
                edit_action = menu.addAction(f"✏️  Edit  \u2014  {short_title}")
                edit_action.triggered.connect(self._on_edit_game)

                menu.addSeparator()
                del_action = menu.addAction(f"🗑  Delete  \u2014  {short_title}")
                del_action.triggered.connect(self._on_delete_game)

        menu.exec(self.table_view.viewport().mapToGlobal(position))
