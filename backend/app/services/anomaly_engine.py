"""
anomaly_engine.py
=================
Detects unusual, missing, or concerning characteristics in two insurance
policies by combining rule-based checks against industry benchmarks with
an LLM-powered pass via Groq.
"""
from __future__ import annotations

import json
import logging
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from groq import Groq

from app.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Industry benchmark constants
# ---------------------------------------------------------------------------

INDUSTRY_BENCHMARKS: dict[str, Any] = {
    "max_reasonable_deductible":  5000.0,
    "min_reasonable_deductible":  100.0,
    "max_reasonable_oop":         10000.0,
    "min_reasonable_oop":         1000.0,
    "max_reasonable_copay":       100.0,
    "max_reasonable_coinsurance": 40.0,
    "min_coverage_items":         5,
    "max_exclusion_ratio":        0.5,
    "expected_coverages": [
        "hospitalization", "emergency", "prescription",
        "preventive care", "mental health", "surgery",
        "laboratory", "outpatient",
    ],
    "high_risk_exclusions": [
        "mental health", "pre-existing", "maternity",
        "cancer", "chronic", "experimental", "rehabilitation",
    ],
}

# ---------------------------------------------------------------------------
# Severity / policy ordering helpers
# ---------------------------------------------------------------------------

_SEVERITY_ORDER: dict[str, int] = {"critical": 0, "warning": 1, "info": 2}
_POLICY_ORDER: dict[str, int]   = {"policy1": 0, "policy2": 1, "both": 2, "general": 3}

_VALID_SEVERITIES: frozenset[str] = frozenset({"critical", "warning", "info"})
_VALID_POLICIES:   frozenset[str] = frozenset({"policy1", "policy2", "both", "general"})

# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _parse_dollar(value: str | None) -> float:
    """Parse a dollar-string such as '$1,500' into a float.

    Returns 0.0 on any parse failure so callers can compare safely.
    """
    if not value:
        return 0.0
    try:
        cleaned = value.replace("$", "").replace(",", "").strip()
        return float(cleaned)
    except (ValueError, AttributeError):
        return 0.0


def _parse_percent(value: str | None) -> float:
    """Parse a percent-string such as '20%' or '20' into a float.

    Returns 0.0 on any parse failure.
    """
    if not value:
        return 0.0
    try:
        cleaned = value.replace("%", "").strip()
        return float(cleaned)
    except (ValueError, AttributeError):
        return 0.0


def _compact_comparison(result: dict) -> dict:
    """Return a token-optimised copy of comparison_result for LLM prompts.

    Strips raw_context keys and truncates string values longer than
    120 characters without mutating the original dict.
    """

    def _process(node: Any) -> Any:
        if isinstance(node, dict):
            return {k: _process(v) for k, v in node.items() if k != "raw_context"}
        if isinstance(node, list):
            return [_process(item) for item in node]
        if isinstance(node, str) and len(node) > 120:
            return node[:120] + "\u2026"
        return node

    return _process(deepcopy(result))


def _coverage_texts(comparison_result: dict, policy_key: str) -> list[str]:
    """Collect all coverage item texts visible to a specific policy.

    Combines common-coverage items and items exclusive to that policy.
    """
    coverage = comparison_result.get("coverage", {})
    texts: list[str] = []
    for item in coverage.get("common", []):
        texts.append(str(item.get("item", "")).lower())
    for item in coverage.get(f"only_in_{policy_key}", []):
        texts.append(str(item.get("text", "")).lower())
    return texts


def _exclusion_texts(comparison_result: dict, policy_key: str) -> list[str]:
    """Collect all exclusion item texts visible to a specific policy."""
    exclusions = comparison_result.get("exclusions", {})
    texts: list[str] = []
    for item in exclusions.get("common", []):
        texts.append(str(item.get("item", "")).lower())
    for item in exclusions.get(f"only_in_{policy_key}", []):
        texts.append(str(item.get("text", "")).lower())
    return texts


