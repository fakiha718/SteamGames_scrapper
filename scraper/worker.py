"""
SteamVibe Scraper Worker Engine
Implements QThread HTML DOM Scraper using requests and BeautifulSoup (bs4).
Supports Pause, Resume, Stop controls via QMutex and QWaitCondition.
Handles CSV persistence and local caching for store.steampowered.com.
"""

import csv
import os
import re
import time
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import bs4
import requests
from PyQt6.QtCore import QMutex, QMutexLocker, QThread, QWaitCondition, pyqtSignal

DEFAULT_CACHE_FILE = "steam_games_cache.csv"
DEFAULT_TARGET_COUNT = 15000
DEFAULT_START_URL = "https://store.steampowered.com/search/?page=1"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
}


def build_page_url(base_url: str, page_number: int) -> str:
    """Safely updates or injects the 'page' query parameter into a Steam search URL."""
    parsed = urlparse(base_url)
    query_params = parse_qs(parsed.query)
    query_params["page"] = [str(page_number)]
    # Set default language filter to english if not present
    if "category1" not in query_params and "supportedlang" not in query_params:
        query_params["supportedlang"] = ["english"]
    new_query = urlencode(query_params, doseq=True)
    return urlunparse((parsed.scheme or "https", parsed.netloc or "store.steampowered.com", parsed.path or "/search/", parsed.params, new_query, parsed.fragment))


def parse_game_row(row: bs4.element.Tag) -> Optional[Dict[str, Any]]:
    """
    Parses exactly 8 attributes from a Steam search result row DOM:
    1. app_id (String)
    2. game_title (String)
    3. release_date (String)
    4. original_price (Float)
    5. final_price (Float)
    6. discount_percent (Integer)
    7. review_score (Integer)
    8. is_free (Boolean)
    """
    try:
        # 1. app_id
        raw_appid = row.get("data-ds-appid", "")
        if not raw_appid:
            return None
        app_id = str(raw_appid).split(",")[0].strip()

        # 2. game_title
        title_tag = row.select_one(".title")
        game_title = title_tag.text.strip() if title_tag else f"Steam App {app_id}"

        # 3. release_date
        rel_tag = row.select_one(".search_released")
        release_date = rel_tag.text.strip() if rel_tag else "Unknown"

        # 4 & 5. Prices
        orig_tag = row.select_one(".discount_original_price")
        final_tag = row.select_one(".discount_final_price") or row.select_one(".search_price")

        final_text = final_tag.text.strip() if final_tag else ""
        is_free = (
            "free" in final_text.lower()
            or "free to play" in final_text.lower()
            or "demo" in final_text.lower()
        )

        original_price = 0.0
        final_price = 0.0

        if orig_tag and orig_tag.text.strip():
            m_orig = re.search(r"(\d+[\.,]\d+|\d+)", orig_tag.text.replace(",", "."))
            if m_orig:
                try:
                    original_price = float(m_orig.group(1))
                except ValueError:
                    original_price = 0.0

        if final_tag and final_text and not is_free:
            m_final = re.search(r"(\d+[\.,]\d+|\d+)", final_text.replace(",", "."))
            if m_final:
                try:
                    final_price = float(m_final.group(1))
                except ValueError:
                    final_price = 0.0

        if original_price == 0.0 and final_price > 0.0:
            original_price = final_price

        # 6. discount_percent
        discount_tag = row.select_one(".discount_pct")
        discount_percent = 0
        if discount_tag and discount_tag.text.strip():
            m_disc = re.search(r"\d+", discount_tag.text)
            if m_disc:
                try:
                    discount_percent = int(m_disc.group())
                except ValueError:
                    discount_percent = 0

        # 7. review_score
        review_tag = row.select_one(".search_review_summary")
        review_score = 50
        if review_tag:
            tooltip = review_tag.get("data-tooltip-html", "")
            m_rev = re.search(r"(\d+)%", tooltip)
            if m_rev:
                try:
                    review_score = int(m_rev.group(1))
                except ValueError:
                    review_score = 50
            else:
                score_class = " ".join(review_tag.get("class", []))
                if "positive" in score_class:
                    review_score = 80
                elif "negative" in score_class:
                    review_score = 30
                elif "mixed" in score_class:
                    review_score = 50

        # 8. is_free
        if final_price == 0.0:
            is_free = True

        return {
            "app_id": app_id,
            "game_title": game_title,
            "release_date": release_date,
            "original_price": round(original_price, 2),
            "final_price": round(final_price, 2),
            "discount_percent": int(discount_percent),
            "review_score": int(review_score),
            "is_free": bool(is_free),
        }
    except Exception:
        return None


