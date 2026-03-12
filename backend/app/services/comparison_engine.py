"""
comparison_engine.py
====================
Uses the Groq LLM to perform an intelligent side-by-side comparison of two
ParsedPolicy objects.  Both policies are already structured (extracted by
text_parser.py), so only the compact JSON representations are sent to
Groq â€“ keeping the prompt well within the model's token budget.

The function returns a dict that exactly matches the schema the frontend
ComparisonView component expects.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict

from groq import Groq

from app.config import settings
from app.services.text_parser import ParsedPolicy

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

_COMPARISON_PROMPT = """\
You are an expert insurance policy analyst. Compare the two insurance policies \
below and return a thorough, structured JSON comparison.

Return ONLY a valid JSON object â€“ no markdown fences, no explanation â€“ with \
exactly this structure:

{{
  "coverage": {{
    "common": [
      {{
        "item": "coverage topic / benefit name",
        "policy1_details": "how Policy 1 covers this (1-2 sentences)",
        "policy2_details": "how Policy 2 covers this (1-2 sentences)",
        "policy1_amount": "dollar limit from Policy 1 or null",
        "policy2_amount": "dollar limit from Policy 2 or null",
        "similarity_score": 0.95
      }}
    ],
    "only_in_policy1": [
      {{"text": "item description", "amount": null, "limit": null, "raw_context": null}}
    ],
    "only_in_policy2": [
      {{"text": "item description", "amount": null, "limit": null, "raw_context": null}}
    ]
  }},
  "exclusions": {{
    "common": [
      {{
        "item": "exclusion topic",
        "policy1_details": "how Policy 1 states this exclusion",
        "policy2_details": "how Policy 2 states this exclusion",
        "policy1_amount": null,
        "policy2_amount": null,
        "similarity_score": 0.9
      }}
    ],
    "only_in_policy1": [
      {{"text": "exclusion description", "amount": null, "limit": null, "raw_context": null}}
    ],
    "only_in_policy2": [
      {{"text": "exclusion description", "amount": null, "limit": null, "raw_context": null}}
    ]
  }},
  "premiums": {{
    "policy1": {{
      "annual_premium": "$X or null",
      "monthly_premium": "$X or null",
      "deductible": "$X or null",
      "copay": "$X or null",
      "coinsurance": "X% or null",
      "out_of_pocket_max": "$X or null",
      "additional_fees": []
    }},
    "policy2": {{
      "annual_premium": "$X or null",
      "monthly_premium": "$X or null",
      "deductible": "$X or null",
      "copay": "$X or null",
      "coinsurance": "X% or null",
      "out_of_pocket_max": "$X or null",
      "additional_fees": []
    }},
    "differences": [
      "plain-English sentence describing a specific premium/cost difference"
    ]
  }},
  "summary": {{
    "total_coverage_items_policy1": 0,
    "total_coverage_items_policy2": 0,
    "shared_coverage_items": 0,
    "total_exclusion_items_policy1": 0,
    "total_exclusion_items_policy2": 0,
    "shared_exclusion_items": 0,
    "policy1_advantages": [
      "plain-English advantage that Policy 1 has over Policy 2"
    ],
    "policy2_advantages": [
      "plain-English advantage that Policy 2 has over Policy 1"
    ],
    "premium_differences": [
      "brief premium difference summary"
    ]
  }}
}}

Rules:
- Classify items that cover the same topic in both policies as "common".
- Items that appear in only one policy go into the respective "only_in_policyX" list.
- similarity_score must be a float between 0.0 and 1.0.
- Be specific and accurate; base everything strictly on the data provided.
- Fill ALL numeric totals in "summary" correctly (count the arrays).
- Return ONLY the JSON object.

---

Policy 1 ({p1_name}):
{p1_data}

---

Policy 2 ({p2_name}):
{p2_data}
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _policy_to_dict(p: ParsedPolicy) -> dict:
    return {
        "coverage_items": [
            {"text": i.text, "amount": i.amount, "limit": i.limit}
            for i in p.coverage_items
        ],
        "exclusion_items": [
            {"text": i.text, "amount": i.amount, "limit": i.limit}
            for i in p.exclusion_items
        ],
        "premium_info": {
            "annual_premium": p.premium_info.annual_premium,
            "monthly_premium": p.premium_info.monthly_premium,
            "deductible": p.premium_info.deductible,
            "copay": p.premium_info.copay,
            "coinsurance": p.premium_info.coinsurance,
            "out_of_pocket_max": p.premium_info.out_of_pocket_max,
            "additional_fees": p.premium_info.additional_fees,
        },
    }


def _recalculate_summary(result: dict) -> None:
    """Guarantee summary counts match actual array lengths."""
    cov = result.get("coverage", {})
    exc = result.get("exclusions", {})
    summary = result.setdefault("summary", {})

    common_cov  = len(cov.get("common", []))
    only1_cov   = len(cov.get("only_in_policy1", []))
    only2_cov   = len(cov.get("only_in_policy2", []))
    common_exc  = len(exc.get("common", []))
    only1_exc   = len(exc.get("only_in_policy1", []))
    only2_exc   = len(exc.get("only_in_policy2", []))

    summary["shared_coverage_items"]          = common_cov
    summary["total_coverage_items_policy1"]   = common_cov + only1_cov
    summary["total_coverage_items_policy2"]   = common_cov + only2_cov
    summary["shared_exclusion_items"]         = common_exc
    summary["total_exclusion_items_policy1"]  = common_exc + only1_exc
    summary["total_exclusion_items_policy2"]  = common_exc + only2_exc

    summary.setdefault("policy1_advantages", [])
    summary.setdefault("policy2_advantages", [])
    summary.setdefault("premium_differences", [])


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compare_policies(policy1: ParsedPolicy, policy2: ParsedPolicy) -> Dict[str, Any]:
    """
    Compare two ParsedPolicy objects using Groq and return a JSON-serialisable
    dict matching the frontend's expected ComparisonResult schema.
    """
    if not settings.GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY is not set. Add it to your .env file.")

    client = Groq(api_key=settings.GROQ_API_KEY)

    prompt = _COMPARISON_PROMPT.format(
        p1_name=policy1.filename,
        p2_name=policy2.filename,
        p1_data=json.dumps(_policy_to_dict(policy1), indent=2),
        p2_data=json.dumps(_policy_to_dict(policy2), indent=2),
    )

    logger.info(
        "Sending comparison to Groq: '%s' vs '%s'",
        policy1.filename, policy2.filename,
    )

    try:
        response = client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            response_format={"type": "json_object"},
            max_tokens=8192,
        )
        result: dict = json.loads(response.choices[0].message.content)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Groq returned malformed JSON during comparison: {exc}") from exc
    except Exception as exc:
        raise ValueError(f"Groq API error during comparison: {exc}") from exc

    result["policy1_filename"] = policy1.filename
    result["policy2_filename"] = policy2.filename
    _recalculate_summary(result)

    logger.info(
        "Comparison done: %d shared coverage, %d shared exclusions",
        result["summary"]["shared_coverage_items"],
        result["summary"]["shared_exclusion_items"],
    )
    return result
