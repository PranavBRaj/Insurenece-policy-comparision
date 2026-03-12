"""
plain_summary_engine.py
=======================
Generates a consumer-friendly, jargon-free plain-English summary of a
policy comparison result using the Groq LLM at a Grade 6 reading level.
"""
from __future__ import annotations

import copy
import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict

from groq import Groq

from app.config import settings

logger = logging.getLogger(__name__)

_VALID_WINNERS: frozenset[str] = frozenset({"policy1", "policy2", "tie"})

_WORD_LIMITS: Dict[str, int] = {
    "one_liner": 20,
    "biggest_strength": 20,
    "biggest_weakness": 20,
    "key_difference": 30,
    "bottom_line": 50,
    "what_it_doesnt_cover": 50,
    "cost_plain": 50,
    "coverage_comparison": 60,
    "cost_comparison": 60,
    "what_it_covers": 60,
    "executive_summary": 80,
}

_SYSTEM_ROLE = (
    "You are a consumer advocate helping ordinary people understand their "
    "insurance policies. You write at a Grade 6 reading level. You never use "
    "jargon. You are direct, honest, and always put the reader's financial "
    "interests first."
)

_FORBIDDEN_WORDS_BLOCK = """\
FORBIDDEN WORDS — never use these exact words: deductible, coinsurance, copay, \
premium, out-of-pocket, insured, policyholder, beneficiary, rider, underwriting, actuarial.
Plain substitutes to use instead:
- deductible → "the amount you pay before insurance helps"
- coinsurance → "the percentage you share after that"
- copay → "your fixed fee per visit"
- premium → "your monthly payment"
- out-of-pocket max → "the most you could ever pay in a year"\
"""


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _compact_for_summary(result: dict) -> dict:
    """Return a stripped copy of comparison_result safe to embed in a prompt.

    Removes raw_context fields, truncates detail strings to 100 characters,
    and caps list lengths at 15 items per section.  The original dict is
    never mutated.
    """
    data = copy.deepcopy(result)

    def _trim_items(items: list) -> list:
        out = []
        for item in items[:15]:
            item.pop("raw_context", None)
            for key in ("policy1_details", "policy2_details"):
                if isinstance(item.get(key), str):
                    item[key] = item[key][:100]
            out.append(item)
        return out

    for section in ("coverage", "exclusions"):
        sec = data.get(section)
        if isinstance(sec, dict):
            for sub in ("common", "only_in_policy1", "only_in_policy2"):
                if isinstance(sec.get(sub), list):
                    sec[sub] = _trim_items(sec[sub])

    return data


def _strip_markdown(text: str) -> str:
    """Remove common markdown formatting characters from a string."""
    text = re.sub(r"\*{1,2}|_{1,2}|#{1,6}\s?", "", text)
    return text.strip()


def _word_count(text: str) -> int:
    """Return the number of whitespace-separated words in text."""
    return len(text.split())


def _apply_markdown_strip(p1: dict, p2: dict, cs: dict) -> None:
    """Strip accidental markdown from all text fields in place."""
    for d in (p1, p2, cs):
        for key, val in d.items():
            if isinstance(val, str):
                d[key] = _strip_markdown(val)


def _validate_winners(cs: dict) -> None:
    """Coerce who_wins_* fields to valid values, falling back to 'tie'."""
    for field in ("who_wins_cost", "who_wins_coverage", "who_wins_overall"):
        val = cs.get(field, "")
        if val not in _VALID_WINNERS:
            logger.warning(
                "Invalid who_wins value '%s' for field '%s'; falling back to 'tie'",
                val,
                field,
            )
            cs[field] = "tie"


def _apply_fallbacks(
    p1: dict,
    p2: dict,
    cs: dict,
    result: dict,
    policy1_name: str,
    policy2_name: str,
) -> None:
    """Replace empty or null text fields with sensible fallback values."""
    summary = result.get("summary", {})
    p1_cov = summary.get("total_coverage_items_policy1", 0)
    p2_cov = summary.get("total_coverage_items_policy2", 0)
    shared = summary.get("shared_coverage_items", 0)

    for ps, pol_name, adv_key, cov_count in [
        (p1, policy1_name, "policy1_advantages", p1_cov),
        (p2, policy2_name, "policy2_advantages", p2_cov),
    ]:
        if not ps.get("one_liner"):
            ps["one_liner"] = f"A policy with {cov_count} coverage items"
            logger.warning("Fallback used for 'one_liner' in '%s'", pol_name)

        advantages: list = summary.get(adv_key, [])
        if not ps.get("biggest_strength"):
            ps["biggest_strength"] = (
                advantages[0] if advantages else "No specific advantages identified"
            )
            logger.warning("Fallback used for 'biggest_strength' in '%s'", pol_name)

    if not cs.get("executive_summary"):
        cs["executive_summary"] = (
            f"{policy1_name} covers {p1_cov} items and {policy2_name} covers "
            f"{p2_cov} items, sharing {shared} in common."
        )
        logger.warning("Fallback used for 'executive_summary'")


def _check_word_limits(p1: dict, p2: dict, cs: dict) -> None:
    """Log warnings for text fields that exceed their word limit by more than 50 %."""
    all_items = [
        *((k, v) for k, v in p1.items() if isinstance(v, str)),
        *((k, v) for k, v in p2.items() if isinstance(v, str)),
        *((k, v) for k, v in cs.items() if isinstance(v, str)),
    ]
    for field, value in all_items:
        limit = _WORD_LIMITS.get(field)
        if limit is None:
            continue
        wc = _word_count(value)
        if wc > limit * 1.5:
            logger.warning(
                "Field '%s' has %d words, exceeds limit of %d by >50%%",
                field,
                wc,
                limit,
            )