class SteamScraperWorker(QThread):
    """
    QThread worker for continuous, asynchronous Steam catalog HTML DOM scraping.
    Provides pause, resume, and stop controls via QMutex and QWaitCondition.
    """
    progress_updated = pyqtSignal(int, int)        # current_count, target_count
    entity_scraped = pyqtSignal(dict)              # newly scraped entity dict
    batch_scraped = pyqtSignal(list)               # batch of entities from page
    status_message = pyqtSignal(str)               # status text
    finished_signal = pyqtSignal(list)             # complete list of entities
    error_occurred = pyqtSignal(str)               # error string

    def __init__(
        self,
        start_url: str = DEFAULT_START_URL,
        target_count: int = DEFAULT_TARGET_COUNT,
        cache_filepath: str = DEFAULT_CACHE_FILE,
        parent: Optional[Any] = None,
        initial_data: Optional[List[Dict[str, Any]]] = None,
        start_page: int = 1
    ) -> None:
        super().__init__(parent)
        self.start_url = start_url.strip() if start_url.strip() else DEFAULT_START_URL
        self.target_count = target_count
        self.cache_filepath = cache_filepath

        self.mutex = QMutex()
        self.wait_condition = QWaitCondition()
        self._is_paused = False
        self._is_stopped = False

        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.scraped_data: List[Dict[str, Any]] = list(initial_data) if initial_data else []
        self.seen_app_ids = {x["app_id"] for x in self.scraped_data}
        self.start_page = max(1, start_page)

    def set_start_url(self, url: str) -> None:
        self.start_url = url.strip() if url.strip() else DEFAULT_START_URL

    def set_target_count(self, count: int) -> None:
        self.target_count = max(1, count)

    def pause(self) -> None:
        """Pauses the scraper execution safely without blocking the UI."""
        with QMutexLocker(self.mutex):
            self._is_paused = True
        self.status_message.emit("Scraper paused by user.")

    def resume(self) -> None:
        """Resumes the scraper execution."""
        with QMutexLocker(self.mutex):
            self._is_paused = False
            self.wait_condition.wakeAll()
        self.status_message.emit("Scraper resumed.")

    def stop(self) -> None:
        """Stops the scraper worker and exits the thread gracefully."""
        with QMutexLocker(self.mutex):
            self._is_stopped = True
            self._is_paused = False
            self.wait_condition.wakeAll()
        self.status_message.emit("Stopping scraper...")

    def run(self) -> None:
        """Main scraping loop executed on the worker thread."""
        page_num = self.start_page
        current_count = len(self.scraped_data)
        self.status_message.emit(f"Connecting to Steam catalog via HTML DOM scraping...")
        self.progress_updated.emit(current_count, self.target_count)

        consecutive_failures = 0
        max_consecutive_failures = 5

        while not self._is_stopped and current_count < self.target_count:
            # Check pause state
            self.mutex.lock()
            while self._is_paused and not self._is_stopped:
                self.wait_condition.wait(self.mutex)
            self.mutex.unlock()

            if self._is_stopped:
                break

            target_page_url = build_page_url(self.start_url, page_num)
            self.status_message.emit(f"Scraping page {page_num} ({current_count}/{self.target_count} games)...")

            try:
                response = self.session.get(target_page_url, timeout=12)
                if response.status_code == 429:
                    self.status_message.emit(f"Steam Rate Limit (429) on page {page_num}. Backing off 3 seconds...")
                    time.sleep(3.0)
                    consecutive_failures += 1
                    if consecutive_failures >= max_consecutive_failures:
                        self.status_message.emit("Rate limit reached. Saving current progress...")
                        break
                    continue

                if response.status_code != 200:
                    self.status_message.emit(f"HTTP {response.status_code} on page {page_num}. Retrying...")
                    time.sleep(1.0)
                    consecutive_failures += 1
                    if consecutive_failures >= max_consecutive_failures:
                        break
                    continue

                consecutive_failures = 0
                soup = bs4.BeautifulSoup(response.text, "html.parser")
                rows = soup.select("a.search_result_row")

                if not rows:
                    self.status_message.emit(f"No more search results found at page {page_num}.")
                    break

                page_new_games: List[Dict[str, Any]] = []
                for row in rows:
                    game = parse_game_row(row)
                    if game and game["app_id"] not in self.seen_app_ids:
                        self.seen_app_ids.add(game["app_id"])
                        self.scraped_data.append(game)
                        page_new_games.append(game)
                        current_count += 1
                        self.entity_scraped.emit(game)
                        self.progress_updated.emit(current_count, self.target_count)

                        if current_count >= self.target_count:
                            break

                if page_new_games:
                    self.batch_scraped.emit(page_new_games)
                    # Periodic auto-cache save every page to preserve data
                    save_cache_to_csv(self.scraped_data, self.cache_filepath)

                page_num += 1

                # Polite scraping delay to avoid aggressive IP throttling
                time.sleep(0.35)

            except requests.RequestException as exc:
                self.error_occurred.emit(f"Network error on page {page_num}: {exc}")
                time.sleep(1.5)
                consecutive_failures += 1
                if consecutive_failures >= max_consecutive_failures:
                    break
            except Exception as exc:
                self.error_occurred.emit(f"Scraping error: {exc}")
                break

        # Save final state to local cache
        save_cache_to_csv(self.scraped_data, self.cache_filepath)
        self.status_message.emit(f"Scraping completed. Total items: {len(self.scraped_data):,}")
        self.finished_signal.emit(self.scraped_data)


