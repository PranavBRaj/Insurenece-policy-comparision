from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ---------------------------------------------------------------------------
# Shared / inner schemas
# ---------------------------------------------------------------------------

class PolicyItemSchema(BaseModel):
    text: str
    amount: Optional[str] = None
    limit: Optional[str] = None
    raw_context: Optional[str] = None


class PremiumInfoSchema(BaseModel):
    annual_premium: Optional[str] = None
    monthly_premium: Optional[str] = None
    deductible: Optional[str] = None
    copay: Optional[str] = None
    coinsurance: Optional[str] = None
    out_of_pocket_max: Optional[str] = None
    additional_fees: List[Dict[str, str]] = []


class ParsedPolicySchema(BaseModel):
    filename: str
    coverage_items: List[PolicyItemSchema] = []
    exclusion_items: List[PolicyItemSchema] = []
    premium_info: PremiumInfoSchema = PremiumInfoSchema()
    raw_text_snippet: Optional[str] = None  # first 500 chars for debug


# ---------------------------------------------------------------------------
# Comparison result schemas
# ---------------------------------------------------------------------------

class MatchedItemSchema(BaseModel):
    item: str
    policy1_details: Optional[str] = None
    policy2_details: Optional[str] = None
    policy1_amount: Optional[str] = None
    policy2_amount: Optional[str] = None
    similarity_score: float = 0.0


class SectionComparisonSchema(BaseModel):
    common: List[MatchedItemSchema] = []
    only_in_policy1: List[PolicyItemSchema] = []
    only_in_policy2: List[PolicyItemSchema] = []


class PremiumComparisonSchema(BaseModel):
    policy1: PremiumInfoSchema = PremiumInfoSchema()
    policy2: PremiumInfoSchema = PremiumInfoSchema()
    differences: List[str] = []


class ComparisonResultSchema(BaseModel):
    coverage: SectionComparisonSchema = SectionComparisonSchema()
    exclusions: SectionComparisonSchema = SectionComparisonSchema()
    premiums: PremiumComparisonSchema = PremiumComparisonSchema()
    summary: Dict[str, Any] = {}


# ---------------------------------------------------------------------------
# API request / response schemas
# ---------------------------------------------------------------------------

class PolicyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    original_name: str
    file_size: int
    parse_status: str
    created_at: datetime


class ComparisonResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    policy1_id: int
    policy2_id: int
    status: str
    comparison_result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    created_at: datetime


class ComparisonListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    policy1_id: int
    policy2_id: int
    policy1_filename: Optional[str] = None
    policy2_filename: Optional[str] = None
    status: str
    created_at: datetime


class UploadCompareResponse(BaseModel):
    session_id: str
    policy1: PolicyResponse
    policy2: PolicyResponse
    comparison: ComparisonResponse


class HistoryItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    session_id: str
    policy1_filename: Optional[str]
    policy2_filename: Optional[str]
    status: str
    comparison_id: Optional[int]
    created_at: datetime


class ErrorResponse(BaseModel):
    detail: str
    code: Optional[str] = None


# ---------------------------------------------------------------------------
# Q&A schemas
# ---------------------------------------------------------------------------


class AskQuestionRequest(BaseModel):
    """Request body for the conversational Q&A endpoint."""

    question: str = Field(min_length=5, max_length=500)


class AskQuestionResponse(BaseModel):
    """Structured answer returned by the conversational Q&A endpoint."""

    question: str
    answer: str
    confidence: Optional[str] = None
    relevant_sections: List[str] = []


# ---------------------------------------------------------------------------
# Visualisation schemas
# ---------------------------------------------------------------------------


class BarChartData(BaseModel):
    """Dataset for a grouped bar chart."""

    labels: List[str]
    policy1_values: List[float]
    policy2_values: List[float]


class DonutChartData(BaseModel):
    """Dataset for a donut / pie chart."""

    labels: List[str]
    values: List[int]


class HistogramData(BaseModel):
    """Dataset for the similarity-score histogram."""

    buckets: List[str]
    counts: List[int]


class VisualisationResponse(BaseModel):
    """All chart datasets for the comparison visualisation page."""

    policy1_name: str
    policy2_name: str
    coverage_bar: BarChartData
    coverage_donut: DonutChartData
    exclusions_donut: DonutChartData
    premium_bar: BarChartData
    similarity_histogram: HistogramData


# ---------------------------------------------------------------------------
# Recommendation schemas
# ---------------------------------------------------------------------------


