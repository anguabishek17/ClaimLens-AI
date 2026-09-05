"""
ClaimLens AI - Claim Analysis Coordinator Service
Integrates deterministic policy rules with grounded AI reasoning to produce audit recommendations.
"""

import uuid
from typing import Optional
from backend.models import (
    ClaimSubmissionRequest,
    ClaimReviewResult,
    RecommendationEnum,
    PolicyClauseEvaluation,
    ClauseImpactEnum,
    EscalationResult,
    EscalationPriorityEnum,
    RuleStatusEnum,
)
from backend.rules.policy_rules import PolicyRulesEngine
from backend.services.contradiction_service import ContradictionService
from backend.services.retrieval_service import RetrievalService
from backend.services.gemini_service import GeminiService


class ClaimAnalysisService:
    """
    Main orchestrator for reviewing insurance claims against motor insurance policies.
    """

    def __init__(self, gemini_service: Optional[GeminiService] = None):
        self.gemini_service = gemini_service or GeminiService()
        self.retrieval_service = RetrievalService(self.gemini_service)

    def analyze_claim(self, request: ClaimSubmissionRequest) -> ClaimReviewResult:
        claim_id = request.claim_id or f"CLM-{uuid.uuid4().hex[:8].upper()}"

        # 1. Deterministic Rule Engine (Phase 5)
        rule_results = PolicyRulesEngine.run_policy_rules(request)
        
        # We need document completeness for the frontend, which expects it. 
        # We can map rule 2 to it, but let's keep a simplified Completeness array or remove it if not strictly required, 
        # but models.py still requires it so we'll mock it or populate it.
        completeness = []

        # 2. Contradiction Detection (Phase 6)
        contradictions = ContradictionService.detect_contradictions(request)

        # 3. Escalation Logic (Phase 6)
        escalation = None
        
        # Check reasons for escalation
        high_risk_contradiction = any(c.severity == "HIGH" for c in contradictions)
        rule_fails = [r for r in rule_results if r.status == RuleStatusEnum.FAIL]
        rule_unknowns = [r for r in rule_results if r.status == RuleStatusEnum.UNKNOWN]
        
        if high_risk_contradiction:
            escalation = EscalationResult(
                escalation_required=True,
                reason="High-risk contradiction detected across submitted evidence documents.",
                priority=EscalationPriorityEnum.HIGH,
                human_action="Potential inconsistency requiring investigator review."
            )
        elif any(r.rule_id == "R-002" for r in rule_fails):
            escalation = EscalationResult(
                escalation_required=True,
                reason="Critical information or required evidence is missing.",
                priority=EscalationPriorityEnum.HIGH,
                human_action="Request missing documents from claimant."
            )
        elif any(r.rule_id == "R-010" and r.status != RuleStatusEnum.PASS for r in rule_results):
            escalation = EscalationResult(
                escalation_required=True,
                reason="Policy coverage cannot be established confidently.",
                priority=EscalationPriorityEnum.HIGH,
                human_action="Review coverage limits and applicability."
            )
        elif rule_fails:
            escalation = EscalationResult(
                escalation_required=True,
                reason="Deterministic policy rules failed indicating violation of terms.",
                priority=EscalationPriorityEnum.HIGH,
                human_action="Review policy violations before final decision."
            )
        elif any(r.rule_id in ["R-001", "R-005", "R-010"] for r in rule_unknowns):
             escalation = EscalationResult(
                escalation_required=True,
                reason="Critical condition returned UNKNOWN from rule engine.",
                priority=EscalationPriorityEnum.MEDIUM,
                human_action="Verify missing claim values (Date or Amount)."
            )

        # 4. Retrieval of Relevant Policy Clauses (Phase 4 integration)
        combined_text = f"{request.claim_form_text}\n{request.evidence_doc_text}\n{request.incident_description_text}"
        
        # Try local vector search if available
        matched_clauses = self.retrieval_service.search_relevant_clauses(combined_text, top_k=3)

        applicable_clauses = []
        for c in matched_clauses:
            applicable_clauses.append(PolicyClauseEvaluation(
                clause_id=c.get("clause_id", "PL-001"),
                clause_title=c.get("title", "Standard Policy Term"),
                clause_text=c.get("text", ""),
                impact=ClauseImpactEnum(c.get("default_impact", "SUPPORTS")),
                reasoning=c.get("summary", "Applicable under general policy terms."),
                source_citation=c.get("section", "Section 1")
            ))

        # Ask Gemini for structured analysis
        clauses_text = "\n".join([f"- {c.clause_id}: {c.clause_text}" for c in applicable_clauses])
        gemini_response = self.gemini_service.generate_structured_analysis(
            claim_evidence_text=combined_text,
            relevant_clauses_text=clauses_text,
            deterministic_findings_text=""
        )

        if not escalation and gemini_response.get("missing_documents"):
            escalation = EscalationResult(
                escalation_required=True,
                reason="Gemini reports insufficient evidence.",
                priority=EscalationPriorityEnum.MEDIUM,
                human_action="Request missing documents from claimant."
            )

        # 5. Recommendation Gateways
        escalate_to_human = False
        escalation_reason = None
        recommendation = RecommendationEnum.APPROVE
        summary_notes = "Claim is approved."

        if escalation and escalation.escalation_required:
            escalate_to_human = True
            escalation_reason = escalation.reason
            if any(r.rule_id == "R-002" for r in rule_fails):
                recommendation = RecommendationEnum.REQUEST_INFORMATION
                summary_notes = "Missing mandatory documents."
            else:
                recommendation = RecommendationEnum.ESCALATE
                summary_notes = "Evidence inconsistency surfaced. Per policy guidelines, requires human review without asserting fraud."
        else:
            recommendation = RecommendationEnum.APPROVE
            summary_notes = "All rules passed and no contradictions detected."

        return ClaimReviewResult(
            claim_id=claim_id,
            recommendation=recommendation,
            escalate_to_human=escalate_to_human,
            escalation_reason=escalation_reason,
            escalation=escalation,
            rule_results=rule_results,
            document_completeness=completeness,
            document_consistency={"status": "CONFLICT" if contradictions else "CONSISTENT"},
            contradictions=contradictions,
            applicable_clauses=applicable_clauses,
            evidence_findings=[],
            summary_notes=summary_notes
        )
