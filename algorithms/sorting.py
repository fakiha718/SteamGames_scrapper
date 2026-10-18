"""
SteamVibe Sorting Algorithms Engine
Implements 8 sorting algorithms from scratch without built-in sort/sorted/min/max.
Instrumented with execution time (ms), comparison count, and swap/shift count.
"""

import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple, Union


@dataclass
class SortResult:
    """Dataclass encapsulating sorted results and instrumentation metrics."""
    sorted_data: List[Any]
    elapsed_ms: float
    comparisons: int
    swaps: int
    complexity: str
    stability: str
    algorithm_name: str

    def summary(self) -> str:
        return (
            f"[{self.algorithm_name}] Time: {self.elapsed_ms:.2f} ms | "
            f"Comparisons: {self.comparisons:,} | Swaps/Shifts: {self.swaps:,} | "
            f"Complexity: {self.complexity} | Stability: {self.stability}"
        )


class MetricsCounter:
    """Helper class to track comparisons and swaps across algorithm operations."""
    __slots__ = ("comparisons", "swaps")

    def __init__(self) -> None:
        self.comparisons = 0
        self.swaps = 0


# Default key extractor
def _default_key(item: Any) -> Any:
    return item


def _extract_comparable_value(raw: Any) -> Tuple[int, Any]:
    """
    Safely extract a comparable value without raising TypeError on mixed types (e.g. None).
    Returns (type_priority, value) so None always sorts consistently.
    """
    if raw is None:
        return (0, "")
    if isinstance(raw, (int, float)):
        return (1, float(raw))
    if isinstance(raw, bool):
        return (1, 1.0 if raw else 0.0)
    return (2, str(raw).lower())


def _compare_keys(val_a: Any, val_b: Any, metrics: MetricsCounter, descending: bool = False) -> int:
    """
    Compare two values using custom logic without built-ins.
    Returns:
       1 if val_a > val_b (or val_a < val_b if descending)
      -1 if val_a < val_b (or val_a > val_b if descending)
       0 if val_a == val_b
    Increments metrics.comparisons.
    """
    metrics.comparisons += 1
    norm_a = _extract_comparable_value(val_a)
    norm_b = _extract_comparable_value(val_b)

    # Compare priority tuple
    if norm_a[0] != norm_b[0]:
        diff = 1 if norm_a[0] > norm_b[0] else -1
        return -diff if descending else diff

    if norm_a[1] == norm_b[1]:
        return 0
    if norm_a[1] > norm_b[1]:
        return -1 if descending else 1
    return 1 if descending else -1


# ==============================================================================
# 1. BUBBLE SORT (Stable, O(n^2))
# ==============================================================================
def bubble_sort(
    data: List[Any],
    key: Callable[[Any], Any] = _default_key,
    descending: bool = False
) -> SortResult:
    """
    Bubble Sort: Compares adjacent elements and swaps them if in wrong order.
    Stability: Stable (only swaps on strictly greater).
    """
    metrics = MetricsCounter()
    start_time = time.perf_counter()

    arr = list(data)
    n = len(arr)

    for i in range(n):
        swapped = False
        # Last i elements are already in place
        for j in range(0, n - i - 1):
            key_j = key(arr[j])
            key_next = key(arr[j + 1])
            if _compare_keys(key_j, key_next, metrics, descending) > 0:
                # Swap adjacent elements
                arr[j], arr[j + 1] = arr[j + 1], arr[j]
                metrics.swaps += 1
                swapped = True
        if not swapped:
            break

    elapsed_ms = (time.perf_counter() - start_time) * 1000.0
    return SortResult(
        sorted_data=arr,
        elapsed_ms=elapsed_ms,
        comparisons=metrics.comparisons,
        swaps=metrics.swaps,
        complexity="O(n²)",
        stability="Stable",
        algorithm_name="Bubble Sort"
    )


