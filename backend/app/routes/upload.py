"""
routes/upload.py
================
Handles uploading two plain-text (.txt) policy documents, parsing them
with the Groq LLM, and triggering a comparison – all in a single request.
"""
from __future__ import annotations

import asyncio
import logging
import os
import uuid
from typing import List, Optional

import aiofiles
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.db_models import Comparison, ComparisonStatus, ParseStatus, Policy, UploadSession
from app.models.schemas import (
    UploadCompareResponse,
)
from app.services.comparison_engine import compare_policies
from app.services.text_parser import ParsedPolicy, PolicyItem, PremiumInfo, parse_policy

logger = logging.getLogger(__name__)
router = APIRouter()

_ALLOWED_MIME = {"text/plain", "application/octet-stream"}
_ALLOWED_EXT = {".txt"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _validate_upload(file: UploadFile) -> None:
    """Raise HTTPException for invalid uploads."""
    ext = os.path.splitext(file.filename or "")[-1].lower()
    if ext not in _ALLOWED_EXT:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Only plain-text (.txt) files are accepted. Received extension: '{ext}'",
        )


async def _save_upload(file: UploadFile) -> tuple[str, int]:
    """Persist uploaded file to disk; return (absolute_path, file_size_bytes)."""
    uid = uuid.uuid4().hex
    ext = os.path.splitext(file.filename or "unnamed")[-1].lower() or ".txt"
    safe_name = f"{uid}{ext}"
    dest = os.path.join(settings.upload_path, safe_name)

    chunk_size = 1024 * 256  # 256 KB chunks
    total = 0
    async with aiofiles.open(dest, "wb") as out:
        while True:
            chunk = await file.read(chunk_size)
            if not chunk:
                break
            total += len(chunk)
            if total > settings.max_file_size_bytes:
                await out.close()
                os.unlink(dest)
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"File exceeds maximum allowed size of {settings.MAX_FILE_SIZE_MB} MB",
                )
            await out.write(chunk)

    return dest, total


def _save_policy_to_db(db: Session, file: UploadFile, file_path: str, file_size: int) -> Policy:
    policy = Policy(
        filename=os.path.basename(file_path),
        original_name=file.filename or "unknown.txt",
        file_path=file_path,
        file_size=file_size,
        mime_type=file.content_type or "text/plain",
        parse_status=ParseStatus.PENDING,
    )
    db.add(policy)
    db.flush()  # get ID without full commit
    return policy


def _parse_and_update(db: Session, policy: Policy, llm_provider: Optional[str] = None) -> None:
    """Parse the PDF and update the DB row; does NOT commit."""
    policy.parse_status = ParseStatus.PROCESSING
    db.flush()
    try:
        parsed = parse_policy(policy.file_path, llm_provider=llm_provider)
        policy.extracted_text = parsed.raw_text[:16_000_000]  # guard LONGTEXT limit
        policy.parsed_data = {
            "coverage_items": [
                {"text": i.text, "amount": i.amount, "limit": i.limit}
                for i in parsed.coverage_items
            ],
            "exclusion_items": [
                {"text": i.text, "amount": i.amount, "limit": i.limit}
                for i in parsed.exclusion_items
            ],
            "premium_info": {
                "annual_premium": parsed.premium_info.annual_premium,
                "monthly_premium": parsed.premium_info.monthly_premium,
                "deductible": parsed.premium_info.deductible,
                "copay": parsed.premium_info.copay,
                "coinsurance": parsed.premium_info.coinsurance,
                "out_of_pocket_max": parsed.premium_info.out_of_pocket_max,
                "additional_fees": parsed.premium_info.additional_fees,
            },
        }
        policy.parse_status = ParseStatus.COMPLETED
    except Exception as exc:
        policy.parse_status = ParseStatus.FAILED
        policy.parse_error = str(exc)
        logger.error("Parse failed for policy %s: %s", policy.id, exc)
        raise


def _rebuild_parsed_policy(policy_row: Policy) -> ParsedPolicy:
    """
    Reconstruct a ParsedPolicy dataclass from a persisted Policy ORM row.

    Reads the stored parsed_data JSON and re-hydrates coverage_items,
    exclusion_items, and premium_info into the appropriate dataclasses.
    """
    pd = policy_row.parsed_data or {}
    pp = ParsedPolicy(
        filename=policy_row.original_name,
        raw_text=policy_row.extracted_text or "",
    )
    pp.coverage_items = [
        PolicyItem(text=i["text"], amount=i.get("amount"), limit=i.get("limit"))
        for i in pd.get("coverage_items", [])
    ]
    pp.exclusion_items = [
        PolicyItem(text=i["text"], amount=i.get("amount"), limit=i.get("limit"))
        for i in pd.get("exclusion_items", [])
    ]
    pi = pd.get("premium_info", {})
    pp.premium_info = PremiumInfo(
        annual_premium=pi.get("annual_premium"),
        monthly_premium=pi.get("monthly_premium"),
        deductible=pi.get("deductible"),
        copay=pi.get("copay"),
        coinsurance=pi.get("coinsurance"),
        out_of_pocket_max=pi.get("out_of_pocket_max"),
        additional_fees=pi.get("additional_fees", []),
    )
    return pp


