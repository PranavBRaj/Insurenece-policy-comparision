"""
pdf_parser.py
=============
Extracts structured insurance-policy content from a PDF file.

Strategy
--------
1. Use pdfplumber (preserves spatial layout, handles tables) with a fallback
   to pypdf for text-only extraction.
2. Attempt to locate section boundaries via regex header patterns.
3. If no sections are found, fall back to a keyword-scan of the full text.
4. Within each section, pull bullet/numbered list items and monetary amounts.
"""
from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import pdfplumber
from pypdf import PdfReader

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data structures
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
    additional_fees: List[Dict[str, str]] = field(default_factory=list)


@dataclass
class ParsedPolicy:
    filename: str
    raw_text: str = ""
    coverage_items: List[PolicyItem] = field(default_factory=list)
    exclusion_items: List[PolicyItem] = field(default_factory=list)
    premium_info: PremiumInfo = field(default_factory=PremiumInfo)


# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

_SECTION_HEADERS: Dict[str, List[str]] = {
    "coverage": [
        r"(?i)(?:section\s+[\dIVXivx]+\s*[.:\-]?\s*)?"
        r"(?:coverages?|what\s+(?:we\s+)?(?:do\s+)?cover|insuring\s+agreements?|"
        r"covered\s+(?:perils|losses|events|services)|schedule\s+of\s+(?:benefits|coverages?)|"
        r"benefit\s+summary|benefits\s+(?:covered|payable))",
    ],
    "exclusions": [
        r"(?i)(?:section\s+[\dIVXivx]+\s*[.:\-]?\s*)?"
        r"(?:exclusions?|what\s+(?:we\s+do\s+)?not\s+cover|not\s+covered|"
        r"exceptions?\s+(?:to\s+coverage)?|limitations?\s+(?:and\s+exclusions?)?|"
        r"coverage\s+(?:exclusions?|limitations?))",
    ],
    "premiums": [
        r"(?i)(?:section\s+[\dIVXivx]+\s*[.:\-]?\s*)?"
        r"(?:premiums?|pricing|cost\s+summary|fees?\s+(?:and\s+charges?)?|"
        r"rates?\s+(?:schedule|information)|payment\s+(?:schedule|information|options?)|"
        r"declarations?\s+page|policy\s+(?:declarations?|summary))",
    ],
}

_DOLLAR_RE = re.compile(r"\$[\d,]+(?:\.\d{1,2})?")
_LIMIT_RE = re.compile(
    r"(?i)(?:up\s+to\s+|maximum\s+(?:of\s+)?)?\$[\d,]+(?:\.\d{1,2})?"
    r"(?:\s*(?:per\s+(?:occurrence|accident|claim|year|person|day)|"
    r"(?:aggregate|maximum|limit)\s*(?:of\s*)?))?",
    re.IGNORECASE,
)
_PERCENT_RE = re.compile(r"\d+(?:\.\d+)?\s*%")
_DEDUCTIBLE_RE = re.compile(
    r"(?i)deductible[s\s]*(?:is|:|of|=)?\s*(\$[\d,]+(?:\.\d{1,2})?|\d+(?:\.\d+)?\s*%)"
)
_COPAY_RE = re.compile(
    r"(?i)co[\-]?pay(?:ment)?[s\s]*(?:is|:|of|=)?\s*(\$[\d,]+(?:\.\d{1,2})?|\d+(?:\.\d+)?\s*%)"
)
_COINSURANCE_RE = re.compile(
    r"(?i)co[\-]?insurance[s\s]*(?:is|:|of|=)?\s*(\$[\d,]+(?:\.\d{1,2})?|\d+(?:\.\d+)?\s*%)"
)
_ANNUAL_PREMIUM_RE = re.compile(
    r"(?i)(?:annual|yearly|total)\s+premium[s\s]*(?:is|:|of|=)?\s*(\$[\d,]+(?:\.\d{1,2})?)"
)
_MONTHLY_PREMIUM_RE = re.compile(
    r"(?i)monthly\s+(?:premium|payment)[s\s]*(?:is|:|of|=)?\s*(\$[\d,]+(?:\.\d{1,2})?)"
)
_OOP_MAX_RE = re.compile(
    r"(?i)out[\-\s]+of[\-\s]+pocket\s+(?:maximum|max|limit)[s\s]*(?:is|:|of|=)?\s*"
    r"(\$[\d,]+(?:\.\d{1,2})?)"
)