# ==============================================================================
# 2. SELECTION SORT (Unstable, O(n^2))
# ==============================================================================
def selection_sort(
    data: List[Any],
    key: Callable[[Any], Any] = _default_key,
    descending: bool = False
) -> SortResult:
    """
    Selection Sort: Repeatedly finds the minimum element and moves it to the front.
    Stability: Unstable (distant swaps can reorder equal elements).
    """
    metrics = MetricsCounter()
    start_time = time.perf_counter()

    arr = list(data)
    n = len(arr)

    for i in range(n):
        target_idx = i
        target_key = key(arr[target_idx])

        for j in range(i + 1, n):
            current_key = key(arr[j])
            # Looking for element smaller (or larger if descending) than target
            if _compare_keys(target_key, current_key, metrics, descending) > 0:
                target_idx = j
                target_key = current_key

        if target_idx != i:
            arr[i], arr[target_idx] = arr[target_idx], arr[i]
            metrics.swaps += 1

    elapsed_ms = (time.perf_counter() - start_time) * 1000.0
    return SortResult(
        sorted_data=arr,
        elapsed_ms=elapsed_ms,
        comparisons=metrics.comparisons,
        swaps=metrics.swaps,
        complexity="O(n²)",
        stability="Unstable",
        algorithm_name="Selection Sort"
    )


# ==============================================================================
# 3. INSERTION SORT (Stable, O(n^2))
# ==============================================================================
def insertion_sort(
    data: List[Any],
    key: Callable[[Any], Any] = _default_key,
    descending: bool = False
) -> SortResult:
    """
    Insertion Sort: Builds sorted array one element at a time by shifting.
    Stability: Stable (does not shift over equal elements).
    """
    metrics = MetricsCounter()
    start_time = time.perf_counter()

    arr = list(data)
    n = len(arr)

    for i in range(1, n):
        current_item = arr[i]
        current_key = key(current_item)
        j = i - 1

        while j >= 0:
            key_j = key(arr[j])
            if _compare_keys(key_j, current_key, metrics, descending) > 0:
                arr[j + 1] = arr[j]
                metrics.swaps += 1  # Element shift counted as a move
                j -= 1
            else:
                break
        arr[j + 1] = current_item

    elapsed_ms = (time.perf_counter() - start_time) * 1000.0
    return SortResult(
        sorted_data=arr,
        elapsed_ms=elapsed_ms,
        comparisons=metrics.comparisons,
        swaps=metrics.swaps,
        complexity="O(n²)",
        stability="Stable",
        algorithm_name="Insertion Sort"
    )


# ==============================================================================
# 4. MERGE SORT (Stable, O(n log n))
# ==============================================================================
def merge_sort(
    data: List[Any],
    key: Callable[[Any], Any] = _default_key,
    descending: bool = False
) -> SortResult:
    """
    Merge Sort: Divide and conquer algorithm using scratch merge buffer.
    Stability: Stable (favors left subarray on equal comparison).
    """
    metrics = MetricsCounter()
    start_time = time.perf_counter()

    arr = list(data)
    n = len(arr)

    def _merge_step(left: List[Any], right: List[Any]) -> List[Any]:
        merged = []
        i = 0
        j = 0
        len_left = len(left)
        len_right = len(right)

        while i < len_left and j < len_right:
            key_left = key(left[i])
            key_right = key(right[j])
            # If left <= right, keep left for stability
            cmp = _compare_keys(key_left, key_right, metrics, descending)
            if cmp <= 0:
                merged.append(left[i])
                i += 1
            else:
                merged.append(right[j])
                j += 1
            metrics.swaps += 1

        while i < len_left:
            merged.append(left[i])
            metrics.swaps += 1
            i += 1

        while j < len_right:
            merged.append(right[j])
            metrics.swaps += 1
            j += 1

        return merged

    def _sort_recursive(sub: List[Any]) -> List[Any]:
        if len(sub) <= 1:
            return sub
        mid = len(sub) // 2
        left_sorted = _sort_recursive(sub[:mid])
        right_sorted = _sort_recursive(sub[mid:])
        return _merge_step(left_sorted, right_sorted)

    sorted_arr = _sort_recursive(arr)
    elapsed_ms = (time.perf_counter() - start_time) * 1000.0

    return SortResult(
        sorted_data=sorted_arr,
        elapsed_ms=elapsed_ms,
        comparisons=metrics.comparisons,
        swaps=metrics.swaps,
        complexity="O(n log n)",
        stability="Stable",
        algorithm_name="Merge Sort"
    )


