"""
visualisation_engine.py
=======================
Computes chart-ready visualisation data from a stored comparison_result dict.

No external API calls are made — all values are derived purely from the
comparison JSON that the comparison_engine already produced.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _parse_dollar(value: Any) -> float:
    """Parse a dollar string such as '$1,200.00' to a float.

    Strips leading '$' and ',' separators before converting.  Returns 0.0 on
    any missing, None, or unparseable input — never raises.
    """
    if value is None:
        return 0.0
    try:
        cleaned = str(value).replace("$", "").replace(",", "").strip()
        return round(float(cleaned), 2)
    except (ValueError, TypeError):
        return 0.0


def _round2(value: float) -> float:
    """Round to 2 decimal places."""
    try:
        return round(float(value), 2)
    except (ValueError, TypeError):
        return 0.0


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_visualisation_data(
    comparison_result: dict,
    policy1_name: str,
    policy2_name: str,
) -> dict:
    """Compute all chart datasets from a comparison_result dict.

    Derives five chart payloads — coverage_bar, coverage_donut,
    exclusions_donut, premium_bar, and similarity_histogram — using only
    the data already present in comparison_result.  Safe .get() calls with
    defaults ensure no crash on partial or missing fields.
    """
    logger.info(
        "Building visualisation data for '%s' vs '%s'",
        policy1_name, policy2_name,
    )

    coverage   = comparison_result.get("coverage")   or {}
    exclusions = comparison_result.get("exclusions") or {}
    premiums   = comparison_result.get("premiums")   or {}
    summary    = comparison_result.get("summary")    or {}

    cov_common    = coverage.get("common", [])   or []
    cov_only_p1   = coverage.get("only_in_policy1", []) or []
    cov_only_p2   = coverage.get("only_in_policy2", []) or []

    exc_common    = exclusions.get("common", []) or []
    exc_only_p1   = exclusions.get("only_in_policy1", []) or []
    exc_only_p2   = exclusions.get("only_in_policy2", []) or []

    # ── a. coverage_bar ───────────────────────────────────────────────────
    shared_cov   = len(cov_common)
    excl_cov_p1  = len(cov_only_p1)
    excl_cov_p2  = len(cov_only_p2)
    shared_exc   = len(exc_common)
    excl_exc_p1  = len(exc_only_p1)
    excl_exc_p2  = len(exc_only_p2)

    coverage_bar = {
        "labels": [
            "Shared Coverage",
            "Exclusive Coverage",
            "Shared Exclusions",
            "Exclusive Exclusions",
        ],
        "policy1_values": [shared_cov, excl_cov_p1, shared_exc, excl_exc_p1],
        "policy2_values": [shared_cov, excl_cov_p2, shared_exc, excl_exc_p2],
    }

    # ── b. coverage_donut ────────────────────────────────────────────────
    coverage_donut = {
        "labels": ["Shared", f"Only {policy1_name}", f"Only {policy2_name}"],
        "values": [shared_cov, excl_cov_p1, excl_cov_p2],
    }

    # ── c. exclusions_donut ──────────────────────────────────────────────
    exclusions_donut = {
        "labels": ["Shared", f"Only {policy1_name}", f"Only {policy2_name}"],
        "values": [shared_exc, excl_exc_p1, excl_exc_p2],
    }

    # ── d. premium_bar ───────────────────────────────────────────────────
    p1_prem = premiums.get("policy1") or {}
    p2_prem = premiums.get("policy2") or {}

    premium_fields = [
        ("Annual Premium",    "annual_premium"),
        ("Monthly Premium",   "monthly_premium"),
        ("Deductible",        "deductible"),
        ("Copay",             "copay"),
        ("Out of Pocket Max", "out_of_pocket_max"),
    ]

    premium_bar = {
        "labels":        [label for label, _ in premium_fields],
        "policy1_values": [_parse_dollar(p1_prem.get(key)) for _, key in premium_fields],
        "policy2_values": [_parse_dollar(p2_prem.get(key)) for _, key in premium_fields],
    }

    # ── e. similarity_histogram ──────────────────────────────────────────
    all_scores: list[float] = []

    for item in cov_common:
        score = item.get("similarity_score")
        if score is not None:
            all_scores.append(_round2(score))

    for item in exc_common:
        score = item.get("similarity_score")
        if score is not None:
            all_scores.append(_round2(score))

    # Items exclusive to one policy have 0.0 similarity — include them so the
    # histogram reflects the full picture even when no common items exist.
    exclusive_count = (
        len(cov_only_p1) + len(cov_only_p2)
        + len(exc_only_p1) + len(exc_only_p2)
    )
    all_scores.extend([0.0] * exclusive_count)

    bucket_labels = ["0.0-0.2", "0.2-0.4", "0.4-0.6", "0.6-0.8", "0.8-1.0"]
    bucket_counts = [0, 0, 0, 0, 0]

    for score in all_scores:
        clamped = max(0.0, min(1.0, score))
        if clamped == 1.0:
            bucket_counts[4] += 1
        else:
            idx = int(clamped / 0.2)
            bucket_counts[idx] += 1

    similarity_histogram = {
        "buckets": bucket_labels,
        "counts":  bucket_counts,
    }

    result = {
        "policy1_name":        policy1_name,
        "policy2_name":        policy2_name,
        "coverage_bar":        coverage_bar,
        "coverage_donut":      coverage_donut,
        "exclusions_donut":    exclusions_donut,
        "premium_bar":         premium_bar,
        "similarity_histogram": similarity_histogram,
    }

    logger.info(
        "Visualisation data built for '%s' vs '%s' — %d similarity scores bucketed",
        policy1_name, policy2_name, len(all_scores),
    )
    return result
