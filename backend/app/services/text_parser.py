"""
text_parser.py
==============
Reads a plain-text (.txt) insurance policy file and uses the Groq LLM API
to extract structured coverage, exclusions, and premium data.

The returned ParsedPolicy dataclass intentionally mirrors the old
pdf_parser interface so the rest of the codebase stays unchanged.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from app.services.llm_client import llm_chat_completion, resolve_llm_provider

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data structures  (identical interface to the old pdf_parser)
# ---------------------------------------------------------------------------

@dataclass
class PolicyItem:
    text: str
    amount: Optional[str] = None
    limit: Optional[str] = None
    raw_context: Optional[str] = None


@dataclass
class PremiumInfo:
    annual_premium: Optional[str] = None
    monthly_premium: Optional[str] = None
    deductible: Optional[str] = None
    copay: Optional[str] = None
    coinsurance: Optional[str] = None
    out_of_pocket_max: Optional[str] = None
    additional_fees: List[Dict] = field(default_factory=list)


@dataclass
class ParsedPolicy:
    filename: str
    raw_text: str = ""
    coverage_items: List[PolicyItem] = field(default_factory=list)
    exclusion_items: List[PolicyItem] = field(default_factory=list)
    premium_info: PremiumInfo = field(default_factory=PremiumInfo)


# ---------------------------------------------------------------------------
# Groq extraction prompt
# ---------------------------------------------------------------------------

_EXTRACTION_PROMPT = """\
You are an expert insurance policy analyst. Carefully read the insurance policy \
document provided below and extract ALL relevant information.

Return ONLY a valid JSON object – no markdown fences, no explanation – \
with exactly this structure:

{
  "coverage_items": [
    {
      "text": "concise description of what is covered (1-2 sentences)",
      "amount": "coverage limit as a string e.g. '$50,000' or null if not stated",
      "limit": "any sub-limit or condition, or null"
    }
  ],
  "exclusion_items": [
    {
      "text": "concise description of what is NOT covered / excluded (1-2 sentences)",
      "amount": null,
      "limit": null
    }
  ],
  "premium_info": {
    "annual_premium":    "e.g. '$1,200.00' or null",
    "monthly_premium":   "e.g. '$100.00' or null",
    "deductible":        "e.g. '$500.00' or null",
    "copay":             "e.g. '$25.00' or null",
    "coinsurance":       "e.g. '20%' or null",
    "out_of_pocket_max": "e.g. '$3,000.00' or null",
    "additional_fees": [
      {"label": "fee name / description", "amount": "$X.XX"}
    ]
  }
}

Rules:
- Extract EVERY coverage item and EVERY exclusion you can find.
- Keep each item text clear and self-contained.
- Preserve monetary values exactly as written in the document.
- If information is not present, use null (not an empty string).
- Return ONLY the JSON object.

Insurance Policy Document:
"""

_MAX_CHARS = 28_000   # ~7 000 tokens – well within llama-3.3-70b-versatile's window


# ---------------------------------------------------------------------------
# Groq API call
# ---------------------------------------------------------------------------

def _extract_via_llm(raw_text: str, llm_provider: Optional[str] = None) -> dict:
    selected_provider = resolve_llm_provider(llm_provider)

    # Truncate very long documents to stay within token budget
    text = raw_text
    if len(text) > _MAX_CHARS:
        logger.warning(
            "Policy text truncated from %d to %d chars for Groq extraction",
            len(text), _MAX_CHARS,
        )
        text = text[:_MAX_CHARS] + "\n\n[Document truncated for processing]"

    content = llm_chat_completion(
        messages=[{"role": "user", "content": _EXTRACTION_PROMPT + text}],
        provider=selected_provider,
        temperature=0.0,
        json_mode=True,
        max_tokens=4096,
    )
    return json.loads(content)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_policy(file_path: str, llm_provider: Optional[str] = None) -> ParsedPolicy:
    """
    Read a .txt policy file and return a ParsedPolicy populated by Groq.
    Raises ValueError on unrecoverable failures.
    """
    filename = os.path.basename(file_path)
    selected_provider = resolve_llm_provider(llm_provider)
    logger.info("Parsing policy via %s: %s", selected_provider, filename)

    # Read the file
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            raw_text = f.read()
    except OSError as exc:
        raise ValueError(f"Could not read file '{filename}': {exc}") from exc

    if not raw_text.strip():
        raise ValueError(f"The uploaded file '{filename}' is empty.")

    # Extract structured data via selected LLM provider
    try:
        data = _extract_via_llm(raw_text, llm_provider=selected_provider)
    except json.JSONDecodeError as exc:
        raise ValueError(f"LLM returned malformed JSON for '{filename}': {exc}") from exc
    except Exception as exc:
        raise ValueError(f"LLM API error while parsing '{filename}': {exc}") from exc

    # Build ParsedPolicy from Groq's response
    policy = ParsedPolicy(filename=filename, raw_text=raw_text)

    for item in data.get("coverage_items") or []:
        txt = (item.get("text") or "").strip()
        if txt:
            policy.coverage_items.append(
                PolicyItem(
                    text=txt,
                    amount=item.get("amount") or None,
                    limit=item.get("limit") or None,
                    raw_context=txt[:200],
                )
            )

    for item in data.get("exclusion_items") or []:
        txt = (item.get("text") or "").strip()
        if txt:
            policy.exclusion_items.append(
                PolicyItem(
                    text=txt,
                    amount=item.get("amount") or None,
                    limit=item.get("limit") or None,
                    raw_context=txt[:200],
                )
            )

    pi = data.get("premium_info") or {}
    policy.premium_info = PremiumInfo(
        annual_premium=pi.get("annual_premium") or None,
        monthly_premium=pi.get("monthly_premium") or None,
        deductible=pi.get("deductible") or None,
        copay=pi.get("copay") or None,
        coinsurance=pi.get("coinsurance") or None,
        out_of_pocket_max=pi.get("out_of_pocket_max") or None,
        additional_fees=pi.get("additional_fees") or [],
    )

    logger.info(
        "%s parsed '%s': %d coverage items, %d exclusions",
        selected_provider,
        filename, len(policy.coverage_items), len(policy.exclusion_items),
    )
    return policy