# ==============================================================================
# 5. QUICK SORT (Unstable, O(n log n))
# ==============================================================================
def quick_sort(
    data: List[Any],
    key: Callable[[Any], Any] = _default_key,
    descending: bool = False
) -> SortResult:
    """
    Quick Sort: In-place iterative implementation using an explicit stack
    to prevent RecursionError on 15,000+ element datasets. Median-of-three pivot.
    Stability: Unstable.
    """
    metrics = MetricsCounter()
    start_time = time.perf_counter()

    arr = list(data)
    n = len(arr)

    if n > 1:
        # Stack storing (low, high) index tuples
        stack: List[Tuple[int, int]] = [(0, n - 1)]

        while stack:
            low, high = stack.pop()
            if low >= high:
                continue

            # Pick middle element as pivot
            mid = low + (high - low) // 2
            pivot_val = key(arr[mid])

            # 3-way Dutch National Flag partition:
            # Elements < pivot moved to [low .. lt-1]
            # Elements == pivot stay in [lt .. gt]
            # Elements > pivot moved to [gt+1 .. high]
            lt = low
            gt = high
            i = low

            while i <= gt:
                cmp = _compare_keys(key(arr[i]), pivot_val, metrics, descending)
                if cmp < 0:
                    if lt != i:
                        arr[lt], arr[i] = arr[i], arr[lt]
                        metrics.swaps += 1
                    lt += 1
                    i += 1
                elif cmp > 0:
                    if i != gt:
                        arr[i], arr[gt] = arr[gt], arr[i]
                        metrics.swaps += 1
                    gt -= 1
                else:
                    i += 1

            if lt - 1 > low:
                stack.append((low, lt - 1))
            if gt + 1 < high:
                stack.append((gt + 1, high))

    elapsed_ms = (time.perf_counter() - start_time) * 1000.0
    return SortResult(
        sorted_data=arr,
        elapsed_ms=elapsed_ms,
        comparisons=metrics.comparisons,
        swaps=metrics.swaps,
        complexity="O(n log n)",
        stability="Unstable",
        algorithm_name="Quick Sort"
    )


