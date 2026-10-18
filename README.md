# SteamVibe - Video Game Analytics & DSA Benchmarking Suite

**SteamVibe** is a high-performance desktop application built with **PyQt6** and Python for PC video game catalog analytics, HTML DOM scraping, and Data Structures & Algorithms (DSA) empirical benchmarking.

---

## 🌟 Key Features

1. **Pure HTML DOM Scraping Engine (`scraper/worker.py`)**:
   - Targets live Steam catalog pagination: `https://store.steampowered.com/search/?page=1`
   - Parses pure HTML DOM tags via `requests` and `BeautifulSoup` (`bs4`) with custom `User-Agent` headers.
   - **No REST APIs, Steam Web APIs, or JSON feeds used**.
   - Extracts 8 attributes per entity:
     - `app_id` (String: parsed from `data-ds-appid`)
     - `game_title` (String: parsed from `<span class="title">`)
     - `release_date` (String: parsed from `<div class="search_released">`)
     - `original_price` (Float: parsed from strike/regular price tag)
     - `final_price` (Float: parsed from `<div class="discount_final_price">`)
     - `discount_percent` (Integer: parsed from `<div class="discount_pct">`)
     - `review_score` (Integer: parsed from `<span class="search_review_summary">` tooltip percentage)
     - `is_free` (Boolean: True if $0.00 / Free to Play)
   - Background `QThread` with **Pause**, **Resume**, and **Stop** controls using `QMutex` and `QWaitCondition`.
   - **Local Persistence**: Automatically caches records to `steam_games_cache.csv`. On startup, instantly reloads the catalog so sorting and searching work with zero delay.
   - **Catalog Pre-seeder**: Supports instant generation of 15,000+ realistic PC game entities for immediate offline evaluation and benchmarking.

2. **Instrumented Algorithms Engine (`algorithms/sorting.py`)**:
   - Implements **8 sorting algorithms strictly from scratch** (NO `sort()`, `sorted()`, `min()`, `max()`):
     1. **Bubble Sort** (Stable, $O(n^2)$)
     2. **Selection Sort** (Unstable, $O(n^2)$)
     3. **Insertion Sort** (Stable, $O(n^2)$)
     4. **Merge Sort** (Stable, $O(n \log n)$)
     5. **Quick Sort** (Unstable, $O(n \log n)$ - 3-Way Dutch National Flag Partition with explicit stack to eliminate recursion overhead and handle duplicate keys)
     6. **Heap Sort** (Unstable, $O(n \log n)$ - custom in-place max heapify)
     7. **Shell Sort** (Unstable, $O(n^{4/3})$ - Knuth gap sequence)
     8. **Radix Sort** (Stable, $O(d \cdot (n + k))$ - LSD Counting Sort for numeric & string keys)
   - **Instrumented Metrics**:
     - Execution time in milliseconds (`time.perf_counter()`)
     - Total element comparisons
     - Total element swaps/shifts
     - Big-O complexity label
     - Stability classification
   - **Multi-Level Sorting**: Supports multi-column hierarchical sorting (e.g., Primary: `final_price` ASC, Secondary: `review_score` DESC).

3. **Searching & Filtering Engine (`algorithms/searching.py`)**:
   - Single-column linear search with operators: `contains`, `starts_with`, `ends_with`, `exact`, `>`, `<`, `>=`, `<=`, `=`.
   - Composite boolean search supporting **`AND`**, **`OR`**, and **`NOT`** logic across multiple columns.
   - Tracks comparison counts and execution time.

4. **PyQt6 Desktop GUI (`ui/main_window.py`)**:
   - **Virtualized `QTableView`** backed by a custom `QAbstractTableModel` for smooth 60 FPS scrolling through 15,000+ records.
   - Top Scraper Bar with URL input (Bonus), Start, Pause, Resume, Stop, and Progress Bar.
   - Search Bar with column selector, operator dropdown, and Composite Search modal.
   - Sorting Bar with column selector, algorithm selector, descending toggle, and scope filter.
   - Real-time **Status Bar** and **Metrics Banner** displaying performance metrics after operations.
   - **Benchmark Modal Dialog**: Compares all 8 sorting algorithms on identical copies of a dataset slice, ranks them by speed, and highlights the fastest algorithm.

---

## 📁 Project Directory Architecture

```
DSA_project/
│
├── algorithms/
│   ├── __init__.py
│   ├── searching.py       # Single-column & composite boolean search engine
│   └── sorting.py         # 8 custom sorting algorithms instrumented with metrics
│
├── scraper/
│   ├── __init__.py
│   └── worker.py          # QThread worker with Start/Pause/Resume/Stop & CSV caching
│
├── ui/
│   ├── __init__.py
│   └── main_window.py     # PyQt6 QTableView, controls, metrics panel, modals
│
├── requirements.txt       # Dependencies: PyQt6, requests, beautifulsoup4
├── main.py                # Main entry point to launch the application
├── test_suite.py          # Automated verification test suite
└── steam_games_cache.csv  # 15,000+ game dataset cache
```

---

## 🚀 Getting Started

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Run the Application
From the project root:
```bash
python main.py
```

### 3. Run Automated Tests
```bash
python test_suite.py
```
