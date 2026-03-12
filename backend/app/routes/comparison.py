"""
routes/comparison.py
====================
Endpoints for retrieving comparison results and upload history.
"""
from __future__ import annotations

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.db_models import Comparison, ComparisonStatus, Policy, UploadSession
from app.models.schemas import (
    AnomalyDetectionResponse,
    AskQuestionRequest,
    AskQuestionResponse,
    ComparisonListItem,
    ComparisonResponse,
    HistoryItem,
    PlainSummaryResponse,
    RecommendationResponse,
    UserProfileInput,
    VisualisationResponse,
)
from app.services.anomaly_engine import run_anomaly_detection
from app.services.plain_summary_engine import generate_plain_summary
from app.services.qa_engine import answer_question
from app.services.pdf_exporter import generate_comparison_pdf
from app.services.recommendation_engine import generate_recommendations
from app.services.visualisation_engine import build_visualisation_data

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Comparisons
# ---------------------------------------------------------------------------

@router.get(
    "/comparisons",
    response_model=List[ComparisonListItem],
    summary="List all comparisons (most recent first)",
)
def list_comparisons(skip: int = 0, limit: int = 20, db: Session = Depends(get_db)):
    if limit > 100:
        limit = 100
    rows = (
        db.query(Comparison)
        .order_by(Comparison.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    result = []
    for row in rows:
        p1 = db.get(Policy, row.policy1_id)
        p2 = db.get(Policy, row.policy2_id)
        result.append(
            ComparisonListItem(
                id=row.id,
                policy1_id=row.policy1_id,
                policy2_id=row.policy2_id,
                policy1_filename=p1.original_name if p1 else None,
                policy2_filename=p2.original_name if p2 else None,
                status=row.status,
                created_at=row.created_at,
            )
        )
    return result


@router.get(
    "/comparisons/{comparison_id}/visualisation",
    response_model=VisualisationResponse,
    summary="Get pre-computed chart-ready visualisation data for a comparison",
)
def get_comparison_visualisation(
    comparison_id: int,
    db: Session = Depends(get_db),
) -> VisualisationResponse:
    """Return all chart datasets derived from a completed comparison result.

    Computes coverage bar, donut, exclusions donut, premium bar, and
    similarity histogram data without any external API calls.
    """
    row = db.get(Comparison, comparison_id)
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Comparison {comparison_id} not found",
        )
    if row.status != ComparisonStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Comparison is not yet completed",
        )

    p1 = db.get(Policy, row.policy1_id)
    p2 = db.get(Policy, row.policy2_id)
    result = row.comparison_result or {}
    p1_name = result.get("policy1_filename") or (p1.original_name if p1 else f"Policy {row.policy1_id}")
    p2_name = result.get("policy2_filename") or (p2.original_name if p2 else f"Policy {row.policy2_id}")

    data = build_visualisation_data(result, p1_name, p2_name)
    return VisualisationResponse(**data)


@router.get(
    "/comparisons/{comparison_id}/export.pdf",
    summary="Download a formatted PDF comparison report",
    response_class=Response,
)
def export_comparison_pdf(
    comparison_id: int,
    db: Session = Depends(get_db),
) -> Response:
    """Generate and return a downloadable PDF report for a completed comparison.

    Validates that the comparison exists and is in COMPLETED status, then
    delegates PDF generation to pdf_exporter.generate_comparison_pdf and
    streams the bytes back as an attachment.
    """
    row = db.get(Comparison, comparison_id)
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Comparison {comparison_id} not found",
        )
    if row.status != ComparisonStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Comparison is not yet completed",
        )

    try:
        pdf_bytes = generate_comparison_pdf(
            comparison_result=row.comparison_result or {},
            comparison_id=row.id,
            created_at=row.created_at,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="comparison_{comparison_id}.pdf"'
        },
    )


@router.get(
    "/comparisons/{comparison_id}",
    response_model=ComparisonResponse,
    summary="Retrieve a specific comparison result",
)
def get_comparison(comparison_id: int, db: Session = Depends(get_db)):
    row = db.get(Comparison, comparison_id)
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Comparison {comparison_id} not found",
        )
    return row


@router.post(
    "/comparisons/{comparison_id}/ask",
    response_model=AskQuestionResponse,
    summary="Ask a natural language question about a comparison result",
)
def ask_comparison_question(
    comparison_id: int,
    body: AskQuestionRequest,
    db: Session = Depends(get_db),
) -> AskQuestionResponse:
    """Answer a natural language question using the stored comparison result as context.

    Returns a structured answer with a confidence level and the list of
    comparison sections that were relevant to forming the answer.
    """
    row = db.get(Comparison, comparison_id)
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Comparison {comparison_id} not found",
        )
    if row.status != ComparisonStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Comparison {comparison_id} is not completed (status: {row.status})",
        )
    if row.comparison_result is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Comparison {comparison_id} has no result data",
        )

    try:
        payload = answer_question(row.comparison_result, body.question)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )

    return AskQuestionResponse(
        question=body.question,
        answer=payload.get("answer", ""),
        confidence=payload.get("confidence"),
        relevant_sections=payload.get("relevant_sections", []),
    )