class UserProfileInput(BaseModel):
    """User profile describing personal situation and insurance priorities.

    All fields are optional so users can supply only the information that
    applies to them.
    """

    age: Optional[int] = None
    family_size: Optional[int] = None
    has_children: Optional[bool] = None
    is_senior: Optional[bool] = None
    has_chronic_condition: Optional[bool] = None
    budget_priority: Optional[str] = None
    primary_concern: Optional[str] = None
    risk_tolerance: Optional[str] = None
    notes: Optional[str] = None

    @field_validator("age")
    @classmethod
    def validate_age(cls, v: Optional[int]) -> Optional[int]:
        """Age must be between 18 and 100 when provided."""
        if v is not None and not (18 <= v <= 100):
            raise ValueError("age must be between 18 and 100")
        return v

    @field_validator("family_size")
    @classmethod
    def validate_family_size(cls, v: Optional[int]) -> Optional[int]:
        """Family size must be between 1 and 20 when provided."""
        if v is not None and not (1 <= v <= 20):
            raise ValueError("family_size must be between 1 and 20")
        return v

    @field_validator("notes")
    @classmethod
    def validate_notes(cls, v: Optional[str]) -> Optional[str]:
        """Free-text notes must not exceed 300 characters."""
        if v and len(v) > 300:
            raise ValueError("notes must be 300 characters or fewer")
        return v


class ProfileRecommendation(BaseModel):
    """Policy recommendation for a specific user profile.

    Returned as part of RecommendationResponse for both the user's own
    profile and each of the four standard demographic profiles.
    """

    profile_label: str
    recommended_policy: str
    recommended_policy_name: str
    confidence: str
    reasoning: str
    key_factors: List[str]
    caveats: List[str]


class RecommendationResponse(BaseModel):
    """Full recommendation response for a POST /comparisons/{id}/recommend request.

    Includes a primary recommendation tailored to the submitted user profile
    and recommendations for four standard demographics, plus an overall winner
    determined by majority vote across all five profiles.
    """

    comparison_id: int
    policy1_name: str
    policy2_name: str
    user_profile: UserProfileInput
    primary_recommendation: ProfileRecommendation
    alternative_profiles: List[ProfileRecommendation]
    overall_winner: Optional[str] = None
    overall_winner_name: Optional[str] = None
    generated_at: str


# ---------------------------------------------------------------------------
# Anomaly detection schemas
# ---------------------------------------------------------------------------


class AnomalyItem(BaseModel):
    """A single anomaly flagged during policy analysis.

    Produced by either a deterministic rule check (detected_by='rule') or the
    Groq LLM (detected_by='llm').
    """

    anomaly_id:  str
    severity:    str
    policy:      str
    category:    str
    title:       str
    description: str
    evidence:    str
    suggestion:  str
    detected_by: str


class AnomalySummary(BaseModel):
    """Aggregate counts and risk assessment across all detected anomalies."""

    total_anomalies:      int
    critical_count:       int
    warning_count:        int
    info_count:           int
    policy1_anomalies:    int
    policy2_anomalies:    int
    both_anomalies:       int
    riskiest_policy:      Optional[str] = None
    riskiest_policy_name: Optional[str] = None


class AnomalyDetectionResponse(BaseModel):
    """Full response for GET /comparisons/{id}/anomalies.

    Contains the merged list of rule-based and LLM-based anomaly items,
    aggregate summary counts, and five plain-English LLM insights about
    overall policy quality and risk.
    """

    comparison_id: int
    policy1_name:  str
    policy2_name:  str
    anomalies:     List[AnomalyItem]
    summary:       AnomalySummary
    llm_insights:  List[str]
    generated_at:  str


# ---------------------------------------------------------------------------
# Plain-English summary schemas
# ---------------------------------------------------------------------------


class PolicyPlainSummary(BaseModel):
    """Plain-English summary of a single policy written for a non-expert reader."""

    policy_name:          str
    one_liner:            str
    what_it_covers:       str
    what_it_doesnt_cover: str
    cost_plain:           str
    biggest_strength:     str
    biggest_weakness:     str


class ComparisonPlainSummary(BaseModel):
    """Plain-English narrative comparing both policies side by side."""

    executive_summary:    str
    key_difference:       str
    cost_comparison:      str
    coverage_comparison:  str
    who_wins_cost:        str
    who_wins_coverage:    str
    who_wins_overall:     str
    bottom_line:          str
    reading_time_seconds: int


class PlainSummaryResponse(BaseModel):
    """Full response for GET /comparisons/{id}/plain-summary."""

    comparison_id:      int
    policy1_name:       str
    policy2_name:       str
    policy1_summary:    PolicyPlainSummary
    policy2_summary:    PolicyPlainSummary
    comparison_summary: ComparisonPlainSummary
    readability_level:  str
    generated_at:       str
    word_count:         int



