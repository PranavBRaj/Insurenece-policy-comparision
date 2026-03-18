"""
recommendation_engine.py
========================
Uses the Groq LLM to generate policy recommendations tailored to a user
profile and four standard demographic profiles.  The full comparison JSON
is embedded in the prompt after a token-optimisation pass.
"""
from __future__ import annotations

import json
import logging
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.services.llm_client import llm_chat_completion, resolve_llm_provider

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_VALID_RECOMMENDATIONS: frozenset[str] = frozenset({"policy1", "policy2", "either", "neither"})
_VALID_CONFIDENCES: frozenset[str] = frozenset({"high", "medium", "low"})

_STANDARD_PROFILES: List[str] = [
    "Young Single Professional",
    "Family with Children",
    "Senior / Retired",
    "Chronic Condition Management",
]

_FALLBACK_PROFILE_TEMPLATE: Dict[str, Any] = {
    "recommended_policy": "either",
    "recommended_policy_name": "Either policy",
    "confidence": "low",
    "reasoning": (
        "Insufficient data was returned by the recommendation engine for this profile."
    ),
    "key_factors": ["No specific data available — review the full comparison manually."],
    "caveats": ["Please consult the detailed comparison sections for an informed decision."],
}

_SYSTEM_PROMPT = """\
You are an expert insurance advisor. You will receive a structured JSON \
comparison of two insurance policies and a user profile. Your task is to \
recommend which policy better suits the user and four standard demographic \
profiles.

Rules:
- Base ALL recommendations strictly on the provided policy data.
- Never invent coverage details not present in the comparison.
- If the data is insufficient to recommend confidently, set \
confidence="low" and explain why in reasoning.
- Always reference specific coverage items or dollar amounts when \
explaining key_factors.
- recommended_policy must always be exactly one of: \
"policy1", "policy2", "either", "neither".

Return ONLY valid JSON — no markdown fences, no text outside the JSON object.
"""


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _compact_comparison(result: dict) -> dict:
    """Return a token-optimised copy of comparison_result.

    Strips raw_context keys and truncates any string value longer than
    150 characters without mutating the original dict.
    """

    def _process(node: Any) -> Any:
        if isinstance(node, dict):
            return {
                k: _process(v)
                for k, v in node.items()
                if k != "raw_context"
            }
        if isinstance(node, list):
            return [_process(item) for item in node]
        if isinstance(node, str) and len(node) > 150:
            return node[:150] + "\u2026"
        return node

    return _process(deepcopy(result))


def _sanitise_profile(
    profile: Dict[str, Any],
    policy1_name: str,
    policy2_name: str,
) -> Dict[str, Any]:
    """Validate and sanitise a single profile recommendation dict in-place.

    Applies safe fallbacks for recommended_policy and confidence if the
    LLM returns unexpected values, and ensures recommended_policy_name is
    always populated.
    """
    rec = profile.get("recommended_policy", "")
    if rec not in _VALID_RECOMMENDATIONS:
        logger.warning(
            "Unexpected recommended_policy value %r from Groq; "
            "falling back to 'either'",
            rec,
        )
        profile["recommended_policy"] = "either"
        rec = "either"

    conf = profile.get("confidence", "")
    if conf not in _VALID_CONFIDENCES:
        logger.warning(
            "Unexpected confidence value %r from Groq; falling back to 'low'",
            conf,
        )
        profile["confidence"] = "low"

    if not profile.get("recommended_policy_name"):
        if rec == "policy1":
            profile["recommended_policy_name"] = policy1_name
        elif rec == "policy2":
            profile["recommended_policy_name"] = policy2_name
        else:
            profile["recommended_policy_name"] = "Either policy"

    return profile


def _compute_overall_winner(
    primary: Dict[str, Any],
    alternatives: List[Dict[str, Any]],
) -> str:
    """Determine the overall winner by majority vote across all profiles.

    Counts policy1 and policy2 votes from the primary recommendation and all
    four alternative profiles.  Returns "policy1", "policy2", or "tie".
    """
    counts: Dict[str, int] = {"policy1": 0, "policy2": 0}
    for profile in [primary, *alternatives]:
        rec = profile.get("recommended_policy", "")
        if rec in counts:
            counts[rec] += 1

    if counts["policy1"] > counts["policy2"]:
        return "policy1"
    if counts["policy2"] > counts["policy1"]:
        return "policy2"
    return "tie"


