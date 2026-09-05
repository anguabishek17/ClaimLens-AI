"""
ClaimLens AI - Pydantic Data Models & Schemas
Defines request/response contracts and domain models for claim review.
"""

from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class RecommendationEnum(str, Enum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    REQUEST_INFORMATION = "REQUEST INFORMATION"
    ESCALATE = "ESCALATE"


class VehicleTypeEnum(str, Enum):
    TWO_WHEELER = "TWO_WHEELER"
    CAR = "CAR"


class ClaimTypeEnum(str, Enum):
    ACCIDENT = "ACCIDENT"
    THEFT = "THEFT"
    THIRD_PARTY = "THIRD_PARTY"
    NATURAL_CALAMITY = "NATURAL_CALAMITY"


class ClauseImpactEnum(str, Enum):
    SUPPORTS = "SUPPORTS"
    BLOCKS = "BLOCKS"
    CONDITIONAL = "CONDITIONAL"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class HealthResponse(BaseModel):
    status: str = "ok"
    project: str = "ClaimLens AI"


class DocumentInput(BaseModel):
    doc_type: str = Field(..., description="Type of document (e.g., 'claim_form', 'fir', 'repair_estimate', 'incident_description')")
    filename: Optional[str] = None
    content: str = Field(..., description="Raw text content extracted from the document")


class ClaimSubmissionRequest(BaseModel):
    claim_id: Optional[str] = None
    vehicle_type: VehicleTypeEnum = VehicleTypeEnum.CAR
    claim_type: ClaimTypeEnum = ClaimTypeEnum.ACCIDENT
    claim_form_text: str = Field(..., description="Content of the claim form")
    evidence_doc_text: str = Field(..., description="Content of the repair estimate or FIR")
    incident_description_text: str = Field(..., description="Customer incident description")
    insured_declared_value: Optional[float] = Field(None, description="Insured Declared Value (IDV)")
    claimed_amount: Optional[float] = Field(None, description="Total amount claimed")
    incident_date: Optional[str] = Field(None, description="YYYY-MM-DD date of incident")
    claim_date: Optional[str] = Field(None, description="YYYY-MM-DD date of claim submission")


class DocumentCompletenessFinding(BaseModel):
    document_name: str
    is_present: bool
    is_sufficient: bool
    missing_fields: List[str] = []
    notes: Optional[str] = None


class ContradictionDocument(BaseModel):
    source: str
    value: str


class ContradictionFinding(BaseModel):
    field: str
    document_a: ContradictionDocument
    document_b: ContradictionDocument
    severity: str = Field("HIGH", description="HIGH, MEDIUM, LOW")
    explanation: str


class PolicyClauseEvaluation(BaseModel):
    clause_id: str
    clause_title: str
    clause_text: str
    impact: ClauseImpactEnum
    reasoning: str
    source_citation: str


class EvidenceFinding(BaseModel):
    finding_id: str
    category: str = Field(..., description="e.g., 'completeness', 'consistency', 'exclusion', 'coverage'")
    observation: str
    source_document: str
    policy_clause_ref: Optional[str] = None
    impact: str


class RuleStatusEnum(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"


class PolicyRuleResult(BaseModel):
    rule_id: str
    status: RuleStatusEnum
    finding: str
    evidence: List[str] = []
    policy_clause: str


class EscalationPriorityEnum(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class EscalationResult(BaseModel):
    escalation_required: bool
    reason: str
    priority: EscalationPriorityEnum
    human_action: str


class ClaimReviewResult(BaseModel):
    claim_id: str
    recommendation: RecommendationEnum
    escalate_to_human: bool
    escalation_reason: Optional[str] = None
    escalation: Optional[EscalationResult] = None
    rule_results: List[PolicyRuleResult] = []
    document_completeness: List[DocumentCompletenessFinding] = []
    document_consistency: Dict[str, Any] = Field(default_factory=dict)
    contradictions: List[ContradictionFinding] = []
    applicable_clauses: List[PolicyClauseEvaluation] = []
    evidence_findings: List[EvidenceFinding] = []
    summary_notes: str