def _anomaly(
    anomaly_id: str,
    severity: str,
    policy: str,
    category: str,
    title: str,
    description: str,
    evidence: str,
    suggestion: str,
    detected_by: str = "rule",
) -> dict[str, str]:
    """Build a single AnomalyItem dict."""
    return {
        "anomaly_id":  anomaly_id,
        "severity":    severity,
        "policy":      policy,
        "category":    category,
        "title":       title,
        "description": description,
        "evidence":    evidence,
        "suggestion":  suggestion,
        "detected_by": detected_by,
    }


# ---------------------------------------------------------------------------
# Part A — Rule-based detection
# ---------------------------------------------------------------------------


def detect_rule_based_anomalies(
    comparison_result: dict,
    policy1_name: str,
    policy2_name: str,
) -> list[dict]:
    """Run all deterministic rule checks against industry benchmarks.

    Iterates through premium/cost, coverage, exclusion, and balance rules
    and returns a list of AnomalyItem dicts for every rule that fires.
    detected_by is set to "rule" for all items.
    """
    anomalies: list[dict] = []
    bm = INDUSTRY_BENCHMARKS
    premiums = comparison_result.get("premiums", {})
    summary  = comparison_result.get("summary",  {})

    p1_premium = premiums.get("policy1", {})
    p2_premium = premiums.get("policy2", {})

    policy_pairs = [
        ("policy1", "P1", policy1_name, p1_premium),
        ("policy2", "P2", policy2_name, p2_premium),
    ]

    # ── Premium / cost rules ────────────────────────────────────────────────

    for pol_key, pol_suffix, pol_name, prem in policy_pairs:

        deductible  = _parse_dollar(prem.get("deductible"))
        oop         = _parse_dollar(prem.get("out_of_pocket_max"))
        copay       = _parse_dollar(prem.get("copay"))
        coinsurance = _parse_percent(prem.get("coinsurance"))

        if deductible and deductible > bm["max_reasonable_deductible"]:
            logger.debug("Rule HIGH_DEDUCTIBLE_%s triggered: $%.0f", pol_suffix, deductible)
            anomalies.append(_anomaly(
                anomaly_id=f"HIGH_DEDUCTIBLE_{pol_suffix}",
                severity="critical",
                policy=pol_key,
                category="premium",
                title="Unusually High Deductible",
                description=(
                    f"{pol_name} has a deductible that exceeds typical industry limits, "
                    "meaning you may face large out-of-pocket costs before coverage begins."
                ),
                evidence=f"Deductible: {prem.get('deductible')}",
                suggestion="Look for policies with deductibles at or below $5,000.",
            ))

        if deductible and deductible < bm["min_reasonable_deductible"]:
            logger.debug("Rule LOW_DEDUCTIBLE_%s triggered: $%.0f", pol_suffix, deductible)
            anomalies.append(_anomaly(
                anomaly_id=f"LOW_DEDUCTIBLE_{pol_suffix}",
                severity="info",
                policy=pol_key,
                category="premium",
                title="Unusually Low Deductible",
                description=(
                    f"{pol_name} has a very low deductible, which typically corresponds "
                    "to a higher monthly premium."
                ),
                evidence=f"Deductible: {prem.get('deductible')}",
                suggestion="Verify that the associated premium is reasonable for your budget.",
            ))

        if oop and oop > bm["max_reasonable_oop"]:
            logger.debug("Rule HIGH_OOP_%s triggered: $%.0f", pol_suffix, oop)
            anomalies.append(_anomaly(
                anomaly_id=f"HIGH_OOP_{pol_suffix}",
                severity="critical",
                policy=pol_key,
                category="premium",
                title="Unusually High Out-of-Pocket Maximum",
                description=(
                    f"{pol_name} has an out-of-pocket maximum above industry norms, "
                    "which could expose you to significant financial risk in a serious illness."
                ),
                evidence=f"Out-of-pocket max: {prem.get('out_of_pocket_max')}",
                suggestion="Seek a policy with an out-of-pocket maximum at or below $10,000.",
            ))

        if copay and copay > bm["max_reasonable_copay"]:
            logger.debug("Rule HIGH_COPAY_%s triggered: $%.0f", pol_suffix, copay)
            anomalies.append(_anomaly(
                anomaly_id=f"HIGH_COPAY_{pol_suffix}",
                severity="warning",
                policy=pol_key,
                category="premium",
                title="High Copay Amount",
                description=(
                    f"{pol_name} has a copay that exceeds what is typically considered "
                    "reasonable, increasing the cost of each visit."
                ),
                evidence=f"Copay: {prem.get('copay')}",
                suggestion="Compare with plans that offer copays under $100 per visit.",
            ))

        if coinsurance and coinsurance > bm["max_reasonable_coinsurance"]:
            logger.debug("Rule HIGH_COINSURANCE_%s triggered: %.0f%%", pol_suffix, coinsurance)
            anomalies.append(_anomaly(
                anomaly_id=f"HIGH_COINSURANCE_{pol_suffix}",
                severity="warning",
                policy=pol_key,
                category="premium",
                title="High Coinsurance Percentage",
                description=(
                    f"{pol_name} requires you to pay more than 40% coinsurance after "
                    "meeting the deductible, which is above industry norms."
                ),
                evidence=f"Coinsurance: {prem.get('coinsurance')}",
                suggestion="Look for plans with coinsurance at or below 30%.",
            ))

        annual  = prem.get("annual_premium")
        monthly = prem.get("monthly_premium")
        if not annual and not monthly:
            logger.debug("Rule MISSING_PREMIUM_%s triggered", pol_suffix)
            anomalies.append(_anomaly(
                anomaly_id=f"MISSING_PREMIUM_{pol_suffix}",
                severity="warning",
                policy=pol_key,
                category="structure",
                title="Premium Information Not Found",
                description=(
                    f"No premium details were extracted for {pol_name}. "
                    "The document may not clearly state the cost."
                ),
                evidence="annual_premium and monthly_premium both absent",
                suggestion="Request a full premium schedule directly from the insurer.",
            ))

    p1_annual  = _parse_dollar(p1_premium.get("annual_premium"))
    p2_annual  = _parse_dollar(p2_premium.get("annual_premium"))
    p1_monthly = _parse_dollar(p1_premium.get("monthly_premium"))
    p2_monthly = _parse_dollar(p2_premium.get("monthly_premium"))

    annual_base  = p1_annual  if p1_annual and p2_annual   else 0.0
    monthly_base = p1_monthly if p1_monthly and p2_monthly else 0.0

    if annual_base:
        lower  = min(p1_annual, p2_annual)
        higher = max(p1_annual, p2_annual)
        if lower and (higher - lower) / lower > 0.5:
            logger.debug("Rule LARGE_PREMIUM_GAP triggered: $%.0f vs $%.0f", p1_annual, p2_annual)
            anomalies.append(_anomaly(
                anomaly_id="LARGE_PREMIUM_GAP",
                severity="info",
                policy="general",
                category="premium",
                title="Large Premium Difference Between Policies",
                description=(
                    "The two policies differ significantly in annual premium, "
                    "which may indicate substantially different coverage levels or risk profiles."
                ),
                evidence=f"Policy 1: {p1_premium.get('annual_premium')} vs Policy 2: {p2_premium.get('annual_premium')}",
                suggestion="Ensure the higher-priced policy offers proportionally better coverage before committing.",
            ))
    elif monthly_base:
        lower  = min(p1_monthly, p2_monthly)
        higher = max(p1_monthly, p2_monthly)
        if lower and (higher - lower) / lower > 0.5:
            logger.debug("Rule LARGE_PREMIUM_GAP triggered: $%.0f vs $%.0f /mo", p1_monthly, p2_monthly)
            anomalies.append(_anomaly(
                anomaly_id="LARGE_PREMIUM_GAP",
                severity="info",
                policy="general",
                category="premium",
                title="Large Premium Difference Between Policies",
                description=(
                    "The two policies differ significantly in monthly premium, "
                    "which may indicate substantially different coverage levels or risk profiles."
                ),
                evidence=f"Policy 1: {p1_premium.get('monthly_premium')}/mo vs Policy 2: {p2_premium.get('monthly_premium')}/mo",
                suggestion="Ensure the higher-priced policy offers proportionally better coverage before committing.",
            ))

    # ── Coverage rules ───────────────────────────────────────────────────────

    total_p1 = summary.get("total_coverage_items_policy1", 0) or 0
    total_p2 = summary.get("total_coverage_items_policy2", 0) or 0

    for pol_key, pol_suffix, pol_name, total in [
        ("policy1", "P1", policy1_name, total_p1),
        ("policy2", "P2", policy2_name, total_p2),
    ]:
        if total < bm["min_coverage_items"]:
            logger.debug("Rule LOW_COVERAGE_COUNT_%s triggered: %d items", pol_suffix, total)
            anomalies.append(_anomaly(
                anomaly_id=f"LOW_COVERAGE_COUNT_{pol_suffix}",
                severity="critical",
                policy=pol_key,
                category="coverage",
                title="Very Few Coverage Items Detected",
                description=(
                    f"Only {total} coverage item(s) were extracted from {pol_name}, "
                    "which is below the minimum expected for a comprehensive policy."
                ),
                evidence=f"Coverage items found: {total}",
                suggestion="Request a full policy schedule to confirm all covered services.",
            ))

    for pol_key, pol_suffix, pol_name in [
        ("policy1", "P1", policy1_name),
        ("policy2", "P2", policy2_name),
    ]:
        cov_texts = _coverage_texts(comparison_result, pol_key)
        for expected in bm["expected_coverages"]:
            if not any(expected in text for text in cov_texts):
                logger.debug(
                    "Rule MISSING_EXPECTED_COVERAGE_%s triggered: %s", pol_suffix, expected
                )
                anomalies.append(_anomaly(
                    anomaly_id=f"MISSING_EXPECTED_COVERAGE_{pol_suffix}_{expected.upper().replace(' ', '_')}",
                    severity="warning",
                    policy=pol_key,
                    category="coverage",
                    title=f"Missing Expected Coverage: {expected.title()}",
                    description=(
                        f"{pol_name} does not appear to include {expected} coverage, "
                        "which is commonly expected in standard insurance plans."
                    ),
                    evidence=f"'{expected}' not found in any coverage item",
                    suggestion=f"Ask the insurer to confirm whether {expected} is covered and under what conditions.",
                ))

    for pol_key, pol_suffix, pol_name in [
        ("policy1", "P1", policy1_name),
        ("policy2", "P2", policy2_name),
    ]:
        excl_count = len(comparison_result.get("exclusions", {}).get("common", [])) + \
                     len(comparison_result.get("exclusions", {}).get(f"only_in_{pol_key}", []))
        cov_count  = (total_p1 if pol_key == "policy1" else total_p2)
        ratio      = excl_count / max(1, cov_count + excl_count)
        if ratio > bm["max_exclusion_ratio"]:
            logger.debug(
                "Rule HIGH_EXCLUSION_RATIO_%s triggered: %.0f%%", pol_suffix, ratio * 100
            )
            anomalies.append(_anomaly(
                anomaly_id=f"HIGH_EXCLUSION_RATIO_{pol_suffix}",
                severity="warning",
                policy=pol_key,
                category="balance",
                title="High Exclusion-to-Coverage Ratio",
                description=(
                    f"{pol_name} has a high proportion of exclusions relative to its "
                    "covered items, which may indicate limited real-world protection."
                ),
                evidence=f"Exclusion ratio: {ratio:.0%}",
                suggestion="Carefully review each exclusion to understand what is NOT protected.",
            ))

    # ── Exclusion rules ──────────────────────────────────────────────────────

    for pol_key, pol_suffix, pol_name in [
        ("policy1", "P1", policy1_name),
        ("policy2", "P2", policy2_name),
    ]:
        excl_texts = _exclusion_texts(comparison_result, pol_key)
        for risk_item in bm["high_risk_exclusions"]:
            if any(risk_item in text for text in excl_texts):
                logger.debug(
                    "Rule HIGH_RISK_EXCLUSION_%s triggered: %s", pol_suffix, risk_item
                )
                anomalies.append(_anomaly(
                    anomaly_id=f"HIGH_RISK_EXCLUSION_{pol_suffix}_{risk_item.upper().replace(' ', '_').replace('-', '_')}",
                    severity="warning",
                    policy=pol_key,
                    category="exclusion",
                    title=f"High-Risk Exclusion: {risk_item.title()}",
                    description=(
                        f"{pol_name} explicitly excludes {risk_item}, which is a commonly "
                        "needed coverage area for many policyholders."
                    ),
                    evidence=f"'{risk_item}' found in exclusion list",
                    suggestion=f"If {risk_item} coverage is important to you, look for a policy that includes it or seek a rider.",
                ))

    # ── Balance / comparison rules ───────────────────────────────────────────

    shared = summary.get("shared_coverage_items", 0) or 0

    if abs(total_p1 - total_p2) > 10:
        logger.debug(
            "Rule COVERAGE_IMBALANCE triggered: %d vs %d", total_p1, total_p2
        )
        anomalies.append(_anomaly(
            anomaly_id="COVERAGE_IMBALANCE",
            severity="info",
            policy="general",
            category="balance",
            title="Significant Coverage Count Difference",
            description=(
                "The two policies have a notably different number of coverage items, "
                "suggesting they offer substantially different levels of protection."
            ),
            evidence=f"Policy 1: {total_p1} items, Policy 2: {total_p2} items",
            suggestion="Investigate whether the policy with fewer items has broader single-item coverage or is genuinely less comprehensive.",
        ))

    if shared == 0:
        logger.debug("Rule NO_SHARED_COVERAGE triggered")
        anomalies.append(_anomaly(
            anomaly_id="NO_SHARED_COVERAGE",
            severity="critical",
            policy="both",
            category="balance",
            title="No Shared Coverage Items Found",
            description=(
                "The two policies share no common coverage items at all, "
                "which is highly unusual and may indicate parsing issues or fundamentally different policy types."
            ),
            evidence="shared_coverage_items = 0",
            suggestion="Verify the uploaded documents are valid insurance policies before comparing.",
        ))

    for pol_key, pol_suffix, pol_name, cov_total in [
        ("policy1", "P1", policy1_name, total_p1),
        ("policy2", "P2", policy2_name, total_p2),
    ]:
        excl_only = len(comparison_result.get("exclusions", {}).get(f"only_in_{pol_key}", []))
        common_excl = len(comparison_result.get("exclusions", {}).get("common", []))
        total_excl = excl_only + common_excl
        if cov_total == 0 and total_excl > 0:
            logger.debug("Rule EXCLUSION_ONLY_POLICY_%s triggered", pol_suffix)
            anomalies.append(_anomaly(
                anomaly_id=f"EXCLUSION_ONLY_POLICY_{pol_suffix}",
                severity="critical",
                policy=pol_key,
                category="structure",
                title="Policy Has Exclusions But No Coverage Items",
                description=(
                    f"{pol_name} contains exclusion items but no coverage items were detected. "
                    "This is almost certainly a parsing error or a non-standard document."
                ),
                evidence=f"Coverage items: 0, Exclusion items: {total_excl}",
                suggestion="Re-upload the document or contact the insurer for a structured benefits summary.",
            ))

    logger.info("Rule-based detection complete — %d anomalies found", len(anomalies))
    return anomalies