def _is_tpd_exhausted(exc: Exception) -> bool:
    """
    Return True when the exception is a Groq daily-token-quota (TPD) 429.

    Detects the "tokens per day" variant of rate-limit errors, which cannot
    be resolved by waiting a few seconds and should abort all remaining calls.
    """
    msg = str(exc).lower()
    return "tokens per day" in msg or "\"type\": \"tokens\"" in msg


def _avg_similarity_from_result(comparison_result: dict) -> float:
    """
    Compute mean similarity_score from coverage.common and exclusions.common.

    Returns 0.0 if no scored items exist or comparison_result is None.
    """
    if not comparison_result:
        return 0.0
    scores: list[float] = []
    for section in ("coverage", "exclusions"):
        for item in comparison_result.get(section, {}).get("common", []):
            s = item.get("similarity_score")
            if isinstance(s, (int, float)):
                scores.append(float(s))
    return sum(scores) / len(scores) if scores else 0.0


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/upload-compare",
    response_model=UploadCompareResponse,
    status_code=status.HTTP_200_OK,
    summary="Upload two plain-text policy files and receive a comparison",
)
async def upload_and_compare(
    request: Request,
    policy1: UploadFile = File(..., description="First insurance policy PDF"),
    policy2: UploadFile = File(..., description="Second insurance policy PDF"),
    llm_provider: Optional[str] = Form(default=None, description="LLM provider override: groq | ollama"),
    db: Session = Depends(get_db),
):
    _validate_upload(policy1)
    _validate_upload(policy2)

    session_id = uuid.uuid4().hex
    ip = request.client.host if request.client else "unknown"

    # --- Create upload session ---
    session = UploadSession(
        session_id=session_id,
        policy1_filename=policy1.filename,
        policy2_filename=policy2.filename,
        status="uploading",
        ip_address=ip,
    )
    db.add(session)
    db.flush()

    # --- Save files ---
    try:
        path1, size1 = await _save_upload(policy1)
        path2, size2 = await _save_upload(policy2)
    except HTTPException:
        session.status = "failed"
        session.error_message = "File upload failed"
        db.commit()
        raise

    # --- Persist policy rows ---
    p1_row = _save_policy_to_db(db, policy1, path1, size1)
    p2_row = _save_policy_to_db(db, policy2, path2, size2)
    session.policy1_id = p1_row.id
    session.policy2_id = p2_row.id
    session.status = "processing"
    db.flush()

    # --- Parse both policies ---
    parse_errors = []
    try:
        _parse_and_update(db, p1_row, llm_provider=llm_provider)
    except Exception as exc:
        parse_errors.append(f"Policy 1 parse error: {exc}")

    try:
        _parse_and_update(db, p2_row, llm_provider=llm_provider)
    except Exception as exc:
        parse_errors.append(f"Policy 2 parse error: {exc}")

    if parse_errors:
        cmp_row = Comparison(
            policy1_id=p1_row.id,
            policy2_id=p2_row.id,
            status=ComparisonStatus.FAILED,
            error_message="; ".join(parse_errors),
        )
        db.add(cmp_row)
        session.status = "failed"
        session.error_message = "; ".join(parse_errors)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="; ".join(parse_errors),
        )

    # --- Compare ---
    cmp_row = Comparison(
        policy1_id=p1_row.id,
        policy2_id=p2_row.id,
        status=ComparisonStatus.PROCESSING,
    )
    db.add(cmp_row)
    db.flush()

    try:
        result = compare_policies(
            _rebuild_parsed_policy(p1_row),
            _rebuild_parsed_policy(p2_row),
            llm_provider=llm_provider,
        )
        cmp_row.comparison_result = result
        cmp_row.status = ComparisonStatus.COMPLETED
    except Exception as exc:
        cmp_row.status = ComparisonStatus.FAILED
        cmp_row.error_message = str(exc)
        session.status = "failed"
        session.error_message = str(exc)
        db.commit()
        logger.error("Comparison failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Comparison failed: {exc}",
        )

    session.comparison_id = cmp_row.id
    session.status = "completed"
    db.commit()
    db.refresh(p1_row)
    db.refresh(p2_row)
    db.refresh(cmp_row)

    return UploadCompareResponse(
        session_id=session_id,
        policy1=p1_row,
        policy2=p2_row,
        comparison=cmp_row,
    )
