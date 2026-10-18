"""
SteamVibe Searching & Filtering Engine
Supports single-column operator matching and multi-column composite boolean searches (AND, OR, NOT).
Tracks exact execution time (ms) and comparison counts.
"""

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Union


@dataclass
class SearchResult:
    """Encapsulates searching results and performance metrics."""
    matched_data: List[Dict[str, Any]]
    total_matches: int
    comparisons: int
    elapsed_ms: float
    query_summary: str

    def summary(self) -> str:
        return (
            f"[Search: {self.query_summary}] Matches: {self.total_matches:,} | "
            f"Comparisons: {self.comparisons:,} | Time: {self.elapsed_ms:.2f} ms"
        )


@dataclass
class CompositeFilterRule:
    """Individual filter rule used in composite boolean queries."""
    column: str
    operator: str  # 'contains', 'starts_with', 'ends_with', 'exact', '>', '<', '>=', '<=', '='
    value: str
    negate: bool = False  # If True, acts as NOT rule


def _normalize_search_value(val: Any) -> str:
    if val is None:
        return ""
    if isinstance(val, bool):
        return "true" if val else "false"
    return str(val).strip().lower()


def _evaluate_single_criterion(
    cell_value: Any,
    operator: str,
    target_value: str,
    counter: List[int]
) -> bool:
    """
    Evaluates whether cell_value satisfies operator and target_value.
    counter[0] is incremented for each comparison made.
    """
    counter[0] += 1
    cell_str = _normalize_search_value(cell_value)
    target_str = target_value.strip().lower()
    op = operator.lower().strip()

    # Numeric operators check
    if op in (">", "<", ">=", "<=", "="):
        try:
            num_cell = float(cell_value) if cell_value is not None else 0.0
            num_target = float(target_value)
            if op == ">":
                return num_cell > num_target
            if op == "<":
                return num_cell < num_target
            if op == ">=":
                return num_cell >= num_target
            if op == "<=":
                return num_cell <= num_target
            if op == "=":
                return num_cell == num_target
        except (ValueError, TypeError):
            # Fall back to string comparison
            pass

    if op == "contains":
        return target_str in cell_str
    if op in ("starts_with", "startswith"):
        return cell_str.startswith(target_str)
    if op in ("ends_with", "endswith"):
        return cell_str.endswith(target_str)
    if op in ("exact", "equals", "=="):
        return cell_str == target_str
    if op in ("!=", "not_equal"):
        return cell_str != target_str

    # Default fallback to substring contains
    return target_str in cell_str


def linear_search(
    data: List[Dict[str, Any]],
    column: str,
    operator: str,
    query_value: str
) -> SearchResult:
    """
    Performs a linear search over a specific column using the designated operator.
    Instruments execution time (ms) and total comparison counts.
    """
    start_time = time.perf_counter()
    counter = [0]
    matched: List[Dict[str, Any]] = []

    for item in data:
        cell_val = item.get(column)
        if _evaluate_single_criterion(cell_val, operator, query_value, counter):
            matched.append(item)

    elapsed_ms = (time.perf_counter() - start_time) * 1000.0
    return SearchResult(
        matched_data=matched,
        total_matches=len(matched),
        comparisons=counter[0],
        elapsed_ms=elapsed_ms,
        query_summary=f"{column} {operator} '{query_value}'"
    )


def composite_search(
    data: List[Dict[str, Any]],
    rules: List[CompositeFilterRule],
    logic: str = "AND"
) -> SearchResult:
    """
    Composite search engine supporting boolean logic ('AND' or 'OR')
    across multiple column rules, with individual NOT negation support.
    """
    start_time = time.perf_counter()
    counter = [0]
    matched: List[Dict[str, Any]] = []
    is_and = logic.upper().strip() == "AND"

    summary_parts = []
    for r in rules:
        not_prefix = "NOT " if r.negate else ""
        summary_parts.append(f"({not_prefix}{r.column} {r.operator} '{r.value}')")
    query_summary = f" {logic.upper()} ".join(summary_parts) if summary_parts else "All records"

    if not rules:
        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        return SearchResult(
            matched_data=list(data),
            total_matches=len(data),
            comparisons=0,
            elapsed_ms=elapsed_ms,
            query_summary="No rules specified"
        )

    for item in data:
        if is_and:
            # For AND: all rules must evaluate to True
            match_item = True
            for rule in rules:
                cell_val = item.get(rule.column)
                res = _evaluate_single_criterion(cell_val, rule.operator, rule.value, counter)
                if rule.negate:
                    res = not res
                if not res:
                    match_item = False
                    break
            if match_item:
                matched.append(item)
        else:
            # For OR: any rule evaluating to True matches
            match_item = False
            for rule in rules:
                cell_val = item.get(rule.column)
                res = _evaluate_single_criterion(cell_val, rule.operator, rule.value, counter)
                if rule.negate:
                    res = not res
                if res:
                    match_item = True
                    break
            if match_item:
                matched.append(item)

    elapsed_ms = (time.perf_counter() - start_time) * 1000.0
    return SearchResult(
        matched_data=matched,
        total_matches=len(matched),
        comparisons=counter[0],
        elapsed_ms=elapsed_ms,
        query_summary=query_summary
    )
