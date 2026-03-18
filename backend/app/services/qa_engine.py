"""
qa_engine.py
============
Uses the Groq LLM to answer natural language questions about a stored
comparison result.  The full comparison JSON is embedded into the prompt
as context so the model can reason over coverage, exclusions, premiums,
and summary sections.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from app.services.llm_client import llm_chat_completion, resolve_llm_provider

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

_QA_SYSTEM_PROMPT = """\
You are an expert insurance policy analyst. A user has a question about a
side-by-side comparison of two insurance policies. The full comparison data
is provided below as JSON.

Answer the user's question clearly and concisely based solely on the
information present in the comparison data.

Return ONLY a valid JSON object with exactly these keys:
{
  "answer": "your answer as a clear, readable string",
  "confidence": "high" | "medium" | "low",
  "relevant_sections": ["coverage", "exclusions", "premiums", "summary"]
}

Rules:
- "confidence" must reflect how directly the comparison data answers the question.
- "relevant_sections" must list only those sections that were actually used to form the answer.
- Do NOT wrap the JSON in markdown fences or add any text outside the JSON object.
"""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def answer_question(
    comparison_result: Dict[str, Any],
    question: str,
    llm_provider: Optional[str] = None,
) -> Dict[str, Any]:
    """Answer a natural language question about a comparison result.

    Sends the comparison_result JSON and the user's question to the Groq LLM
    and returns a structured dict with keys ``answer``, ``confidence``, and
    ``relevant_sections``.  Falls back to returning the raw response text with
    ``confidence="low"`` if the model output cannot be parsed as JSON.
    """
    selected_provider = resolve_llm_provider(llm_provider)

    user_message = (
        f"Comparison data:\n{json.dumps(comparison_result, indent=2)}\n\n"
        f"Question: {question}"
    )

    logger.info("Sending QA request to %s for question: %.80s", selected_provider, question)

    try:
        raw_text = llm_chat_completion(
            messages=[
                {"role": "system", "content": _QA_SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            provider=selected_provider,
            temperature=0.2,
            json_mode=True,
            max_tokens=1200,
        )
    except Exception as exc:
        raise ValueError(f"LLM API request failed: {exc}") from exc

    logger.debug("Raw QA response: %.200s", raw_text)

    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        inner_lines = [line for line in cleaned.splitlines() if not line.startswith("```")]
        cleaned = "\n".join(inner_lines).strip()

    try:
        payload: Dict[str, Any] = json.loads(cleaned)
    except json.JSONDecodeError:
        logger.warning("JSON parse failed for QA response; returning raw text as answer")
        payload = {
            "answer": raw_text.strip(),
            "confidence": "low",
            "relevant_sections": [],
        }

    return payload