def _build_prompt(compact: dict, policy1_name: str, policy2_name: str) -> str:
    """Assemble the full user message sent to the Groq LLM."""
    return (
        f"ROLE:\n{_SYSTEM_ROLE}\n\n"
        f"{_FORBIDDEN_WORDS_BLOCK}\n\n"
        "TASK:\n"
        "You will receive the result of a side-by-side comparison of two insurance "
        "policies. Generate a plain-English summary that any adult can understand.\n\n"
        f"Policy 1 name: {policy1_name}\n"
        f"Policy 2 name: {policy2_name}\n\n"
        f"Comparison data:\n{json.dumps(compact, indent=2)}\n\n"
        "RULES:\n"
        '1. Write in second person — use "you" and "your", not "the insured" '
        'or "the policyholder".\n'
        "2. Use actual dollar figures from the data wherever available.\n"
        '3. If a cost field is missing or null, write "not stated in this policy" '
        '— never write "null" or "N/A".\n'
        "4. who_wins_cost, who_wins_coverage, and who_wins_overall must each be "
        "exactly one of: policy1, policy2, tie — no other values are allowed.\n"
        "5. Every text field must be flowing prose — no bullet points, no markdown "
        "formatting, no headers inside strings.\n"
        "6. Word limits (do not exceed):\n"
        "   one_liner: 20 words, biggest_strength: 20 words, biggest_weakness: 20 words,\n"
        "   key_difference: 30 words, bottom_line: 50 words,\n"
        "   what_it_doesnt_cover: 50 words, cost_plain: 50 words,\n"
        "   coverage_comparison: 60 words, cost_comparison: 60 words,\n"
        "   what_it_covers: 60 words, executive_summary: 80 words.\n\n"
        "Return ONLY a valid JSON object with this exact structure:\n"
        "{\n"
        '  "policy1_summary": {\n'
        f'    "policy_name": "{policy1_name}",\n'
        '    "one_liner": "...",\n'
        '    "what_it_covers": "...",\n'
        '    "what_it_doesnt_cover": "...",\n'
        '    "cost_plain": "...",\n'
        '    "biggest_strength": "...",\n'
        '    "biggest_weakness": "..."\n'
        "  },\n"
        '  "policy2_summary": {\n'
        f'    "policy_name": "{policy2_name}",\n'
        '    "one_liner": "...",\n'
        '    "what_it_covers": "...",\n'
        '    "what_it_doesnt_cover": "...",\n'
        '    "cost_plain": "...",\n'
        '    "biggest_strength": "...",\n'
        '    "biggest_weakness": "..."\n'
        "  },\n"
        '  "comparison_summary": {\n'
        '    "executive_summary": "...",\n'
        '    "key_difference": "...",\n'
        '    "cost_comparison": "...",\n'
        '    "coverage_comparison": "...",\n'
        '    "who_wins_cost": "policy1 or policy2 or tie",\n'
        '    "who_wins_coverage": "policy1 or policy2 or tie",\n'
        '    "who_wins_overall": "policy1 or policy2 or tie",\n'
        '    "bottom_line": "..."\n'
        "  }\n"
        "}\n\n"
        "Do NOT include any text outside the JSON object."
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_plain_summary(
    comparison_result: dict,
    policy1_name: str,
    policy2_name: str,
) -> dict:
    """Generate a plain-English consumer summary of a policy comparison result.

    Calls the Groq LLM to produce jargon-free summaries of each policy and a
    comparison narrative.  Applies post-processing to validate who_wins fields,
    strip markdown, compute word counts, apply fallbacks for empty fields, and
    attach metadata.  Raises ValueError on Groq API failure or invalid JSON.
    """
    compact = _compact_for_summary(comparison_result)
    prompt = _build_prompt(compact, policy1_name, policy2_name)

    logger.info(
        "Generating plain summary for '%s' vs '%s'",
        policy1_name,
        policy2_name,
    )

    client = Groq(api_key=settings.GROQ_API_KEY)

    try:
        response = client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            response_format={"type": "json_object"},
            max_tokens=3000,
        )
    except Exception as exc:
        raise ValueError(f"Groq API request failed: {exc}") from exc

    raw: str = response.choices[0].message.content or ""
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        inner = [line for line in cleaned.splitlines() if not line.startswith("```")]
        cleaned = "\n".join(inner).strip()

    try:
        payload: Dict[str, Any] = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Groq returned invalid JSON: {exc}") from exc

    p1: dict = payload.get("policy1_summary", {})
    p2: dict = payload.get("policy2_summary", {})
    cs: dict = payload.get("comparison_summary", {})

    _apply_markdown_strip(p1, p2, cs)
    _validate_winners(cs)
    _apply_fallbacks(p1, p2, cs, comparison_result, policy1_name, policy2_name)
    _check_word_limits(p1, p2, cs)

    text_fields = [
        *(v for v in p1.values() if isinstance(v, str)),
        *(v for v in p2.values() if isinstance(v, str)),
        *(v for v in cs.values() if isinstance(v, str)),
    ]
    word_count = sum(_word_count(t) for t in text_fields)
    reading_time = word_count // 3

    cs["reading_time_seconds"] = reading_time

    generated_at = datetime.now(timezone.utc).isoformat()

    logger.info(
        "Plain summary generation complete: word_count=%d, reading_time_seconds=%d",
        word_count,
        reading_time,
    )

    return {
        "comparison_id": 0,
        "policy1_name": policy1_name,
        "policy2_name": policy2_name,
        "policy1_summary": p1,
        "policy2_summary": p2,
        "comparison_summary": cs,
        "readability_level": "grade_6",
        "generated_at": generated_at,
        "word_count": word_count,
    }