# Bullet/numbered item starters
_ITEM_RE = re.compile(
    r"^(?:\s*(?:[\•\-\*\u2022\u2013\u2014]|\d{1,3}[.)]\s|\([a-z]\)\s))\s*(.+)",
    re.MULTILINE,
)


# ---------------------------------------------------------------------------
# Text extraction
# ---------------------------------------------------------------------------

def _extract_text_pdfplumber(path: str) -> str:
    """Primary extractor – pdfplumber handles layout and tables well."""
    pages: List[str] = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text = page.extract_text(x_tolerance=3, y_tolerance=3)
            if text:
                pages.append(text)
            # Also attempt to extract tables and append them as plain text
            for table in page.extract_tables():
                for row in table:
                    if row:
                        clean_row = " | ".join(cell or "" for cell in row)
                        pages.append(clean_row)
    return "\n".join(pages)


def _extract_text_pypdf(path: str) -> str:
    """Fallback extractor using pypdf."""
    reader = PdfReader(path)
    return "\n".join(
        page.extract_text() or "" for page in reader.pages
    )


def extract_text_from_pdf(path: str) -> str:
    """Try pdfplumber first; fall back to pypdf."""
    text = ""
    try:
        text = _extract_text_pdfplumber(path)
    except Exception as exc:
        logger.warning("pdfplumber failed (%s), trying pypdf", exc)

    if not text.strip():
        try:
            text = _extract_text_pypdf(path)
        except Exception as exc:
            logger.error("pypdf also failed: %s", exc)
            raise ValueError(f"Could not extract text from PDF: {exc}") from exc

    if not text.strip():
        raise ValueError(
            "The PDF appears to contain no extractable text. "
            "Scanned/image-only PDFs require OCR (not supported in this version)."
        )
    return text


# ---------------------------------------------------------------------------
# Section splitting
# ---------------------------------------------------------------------------

def _find_section_boundaries(text: str) -> Dict[str, Tuple[int, int]]:
    """
    Returns a dict mapping section name → (start_char, end_char) in *text*.
    If a section is not found, it is omitted from the result.
    """
    boundaries: Dict[str, int] = {}

    for section_name, patterns in _SECTION_HEADERS.items():
        for pattern in patterns:
            for m in re.finditer(pattern, text):
                # Pick the earliest match per section
                if section_name not in boundaries or m.start() < boundaries[section_name]:
                    boundaries[section_name] = m.start()
            if section_name in boundaries:
                break

    if not boundaries:
        return {}

    # Sort found sections by position
    ordered = sorted(boundaries.items(), key=lambda kv: kv[1])
    result: Dict[str, Tuple[int, int]] = {}
    for i, (name, start) in enumerate(ordered):
        end = ordered[i + 1][1] if i + 1 < len(ordered) else len(text)
        result[name] = (start, end)

    return result


def _get_section_text(text: str, section_boundaries: Dict[str, Tuple[int, int]], name: str) -> str:
    if name not in section_boundaries:
        return ""
    start, end = section_boundaries[name]
    return text[start:end]


# ---------------------------------------------------------------------------
# Item extraction helpers
# ---------------------------------------------------------------------------

def _extract_items_from_text(section_text: str, max_items: int = 60) -> List[PolicyItem]:
    """
    Extract meaningful items from a section of policy text.
    Priority: bullet/numbered items → short sentences (≤ 180 chars).
    """
    items: List[PolicyItem] = []
    seen: set = set()

    # 1. Bullet / numbered items
    for m in _ITEM_RE.finditer(section_text):
        raw = m.group(1).strip()
        if len(raw) < 8:
            continue
        key = raw.lower()[:80]
        if key in seen:
            continue
        seen.add(key)
        amount = _first_match(_DOLLAR_RE, raw)
        limit = _first_match(_LIMIT_RE, raw)
        items.append(PolicyItem(text=raw, amount=amount, limit=limit, raw_context=raw[:200]))

    # 2. Sentences / lines if we didn't find many bullet items
    if len(items) < 5:
        for line in section_text.splitlines():
            line = line.strip()
            if len(line) < 15 or len(line) > 300:
                continue
            key = line.lower()[:80]
            if key in seen:
                continue
            # Skip lines that look like headers (all caps or very short)
            if line.isupper() and len(line) < 50:
                continue
            seen.add(key)
            amount = _first_match(_DOLLAR_RE, line)
            limit = _first_match(_LIMIT_RE, line)
            items.append(PolicyItem(text=line, amount=amount, limit=limit, raw_context=line[:200]))
            if len(items) >= max_items:
                break

    return items[:max_items]