# ---------------------------------------------------------------------------
# Part B — LLM-based detection
# ---------------------------------------------------------------------------

_LLM_SYSTEM_PROMPT = """\
You are an expert insurance analyst. You will receive structured JSON data \
comparing two insurance policies and a list of anomaly IDs already detected \
by automated rules. Your job is to identify additional anomalies not already \
flagged by those rules.

Rules:
- Only flag genuine anomalies NOT already in the provided rule_anomaly_ids list.
- Base everything strictly on the provided policy data — never invent details.
- insights must be in plain English, suitable for a consumer reading their \
insurance policy — avoid jargon.
- severity="critical" only for issues that could cause significant financial harm.
- Return at minimum 2 anomalies and exactly 5 insights.
- If no additional anomalies exist beyond the rules, return anomalies as an \
empty array but always return exactly 5 insights.

Return ONLY valid JSON — no markdown fences, no text outside the JSON object.
"""


def detect_llm_anomalies(
    comparison_result: dict,
    policy1_name: str,
    policy2_name: str,
    rule_anomalies: list[dict],
) -> tuple[list[dict], list[str]]:
    """Detect additional anomalies using the Groq LLM beyond rule-based checks.

    Sends a compact comparison_result and the list of already-detected rule
    anomaly IDs to Groq, requesting novel anomaly items and five plain-English
    insights about overall policy quality.  Returns a tuple of
    (llm_anomaly_items, llm_insights).  On any Groq failure, logs a WARNING
    and returns ([], []) so that rule-based results are still surfaced.
    """
    rule_ids = [a["anomaly_id"] for a in rule_anomalies]
    compact  = _compact_comparison(comparison_result)

    prompt = (
        f"Policy 1 name: {policy1_name}\n"
        f"Policy 2 name: {policy2_name}\n\n"
        f"Comparison data:\n{json.dumps(compact)}\n\n"
        f"Anomaly IDs already detected by rules (do NOT duplicate these):\n"
        f"{json.dumps(rule_ids)}\n\n"
        "Return a JSON object with exactly this structure:\n"
        "{\n"
        '  "anomalies": [\n'
        "    {\n"
        '      "anomaly_id": "UNIQUE_SLUG_IN_CAPS",\n'
        '      "severity": "critical | warning | info",\n'
        '      "policy": "policy1 | policy2 | both | general",\n'
        '      "category": "premium | coverage | exclusion | structure | balance",\n'
        '      "title": "Short anomaly title",\n'
        '      "description": "1-2 sentences explaining the issue",\n'
        '      "evidence": "specific text or value from the policy",\n'
        '      "suggestion": "one actionable sentence"\n'
        "    }\n"
        "  ],\n"
        '  "insights": [\n'
        '    "Plain-English observation 1",\n'
        '    "Plain-English observation 2",\n'
        '    "Plain-English observation 3",\n'
        '    "Plain-English observation 4",\n'
        '    "Plain-English observation 5"\n'
        "  ]\n"
        "}"
    )

    try:
        client = Groq(api_key=settings.GROQ_API_KEY)
        chat_response = client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[
                {"role": "system", "content": _LLM_SYSTEM_PROMPT},
                {"role": "user",   "content": prompt},
            ],
            temperature=0.1,
            response_format={"type": "json_object"},
            max_tokens=2500,
        )
    except Exception as exc:
        logger.warning("Groq anomaly detection failed — falling back to rule results only: %s", exc)
        return [], []

    raw_text: str = chat_response.choices[0].message.content or ""
    logger.debug("Raw Groq anomaly response: %.300s", raw_text)

    try:
        payload: dict[str, Any] = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        logger.warning("Failed to parse Groq anomaly JSON: %s — falling back to rule results only", exc)
        return [], []

    rule_ids_lower = {rid.lower() for rid in rule_ids}

    raw_items: list[dict] = payload.get("anomalies") or []
    llm_items: list[dict] = []
    for item in raw_items:
        aid = str(item.get("anomaly_id", "")).strip()
        if not aid:
            continue
        if aid.lower() in rule_ids_lower:
            continue

        sev = item.get("severity", "")
        if sev not in _VALID_SEVERITIES:
            logger.warning("LLM anomaly %r has invalid severity %r — using 'info'", aid, sev)
            item["severity"] = "info"

        pol = item.get("policy", "")
        if pol not in _VALID_POLICIES:
            logger.warning("LLM anomaly %r has invalid policy %r — using 'general'", aid, pol)
            item["policy"] = "general"

        item["detected_by"] = "llm"
        item.setdefault("category",    "structure")
        item.setdefault("title",       aid)
        item.setdefault("description", "")
        item.setdefault("evidence",    "")
        item.setdefault("suggestion",  "")
        llm_items.append(item)

    insights: list[str] = [str(s) for s in (payload.get("insights") or []) if s]

    logger.info("LLM anomaly detection complete — %d new anomalies, %d insights", len(llm_items), len(insights))
    return llm_items, insights