def _build_prompt(
    compact_result: dict,
    profile_for_prompt: dict,
    policy1_name: str,
    policy2_name: str,
) -> str:
    """Assemble the user-turn prompt sent to Groq."""
    return (
        f"Policy 1 name: {policy1_name}\n"
        f"Policy 2 name: {policy2_name}\n\n"
        f"Comparison data:\n{json.dumps(compact_result)}\n\n"
        f"User profile:\n{json.dumps(profile_for_prompt)}\n\n"
        "Return a JSON object with exactly this structure:\n"
        "{\n"
        '  "primary_recommendation": {\n'
        '    "profile_label": "descriptive label for this specific user",\n'
        '    "recommended_policy": "policy1 | policy2 | either | neither",\n'
        '    "recommended_policy_name": "actual filename",\n'
        '    "confidence": "high | medium | low",\n'
        '    "reasoning": "2-4 sentence explanation grounded in the policy data",\n'
        '    "key_factors": ["factor 1", "factor 2", "factor 3"],\n'
        '    "caveats": ["caveat 1"]\n'
        "  },\n"
        '  "alternative_profiles": [\n'
        '    {\n'
        '      "profile_label": "Young Single Professional",\n'
        '      "recommended_policy": "policy1 | policy2 | either | neither",\n'
        '      "recommended_policy_name": "actual filename",\n'
        '      "confidence": "high | medium | low",\n'
        '      "reasoning": "...",\n'
        '      "key_factors": ["...", "...", "..."],\n'
        '      "caveats": ["..."]\n'
        "    },\n"
        '    { "profile_label": "Family with Children", "recommended_policy": "...", '
        '"recommended_policy_name": "...", "confidence": "...", '
        '"reasoning": "...", "key_factors": ["..."], "caveats": ["..."] },\n'
        '    { "profile_label": "Senior / Retired", "recommended_policy": "...", '
        '"recommended_policy_name": "...", "confidence": "...", '
        '"reasoning": "...", "key_factors": ["..."], "caveats": ["..."] },\n'
        '    { "profile_label": "Chronic Condition Management", "recommended_policy": "...", '
        '"recommended_policy_name": "...", "confidence": "...", '
        '"reasoning": "...", "key_factors": ["..."], "caveats": ["..."] }\n'
        "  ],\n"
        '  "overall_winner": "policy1 | policy2 | tie",\n'
        '  "overall_winner_name": "actual filename or \'Tie\'"\n'
        "}"
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_recommendations(
    comparison_result: dict,
    user_profile: dict,
    policy1_name: str,
    policy2_name: str,
    llm_provider: Optional[str] = None,
) -> dict:
    """Generate LLM-powered policy recommendations for a user and standard profiles.

    Sends a compacted comparison_result and user_profile to the Groq LLM,
    requesting structured JSON recommendations for the user's specific situation
    and four standard profiles: Young Single Professional, Family with Children,
    Senior / Retired, and Chronic Condition Management.  Post-processes the
    response to sanitise values, pad missing profiles, recompute the overall
    winner, and attach a generated_at timestamp.

    Raises ValueError with a descriptive message if the Groq API call fails or
    returns a response that cannot be parsed as JSON.
    """
    logger.info(
        "Starting recommendation generation — budget_priority=%s, primary_concern=%s",
        user_profile.get("budget_priority"),
        user_profile.get("primary_concern"),
    )

    selected_provider = resolve_llm_provider(llm_provider)

    compact_result = _compact_comparison(comparison_result)
    profile_for_prompt = {k: v for k, v in user_profile.items() if v is not None}
    prompt = _build_prompt(compact_result, profile_for_prompt, policy1_name, policy2_name)

    try:
        raw_text = llm_chat_completion(
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            provider=selected_provider,
            temperature=0.1,
            json_mode=True,
            max_tokens=3000,
        )
    except Exception as exc:
        raise ValueError(f"LLM API request failed: {exc}") from exc

    logger.debug("Raw %s recommendation response: %.300s", selected_provider, raw_text)

    try:
        payload: Dict[str, Any] = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"LLM returned non-JSON recommendation response: {exc}"
        ) from exc

    primary: Dict[str, Any] = _sanitise_profile(
        payload.get("primary_recommendation", {}),
        policy1_name,
        policy2_name,
    )
    payload["primary_recommendation"] = primary

    raw_alternatives: List[Dict[str, Any]] = payload.get("alternative_profiles", [])
    alternatives: List[Dict[str, Any]] = [
        _sanitise_profile(p, policy1_name, policy2_name) for p in raw_alternatives
    ]

    while len(alternatives) < 4:
        idx = len(alternatives)
        fallback = dict(_FALLBACK_PROFILE_TEMPLATE)
        fallback["profile_label"] = (
            _STANDARD_PROFILES[idx]
            if idx < len(_STANDARD_PROFILES)
            else f"Profile {idx + 1}"
        )
        alternatives.append(fallback)

    payload["alternative_profiles"] = alternatives[:4]

    overall_winner = _compute_overall_winner(primary, payload["alternative_profiles"])
    payload["overall_winner"] = overall_winner
    if overall_winner == "policy1":
        payload["overall_winner_name"] = policy1_name
    elif overall_winner == "policy2":
        payload["overall_winner_name"] = policy2_name
    else:
        payload["overall_winner_name"] = "Tie"

    payload["generated_at"] = datetime.now(timezone.utc).isoformat()

    logger.info(
        "Recommendation generation completed — overall_winner=%s", overall_winner
    )
    return payload