def _first_match(pattern: re.Pattern, text: str) -> Optional[str]:
    m = pattern.search(text)
    return m.group(0) if m else None


# ---------------------------------------------------------------------------
# Premium extraction
# ---------------------------------------------------------------------------

def _extract_premium_info(text: str) -> PremiumInfo:
    info = PremiumInfo()

    m = _ANNUAL_PREMIUM_RE.search(text)
    if m:
        info.annual_premium = m.group(1)

    m = _MONTHLY_PREMIUM_RE.search(text)
    if m:
        info.monthly_premium = m.group(1)

    m = _DEDUCTIBLE_RE.search(text)
    if m:
        info.deductible = m.group(1)

    m = _COPAY_RE.search(text)
    if m:
        info.copay = m.group(1)

    m = _COINSURANCE_RE.search(text)
    if m:
        info.coinsurance = m.group(1)

    m = _OOP_MAX_RE.search(text)
    if m:
        info.out_of_pocket_max = m.group(1)

    # Generic dollar amounts not captured above → additional_fees
    if not info.annual_premium and not info.monthly_premium:
        amounts_found = _DOLLAR_RE.findall(text)
        for amt in amounts_found[:5]:
            # Grab 60-char context around each amount
            idx = text.find(amt)
            snippet = text[max(0, idx - 30): idx + len(amt) + 30].strip()
            info.additional_fees.append({"label": snippet, "amount": amt})

    return info


# ---------------------------------------------------------------------------
# Keyword-scan fallback (when no section headers are found)
# ---------------------------------------------------------------------------

_COVERAGE_KEYWORDS = re.compile(
    r"(?i)\b(cover(?:age|ed)|benefit|protect(?:ion|ed)|insur(?:ed|ance)|"
    r"reimburse|compensat|liability|loss(?:es)?)\b"
)
_EXCLUSION_KEYWORDS = re.compile(
    r"(?i)\b(exclud|exclusion|not\s+cover|except(?:ion)?|does\s+not\s+apply|"
    r"limitation|void|waiv)\b"
)


def _keyword_scan(text: str) -> Tuple[List[PolicyItem], List[PolicyItem]]:
    """
    Fallback: scan every meaningful line and classify it as coverage or exclusion
    based on keyword presence.
    """
    coverage_items: List[PolicyItem] = []
    exclusion_items: List[PolicyItem] = []
    seen: set = set()

    for line in text.splitlines():
        line = line.strip()
        if len(line) < 20 or len(line) > 400:
            continue
        key = line.lower()[:80]
        if key in seen:
            continue
        seen.add(key)

        amount = _first_match(_DOLLAR_RE, line)
        limit = _first_match(_LIMIT_RE, line)
        item = PolicyItem(text=line, amount=amount, limit=limit, raw_context=line[:200])

        if _EXCLUSION_KEYWORDS.search(line):
            exclusion_items.append(item)
        elif _COVERAGE_KEYWORDS.search(line):
            coverage_items.append(item)

        if len(coverage_items) >= 50 and len(exclusion_items) >= 50:
            break

    return coverage_items, exclusion_items


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_policy(file_path: str) -> ParsedPolicy:
    """
    Main entry-point: given a path to a PDF file, return a ParsedPolicy.
    Raises ValueError on unrecoverable parse failures.
    """
    filename = os.path.basename(file_path)
    logger.info("Parsing policy: %s", filename)

    raw_text = extract_text_from_pdf(file_path)

    policy = ParsedPolicy(filename=filename, raw_text=raw_text)

    section_boundaries = _find_section_boundaries(raw_text)
    logger.debug("Sections found: %s", list(section_boundaries.keys()))

    if section_boundaries:
        cov_text = _get_section_text(raw_text, section_boundaries, "coverage")
        exc_text = _get_section_text(raw_text, section_boundaries, "exclusions")
        prm_text = _get_section_text(raw_text, section_boundaries, "premiums")

        policy.coverage_items = _extract_items_from_text(cov_text) if cov_text else []
        policy.exclusion_items = _extract_items_from_text(exc_text) if exc_text else []
        policy.premium_info = _extract_premium_info(prm_text if prm_text else raw_text)
    else:
        logger.info("No section headers found; falling back to keyword scan.")
        policy.coverage_items, policy.exclusion_items = _keyword_scan(raw_text)
        policy.premium_info = _extract_premium_info(raw_text)

    logger.info(
        "Parsed '%s': %d coverage items, %d exclusion items",
        filename,
        len(policy.coverage_items),
        len(policy.exclusion_items),
    )
    return policy