# ---------------------------------------------------------------------------
# Part C — Orchestrator
# ---------------------------------------------------------------------------


def run_anomaly_detection(
    comparison_result: dict,
    policy1_name: str,
    policy2_name: str,
) -> dict:
    """Orchestrate rule-based and LLM-based anomaly detection and return results.

    Calls detect_rule_based_anomalies followed by detect_llm_anomalies, merges
    and sorts the combined anomaly list, computes the AnomalySummary, determines
    the riskiest policy by critical + warning vote, and returns a dict matching
    AnomalyDetectionResponse field names.
    """
    rule_anomalies = detect_rule_based_anomalies(comparison_result, policy1_name, policy2_name)
    llm_anomalies, llm_insights = detect_llm_anomalies(
        comparison_result, policy1_name, policy2_name, rule_anomalies
    )

    all_anomalies = rule_anomalies + llm_anomalies

    all_anomalies.sort(key=lambda a: (
        _SEVERITY_ORDER.get(a.get("severity", "info"), 2),
        _POLICY_ORDER.get(a.get("policy", "general"), 3),
    ))

    total     = len(all_anomalies)
    critical  = sum(1 for a in all_anomalies if a.get("severity") == "critical")
    warning   = sum(1 for a in all_anomalies if a.get("severity") == "warning")
    info      = sum(1 for a in all_anomalies if a.get("severity") == "info")
    p1_count  = sum(1 for a in all_anomalies if a.get("policy") == "policy1")
    p2_count  = sum(1 for a in all_anomalies if a.get("policy") == "policy2")
    both_cnt  = sum(1 for a in all_anomalies if a.get("policy") in {"both", "general"})

    def _risk_score(policy_key: str) -> int:
        return sum(
            1 for a in all_anomalies
            if a.get("policy") == policy_key
            and a.get("severity") in {"critical", "warning"}
        )

    p1_risk = _risk_score("policy1")
    p2_risk = _risk_score("policy2")

    if p1_risk > p2_risk:
        riskiest_policy      = "policy1"
        riskiest_policy_name = policy1_name
    elif p2_risk > p1_risk:
        riskiest_policy      = "policy2"
        riskiest_policy_name = policy2_name
    else:
        riskiest_policy      = "equal"
        riskiest_policy_name = None

    logger.info(
        "Anomaly detection complete — total=%d critical=%d warning=%d info=%d",
        total, critical, warning, info,
    )

    return {
        "anomalies": all_anomalies,
        "summary": {
            "total_anomalies":      total,
            "critical_count":       critical,
            "warning_count":        warning,
            "info_count":           info,
            "policy1_anomalies":    p1_count,
            "policy2_anomalies":    p2_count,
            "both_anomalies":       both_cnt,
            "riskiest_policy":      riskiest_policy,
            "riskiest_policy_name": riskiest_policy_name,
        },
        "llm_insights": llm_insights,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