# ==============================================================================
# 6. HEAP SORT (Unstable, O(n log n))
# ==============================================================================
def heap_sort(
    data: List[Any],
    key: Callable[[Any], Any] = _default_key,
    descending: bool = False
) -> SortResult:
    """
    Heap Sort: Builds a heap from scratch and extracts root in-place.
    Stability: Unstable.
    """
    metrics = MetricsCounter()
    start_time = time.perf_counter()

    arr = list(data)
    n = len(arr)

    def _sift_down(heap_size: int, root: int) -> None:
        largest = root
        while True:
            left = 2 * root + 1
            right = 2 * root + 2

            if left < heap_size:
                if _compare_keys(key(arr[left]), key(arr[largest]), metrics, descending) > 0:
                    largest = left

            if right < heap_size:
                if _compare_keys(key(arr[right]), key(arr[largest]), metrics, descending) > 0:
                    largest = right

            if largest != root:
                arr[root], arr[largest] = arr[largest], arr[root]
                metrics.swaps += 1
                root = largest
            else:
                break

    # Build max-heap (or min-heap if descending)
    for i in range(n // 2 - 1, -1, -1):
        _sift_down(n, i)

    # Extract elements one by one from heap
    for i in range(n - 1, 0, -1):
        arr[0], arr[i] = arr[i], arr[0]
        metrics.swaps += 1
        _sift_down(i, 0)

    elapsed_ms = (time.perf_counter() - start_time) * 1000.0
    return SortResult(
        sorted_data=arr,
        elapsed_ms=elapsed_ms,
        comparisons=metrics.comparisons,
        swaps=metrics.swaps,
        complexity="O(n log n)",
        stability="Unstable",
        algorithm_name="Heap Sort"
    )


# ==============================================================================
# 7. SHELL SORT (Unstable, O(n^(4/3)) / O(n log^2 n))
# ==============================================================================
def shell_sort(
    data: List[Any],
    key: Callable[[Any], Any] = _default_key,
    descending: bool = False
) -> SortResult:
    """
    Shell Sort: Diminishing increment sort using Knuth's gap sequence (3^k - 1) // 2.
    Stability: Unstable.
    """
    metrics = MetricsCounter()
    start_time = time.perf_counter()

    arr = list(data)
    n = len(arr)

    if n > 1:
        # Compute Knuth's gap sequence: 1, 4, 13, 40, 121, 364...
        h = 1
        while h < n // 3:
            h = 3 * h + 1

        while h >= 1:
            for i in range(h, n):
                temp = arr[i]
                temp_key = key(temp)
                j = i
                while j >= h:
                    key_prev = key(arr[j - h])
                    if _compare_keys(key_prev, temp_key, metrics, descending) > 0:
                        arr[j] = arr[j - h]
                        metrics.swaps += 1
                        j -= h
                    else:
                        break
                arr[j] = temp
            h //= 3

    elapsed_ms = (time.perf_counter() - start_time) * 1000.0
    return SortResult(
        sorted_data=arr,
        elapsed_ms=elapsed_ms,
        comparisons=metrics.comparisons,
        swaps=metrics.swaps,
        complexity="O(n^(4/3))",
        stability="Unstable",
        algorithm_name="Shell Sort"
    )


# ==============================================================================
# 8. RADIX SORT (Stable, O(d * (n + k)))
# ==============================================================================
def radix_sort(
    data: List[Any],
    key: Callable[[Any], Any] = _default_key,
    descending: bool = False
) -> SortResult:
    """
    Radix Sort (LSD): Non-comparative sorting algorithm.
    Optimized for numeric columns (integers and fixed-point floats).
    For string columns, automatically performs LSD Radix Sort over character ordinals.
    Stability: Stable.
    """
    metrics = MetricsCounter()
    start_time = time.perf_counter()

    arr = list(data)
    n = len(arr)

    if n <= 1:
        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        return SortResult(
            sorted_data=arr,
            elapsed_ms=elapsed_ms,
            comparisons=0,
            swaps=0,
            complexity="O(d·(n + k))",
            stability="Stable",
            algorithm_name="Radix Sort"
        )

    # Check data type of extracted keys
    sample_key = key(arr[0])
    is_numeric = isinstance(sample_key, (int, float, bool))

    if is_numeric:
        # Scale floats to integers (e.g. cents)
        int_keys = []
        for item in arr:
            raw_val = key(item)
            if raw_val is None:
                val = 0
            elif isinstance(raw_val, bool):
                val = 1 if raw_val else 0
            elif isinstance(raw_val, float):
                val = int(round(raw_val * 100))
            else:
                try:
                    val = int(raw_val)
                except (ValueError, TypeError):
                    val = 0
            int_keys.append(val)

        # Custom min and max loops without built-ins
        min_val = int_keys[0]
        max_val = int_keys[0]
        for val in int_keys:
            metrics.comparisons += 2
            if val < min_val:
                min_val = val
            if val > max_val:
                max_val = val

        # Shift all numbers to non-negative domain
        offset = -min_val if min_val < 0 else 0
        range_val = max_val + offset

        paired = [(int_keys[i] + offset, arr[i]) for i in range(n)]

        # LSD Counting sort pass for each decimal digit
        exp = 1
        while range_val // exp > 0:
            count = [0] * 10
            output = [None] * n

            # Count occurrences of current digit
            for num, _ in paired:
                digit = (num // exp) % 10
                count[digit] += 1

            # Accumulate prefix counts
            for i in range(1, 10):
                count[i] += count[i - 1]

            # Place elements into output in reverse order to maintain stability
            for i in range(n - 1, -1, -1):
                digit = (paired[i][0] // exp) % 10
                count[digit] -= 1
                output[count[digit]] = paired[i]
                metrics.swaps += 1

            paired = output
            exp *= 10

        sorted_arr = [pair[1] for pair in paired]

    else:
        # String LSD Radix Sort
        str_keys = []
        max_len = 0
        for item in arr:
            raw_val = key(item)
            s = str(raw_val).lower() if raw_val is not None else ""
            str_keys.append(s)
            s_len = len(s)
            metrics.comparisons += 1
            if s_len > max_len:
                max_len = s_len

        paired = [(str_keys[i], arr[i]) for i in range(n)]

        # Pad and sort from rightmost character to leftmost character
        for pos in range(max_len - 1, -1, -1):
            count = [0] * 257  # 0 for padded null, 1..256 for ASCII/byte ordinals
            output = [None] * n

            for s, _ in paired:
                ch = ord(s[pos]) + 1 if pos < len(s) and ord(s[pos]) < 256 else 0
                count[ch] += 1

            for i in range(1, 257):
                count[i] += count[i - 1]

            for i in range(n - 1, -1, -1):
                s = paired[i][0]
                ch = ord(s[pos]) + 1 if pos < len(s) and ord(s[pos]) < 256 else 0
                count[ch] -= 1
                output[count[ch]] = paired[i]
                metrics.swaps += 1

            paired = output

        sorted_arr = [pair[1] for pair in paired]

    # Handle descending order in-place without built-ins
    if descending:
        left = 0
        right = n - 1
        while left < right:
            sorted_arr[left], sorted_arr[right] = sorted_arr[right], sorted_arr[left]
            metrics.swaps += 1
            left += 1
            right -= 1

    elapsed_ms = (time.perf_counter() - start_time) * 1000.0
    return SortResult(
        sorted_data=sorted_arr,
        elapsed_ms=elapsed_ms,
        comparisons=metrics.comparisons,
        swaps=metrics.swaps,
        complexity="O(d·(n + k))",
        stability="Stable",
        algorithm_name="Radix Sort"
    )


# ==============================================================================
# MULTI-COLUMN SORTING ENGINE
# ==============================================================================
def multi_column_sort(
    data: List[Dict[str, Any]],
    specs: List[Tuple[str, bool]],
    algorithm_name: str = "Merge Sort"
) -> SortResult:
    """
    Multi-Column Sorting:
    Accepts specs as [(column_name, descending_bool), ...].
    Example: [('final_price', False), ('review_score', True)]

    Uses a composite comparator that evaluates primary key,
    and falls through to secondary/tertiary keys on equality.
    """
    if not specs:
        return merge_sort(data)

    def composite_key(item: Dict[str, Any]) -> Any:
        return item

    metrics = MetricsCounter()
    start_time = time.perf_counter()
    arr = list(data)
    n = len(arr)

    def _composite_compare(item_a: Dict[str, Any], item_b: Dict[str, Any]) -> int:
        for col, col_descending in specs:
            val_a = item_a.get(col)
            val_b = item_b.get(col)
            cmp = _compare_keys(val_a, val_b, metrics, descending=col_descending)
            if cmp != 0:
                return cmp
        return 0

    # Stable multi-level merge sort with composite comparator
    def _merge(left: List[Any], right: List[Any]) -> List[Any]:
        merged = []
        i, j = 0, 0
        len_l, len_r = len(left), len(right)
        while i < len_l and j < len_r:
            cmp = _composite_compare(left[i], right[j])
            if cmp <= 0:
                merged.append(left[i])
                i += 1
            else:
                merged.append(right[j])
                j += 1
            metrics.swaps += 1
        while i < len_l:
            merged.append(left[i])
            metrics.swaps += 1
            i += 1
        while j < len_r:
            merged.append(right[j])
            metrics.swaps += 1
            j += 1
        return merged

    def _sort(sub: List[Any]) -> List[Any]:
        if len(sub) <= 1:
            return sub
        mid = len(sub) // 2
        return _merge(_sort(sub[:mid]), _sort(sub[mid:]))

    sorted_arr = _sort(arr)
    elapsed_ms = (time.perf_counter() - start_time) * 1000.0

    return SortResult(
        sorted_data=sorted_arr,
        elapsed_ms=elapsed_ms,
        comparisons=metrics.comparisons,
        swaps=metrics.swaps,
        complexity="O(n log n)",
        stability="Stable",
        algorithm_name=f"Multi-Level Sort ({algorithm_name})"
    )


# Registry of all 8 sorting algorithms
SORT_ALGORITHMS: Dict[str, Callable[..., SortResult]] = {
    "Bubble Sort": bubble_sort,
    "Selection Sort": selection_sort,
    "Insertion Sort": insertion_sort,
    "Merge Sort": merge_sort,
    "Quick Sort": quick_sort,
    "Heap Sort": heap_sort,
    "Shell Sort": shell_sort,
    "Radix Sort": radix_sort,
}

ALGORITHM_METADATA = {
    "Bubble Sort": {"complexity": "O(n²)", "stability": "Stable", "best": "O(n)", "worst": "O(n²)"},
    "Selection Sort": {"complexity": "O(n²)", "stability": "Unstable", "best": "O(n²)", "worst": "O(n²)"},
    "Insertion Sort": {"complexity": "O(n²)", "stability": "Stable", "best": "O(n)", "worst": "O(n²)"},
    "Merge Sort": {"complexity": "O(n log n)", "stability": "Stable", "best": "O(n log n)", "worst": "O(n log n)"},
    "Quick Sort": {"complexity": "O(n log n)", "stability": "Unstable", "best": "O(n log n)", "worst": "O(n²)"},
    "Heap Sort": {"complexity": "O(n log n)", "stability": "Unstable", "best": "O(n log n)", "worst": "O(n log n)"},
    "Shell Sort": {"complexity": "O(n^(4/3))", "stability": "Unstable", "best": "O(n log n)", "worst": "O(n²)"},
    "Radix Sort": {"complexity": "O(d·(n + k))", "stability": "Stable", "best": "O(d·n)", "worst": "O(d·n)"},
}