@router.post(
    "/comparisons/{comparison_id}/recommend",
    response_model=RecommendationResponse,
    summary="Get LLM-powered policy recommendations tailored to a user profile",
)
def recommend_policy(
    comparison_id: int,
    body: UserProfileInput,
    db: Session = Depends(get_db),
) -> RecommendationResponse:
    """Analyse a completed comparison and recommend the better-suited policy.

    Calls the Groq LLM to generate a recommendation tailored to the submitted
    user profile and four standard demographic profiles (Young Single
    Professional, Family with Children, Senior / Retired, Chronic Condition
    Management).  An overall winner is determined by majority vote across all
    five profiles.
    """
    row = db.get(Comparison, comparison_id)
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Comparison {comparison_id} not found",
        )
    if row.status != ComparisonStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Comparison is not yet completed",
        )
    if row.comparison_result is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No result data",
        )

    p1 = db.get(Policy, row.policy1_id)
    p2 = db.get(Policy, row.policy2_id)
    result = row.comparison_result

    p1_name = (
        (p1.original_name if p1 else None)
        or result.get("policy1_filename")
        or f"Policy {row.policy1_id}"
    )
    p2_name = (
        (p2.original_name if p2 else None)
        or result.get("policy2_filename")
        or f"Policy {row.policy2_id}"
    )

    logger.info(
        "Generating recommendations for comparison %d, profile: %s, concern: %s",
        comparison_id,
        body.budget_priority,
        body.primary_concern,
    )

    try:
        payload = generate_recommendations(
            comparison_result=result,
            user_profile=body.model_dump(),
            policy1_name=p1_name,
            policy2_name=p2_name,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )

    return RecommendationResponse(
        comparison_id=comparison_id,
        policy1_name=p1_name,
        policy2_name=p2_name,
        user_profile=body,
        primary_recommendation=payload["primary_recommendation"],
        alternative_profiles=payload["alternative_profiles"],
        overall_winner=payload.get("overall_winner"),
        overall_winner_name=payload.get("overall_winner_name"),
        generated_at=payload["generated_at"],
    )


@router.get(
    "/comparisons/{comparison_id}/anomalies",
    response_model=AnomalyDetectionResponse,
    summary="Detect anomalies in both policies against industry norms",
)
def get_comparison_anomalies(
    comparison_id: int,
    db: Session = Depends(get_db),
) -> AnomalyDetectionResponse:
    """Analyse a completed comparison result for unusual or missing policy characteristics.

    Runs deterministic rule-based checks against industry benchmarks followed by
    a Groq LLM pass to surface additional anomalies.  Returns a merged, sorted
    list of AnomalyItem entries together with summary counts and five plain-English
    LLM insights about overall policy quality and risk.
    """
    row = db.get(Comparison, comparison_id)
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Comparison {comparison_id} not found",
        )
    if row.status != ComparisonStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Comparison is not yet completed",
        )
    if row.comparison_result is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No result data",
        )

    p1 = db.get(Policy, row.policy1_id)
    p2 = db.get(Policy, row.policy2_id)
    result = row.comparison_result

    p1_name = (
        (p1.original_name if p1 else None)
        or result.get("policy1_filename")
        or f"Policy {row.policy1_id}"
    )
    p2_name = (
        (p2.original_name if p2 else None)
        or result.get("policy2_filename")
        or f"Policy {row.policy2_id}"
    )

    logger.info("Running anomaly detection for comparison %d", comparison_id)

    try:
        payload = run_anomaly_detection(
            comparison_result=result,
            policy1_name=p1_name,
            policy2_name=p2_name,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )

    return AnomalyDetectionResponse(
        comparison_id=comparison_id,
        policy1_name=p1_name,
        policy2_name=p2_name,
        **payload,
    )


@router.get(
    "/comparisons/{comparison_id}/plain-summary",
    response_model=PlainSummaryResponse,
    summary="Get a plain-English consumer-friendly summary of a comparison",
)
def get_comparison_plain_summary(
    comparison_id: int,
    db: Session = Depends(get_db),
) -> PlainSummaryResponse:
    """Generate a jargon-free plain-English summary of a completed comparison.

    Uses the Groq LLM to produce a Grade 6 reading level summary of both
    policies individually and a comparison narrative, suitable for consumers
    with no insurance expertise.
    """
    row = db.get(Comparison, comparison_id)
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Comparison {comparison_id} not found",
        )
    if row.status != ComparisonStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Comparison {comparison_id} is not yet completed "
                f"(current status: {row.status})"
            ),
        )
    if not row.comparison_result:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Comparison {comparison_id} has no result data",
        )

    p1 = db.get(Policy, row.policy1_id)
    p2 = db.get(Policy, row.policy2_id)
    result = row.comparison_result

    p1_name = (
        (p1.original_name if p1 else None)
        or result.get("policy1_filename")
        or f"Policy {row.policy1_id}"
    )
    p2_name = (
        (p2.original_name if p2 else None)
        or result.get("policy2_filename")
        or f"Policy {row.policy2_id}"
    )

    logger.info(
        "Generating plain summary for comparison %d ('%s' vs '%s')",
        comparison_id,
        p1_name,
        p2_name,
    )

    try:
        payload = generate_plain_summary(result, p1_name, p2_name)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )
    except Exception as exc:
        logger.error(
            "Unexpected error generating plain summary for comparison %d",
            comparison_id,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while generating the plain summary",
        )

    payload["comparison_id"] = comparison_id
    return PlainSummaryResponse(**payload)


@router.delete(
    "/comparisons/{comparison_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a comparison and its associated policies",
)
def delete_comparison(comparison_id: int, db: Session = Depends(get_db)):
    row = db.get(Comparison, comparison_id)
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Comparison {comparison_id} not found",
        )
    db.delete(row)
    db.commit()


# ---------------------------------------------------------------------------
# Upload history
# ---------------------------------------------------------------------------

@router.get(
    "/history",
    response_model=List[HistoryItem],
    summary="Upload session history (most recent first)",
)
def get_history(skip: int = 0, limit: int = 20, db: Session = Depends(get_db)):
    if limit > 100:
        limit = 100
    rows = (
        db.query(UploadSession)
        .order_by(UploadSession.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return rows