# ==============================================================================
# CSV CACHING & LOCAL PERSISTENCE
# ==============================================================================
CSV_FIELDNAMES = [
    "app_id",
    "game_title",
    "release_date",
    "original_price",
    "final_price",
    "discount_percent",
    "review_score",
    "is_free"
]


def save_cache_to_csv(data: List[Dict[str, Any]], filepath: str = DEFAULT_CACHE_FILE) -> bool:
    """Saves records to CSV cache file."""
    if not data:
        return False
    try:
        with open(filepath, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES)
            writer.writeheader()
            for item in data:
                writer.writerow({
                    "app_id": item.get("app_id", ""),
                    "game_title": item.get("game_title", ""),
                    "release_date": item.get("release_date", ""),
                    "original_price": item.get("original_price", 0.0),
                    "final_price": item.get("final_price", 0.0),
                    "discount_percent": item.get("discount_percent", 0),
                    "review_score": item.get("review_score", 50),
                    "is_free": "True" if item.get("is_free") else "False",
                })
        return True
    except Exception as exc:
        print(f"Error saving CSV cache to {filepath}: {exc}")
        return False


def load_cache_from_csv(filepath: str = DEFAULT_CACHE_FILE) -> List[Dict[str, Any]]:
    """Loads and type-casts records from CSV cache file."""
    if not os.path.exists(filepath):
        return []
    records: List[Dict[str, Any]] = []
    try:
        with open(filepath, mode="r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    orig_p = float(row.get("original_price", 0.0))
                except (ValueError, TypeError):
                    orig_p = 0.0

                try:
                    final_p = float(row.get("final_price", 0.0))
                except (ValueError, TypeError):
                    final_p = 0.0

                try:
                    disc = int(float(row.get("discount_percent", 0)))
                except (ValueError, TypeError):
                    disc = 0

                try:
                    rev = int(float(row.get("review_score", 50)))
                except (ValueError, TypeError):
                    rev = 50

                is_free_val = str(row.get("is_free", "")).lower() in ("true", "1", "yes")

                records.append({
                    "app_id": str(row.get("app_id", "")).strip(),
                    "game_title": str(row.get("game_title", "")).strip(),
                    "release_date": str(row.get("release_date", "")).strip(),
                    "original_price": round(orig_p, 2),
                    "final_price": round(final_p, 2),
                    "discount_percent": disc,
                    "review_score": rev,
                    "is_free": is_free_val,
                })
    except Exception as exc:
        print(f"Error loading CSV cache from {filepath}: {exc}")
    return records
