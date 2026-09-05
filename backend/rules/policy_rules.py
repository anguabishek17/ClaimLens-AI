"""
ClaimLens AI - Deterministic Policy Rules
Encapsulates rigid motor insurance policy rules separate from LLM reasoning.
Phase 5 Implementation.
"""

from datetime import datetime
import re
from typing import List, Optional

from backend.models import (
    ClaimSubmissionRequest,
    PolicyRuleResult,
    RuleStatusEnum,
    ClaimTypeEnum,
    VehicleTypeEnum,
)
class PolicyRulesEngine:
    ACCIDENT_REPORTING_WINDOW_DAYS = 7
    THEFT_REPORTING_WINDOW_DAYS = 2

    @classmethod
    def run_policy_rules(cls, request: ClaimSubmissionRequest, policy_data: dict = None) -> List[PolicyRuleResult]:
        """Runs all 10 deterministic rules and returns structured results."""
        results = [
            cls.rule_001_reporting_window(request),
            cls.rule_002_required_documents(request),
            cls.rule_003_vehicle_registration_match(request, policy_data),
            cls.rule_004_policy_number_match(request, policy_data),
            cls.rule_005_idv_vs_claimed_amount(request),
            cls.rule_006_policy_validity(request, policy_data),
            cls.rule_007_required_fir_for_theft(request),
            cls.rule_008_required_repair_estimate(request),
            cls.rule_009_deductible_calculation(request),
            cls.rule_010_basic_coverage_eligibility(request),
        ]
        return results

    @staticmethod
    def _extract_text_fields(request: ClaimSubmissionRequest):
        from backend.services.document_service import DocumentService
        cf_entities = DocumentService.extract_key_fields(request.claim_form_text)
        ev_entities = DocumentService.extract_key_fields(request.evidence_doc_text)
        id_entities = DocumentService.extract_key_fields(request.incident_description_text)
        return cf_entities, ev_entities, id_entities

    @classmethod
    def rule_001_reporting_window(cls, request: ClaimSubmissionRequest) -> PolicyRuleResult:
        if not request.incident_date or not request.claim_date:
            return PolicyRuleResult(
                rule_id="R-001",
                status=RuleStatusEnum.UNKNOWN,
                finding="Incident date or claim date is missing.",
                evidence=[],
                policy_clause="C-08"
            )
        try:
            inc_dt = datetime.strptime(request.incident_date, "%Y-%m-%d")
            clm_dt = datetime.strptime(request.claim_date, "%Y-%m-%d")
            diff_days = (clm_dt - inc_dt).days
            allowed = cls.THEFT_REPORTING_WINDOW_DAYS if request.claim_type == ClaimTypeEnum.THEFT else cls.ACCIDENT_REPORTING_WINDOW_DAYS
            
            if diff_days < 0:
                return PolicyRuleResult(
                    rule_id="R-001",
                    status=RuleStatusEnum.FAIL,
                    finding=f"Claim date ({request.claim_date}) is prior to incident date ({request.incident_date}).",
                    evidence=[f"Incident Date: {request.incident_date}", f"Claim Date: {request.claim_date}"],
                    policy_clause="C-08"
                )
            if diff_days <= allowed:
                return PolicyRuleResult(
                    rule_id="R-001",
                    status=RuleStatusEnum.PASS,
                    finding=f"Claim reported {diff_days} days after incident, within the {allowed}-day window.",
                    evidence=[f"Incident Date: {request.incident_date}", f"Claim Date: {request.claim_date}"],
                    policy_clause="C-08"
                )
            else:
                return PolicyRuleResult(
                    rule_id="R-001",
                    status=RuleStatusEnum.FAIL,
                    finding=f"Claim reported {diff_days} days after incident, exceeding the {allowed}-day window.",
                    evidence=[f"Incident Date: {request.incident_date}", f"Claim Date: {request.claim_date}"],
                    policy_clause="C-08"
                )
        except ValueError:
            return PolicyRuleResult(
                rule_id="R-001",
                status=RuleStatusEnum.UNKNOWN,
                finding="Invalid date format provided.",
                evidence=[],
                policy_clause="C-08"
            )

    @classmethod
    def rule_002_required_documents(cls, request: ClaimSubmissionRequest) -> PolicyRuleResult:
        missing = []
        if not request.claim_form_text or len(request.claim_form_text.strip()) < 20:
            missing.append("Claim Form")
        if not request.incident_description_text or len(request.incident_description_text.strip()) < 10:
            missing.append("Incident Description")
        if not request.evidence_doc_text or len(request.evidence_doc_text.strip()) < 20 or "[MISSING DOCUMENT]" in request.evidence_doc_text:
            missing.append("Evidence Document (FIR or Repair Estimate)")

        if missing:
            return PolicyRuleResult(
                rule_id="R-002",
                status=RuleStatusEnum.FAIL,
                finding=f"Missing required documents: {', '.join(missing)}.",
                evidence=missing,
                policy_clause="C-09"
            )
        return PolicyRuleResult(
            rule_id="R-002",
            status=RuleStatusEnum.PASS,
            finding="All mandatory documents are present.",
            evidence=["Claim Form", "Incident Description", "Evidence Document"],
            policy_clause="C-09"
        )

    @classmethod
    def rule_003_vehicle_registration_match(cls, request: ClaimSubmissionRequest, policy_data: dict = None) -> PolicyRuleResult:
        cf_ent, ev_ent, id_ent = cls._extract_text_fields(request)
        cf_regs = set(cf_ent.get("detected_vehicle_numbers", []))
        ev_regs = set(ev_ent.get("detected_vehicle_numbers", []))
        id_regs = set(id_ent.get("detected_vehicle_numbers", []))
        
        all_regs = cf_regs.union(ev_regs).union(id_regs)
        if not all_regs:
            return PolicyRuleResult(
                rule_id="R-003",
                status=RuleStatusEnum.UNKNOWN,
                finding="No vehicle registration numbers detected in documents.",
                evidence=[],
                policy_clause="C-19"
            )
        
        expected_reg = policy_data.get("vehicle_registration") if policy_data else None
        
        if len(all_regs) == 1:
            detected_reg = list(all_regs)[0]
            if expected_reg:
                if detected_reg == expected_reg:
                    return PolicyRuleResult(
                        rule_id="R-003",
                        status=RuleStatusEnum.PASS,
                        finding=f"Vehicle registration {detected_reg} matches policy data and across documents.",
                        evidence=[f"Detected: {detected_reg}", f"Expected: {expected_reg}"],
                        policy_clause="C-19"
                    )
                else:
                    return PolicyRuleResult(
                        rule_id="R-003",
                        status=RuleStatusEnum.FAIL,
                        finding=f"Vehicle registration mismatch. Detected: {detected_reg}, Expected: {expected_reg}.",
                        evidence=[f"Detected: {detected_reg}", f"Expected: {expected_reg}"],
                        policy_clause="C-19"
                    )
            return PolicyRuleResult(
                rule_id="R-003",
                status=RuleStatusEnum.PASS,
                finding=f"Vehicle registration {detected_reg} matches across documents.",
                evidence=[f"Detected: {detected_reg}"],
                policy_clause="C-19"
            )
        
        return PolicyRuleResult(
            rule_id="R-003",
            status=RuleStatusEnum.FAIL,
            finding="Mismatched vehicle registrations detected across documents.",
            evidence=[f"Found registrations: {list(all_regs)}"],
            policy_clause="C-19"
        )

    @classmethod
    def rule_004_policy_number_match(cls, request: ClaimSubmissionRequest, policy_data: dict = None) -> PolicyRuleResult:
        # Looking for generic policy number patterns in the claim form
        pol_matches = re.findall(r"POL-\d+-[A-Z]+|Policy Number:\s*([A-Za-z0-9\-]+)", request.claim_form_text, re.IGNORECASE)
        found = [p for p in pol_matches if p] or re.findall(r"POL-\d+-[A-Z]+", request.claim_form_text)
        if not found:
            return PolicyRuleResult(
                rule_id="R-004",
                status=RuleStatusEnum.UNKNOWN,
                finding="Policy number not explicitly found in Claim Form.",
                evidence=[],
                policy_clause="C-18"
            )
            
        extracted_pol = found[0].strip()
        expected_pol = policy_data.get("policy_number") if policy_data else None
        
        if expected_pol:
            if extracted_pol == expected_pol:
                return PolicyRuleResult(
                    rule_id="R-004",
                    status=RuleStatusEnum.PASS,
                    finding=f"Policy number {extracted_pol} matches policy data.",
                    evidence=[f"Found: {extracted_pol}", f"Expected: {expected_pol}"],
                    policy_clause="C-18"
                )
            else:
                return PolicyRuleResult(
                    rule_id="R-004",
                    status=RuleStatusEnum.FAIL,
                    finding=f"Policy number mismatch. Found: {extracted_pol}, Expected: {expected_pol}.",
                    evidence=[f"Found: {extracted_pol}", f"Expected: {expected_pol}"],
                    policy_clause="C-18"
                )
                
        return PolicyRuleResult(
            rule_id="R-004",
            status=RuleStatusEnum.PASS,
            finding=f"Policy number {extracted_pol} provided.",
            evidence=[f"Policy Number: {extracted_pol}"],
            policy_clause="C-18"
        )

    @classmethod
    def rule_005_idv_vs_claimed_amount(cls, request: ClaimSubmissionRequest) -> PolicyRuleResult:
        if request.insured_declared_value is None or request.claimed_amount is None:
            return PolicyRuleResult(
                rule_id="R-005",
                status=RuleStatusEnum.UNKNOWN,
                finding="IDV or Claimed Amount is missing.",
                evidence=[],
                policy_clause="C-12"
            )
        if request.claimed_amount <= request.insured_declared_value:
            return PolicyRuleResult(
                rule_id="R-005",
                status=RuleStatusEnum.PASS,
                finding="Claimed amount is within the IDV limit.",
                evidence=[f"IDV: {request.insured_declared_value}", f"Claimed: {request.claimed_amount}"],
                policy_clause="C-12"
            )
        return PolicyRuleResult(
            rule_id="R-005",
            status=RuleStatusEnum.FAIL,
            finding="Claimed amount exceeds the IDV limit.",
            evidence=[f"IDV: {request.insured_declared_value}", f"Claimed: {request.claimed_amount}"],
            policy_clause="C-12"
        )

    @classmethod
    def rule_006_policy_validity(cls, request: ClaimSubmissionRequest, policy_data: dict = None) -> PolicyRuleResult:
        if not policy_data:
            return PolicyRuleResult(
                rule_id="R-006",
                status=RuleStatusEnum.UNKNOWN,
                finding="Policy data not provided for deterministic check.",
                evidence=[],
                policy_clause="C-18"
            )
            
        start_date = policy_data.get("policy_start_date")
        end_date = policy_data.get("policy_end_date")
        inc_date = request.incident_date
        
        if not start_date or not end_date or not inc_date:
            return PolicyRuleResult(
                rule_id="R-006",
                status=RuleStatusEnum.UNKNOWN,
                finding="Policy start/end dates or incident date missing.",
                evidence=[],
                policy_clause="C-18"
            )
            
        try:
            s_dt = datetime.strptime(start_date, "%Y-%m-%d")
            e_dt = datetime.strptime(end_date, "%Y-%m-%d")
            i_dt = datetime.strptime(inc_date, "%Y-%m-%d")
            
            if s_dt <= i_dt <= e_dt:
                return PolicyRuleResult(
                    rule_id="R-006",
                    status=RuleStatusEnum.PASS,
                    finding="Incident occurred within active policy period.",
                    evidence=[f"Incident: {inc_date}", f"Policy: {start_date} to {end_date}"],
                    policy_clause="C-18"
                )
            else:
                return PolicyRuleResult(
                    rule_id="R-006",
                    status=RuleStatusEnum.FAIL,
                    finding="Incident occurred outside active policy period.",
                    evidence=[f"Incident: {inc_date}", f"Policy: {start_date} to {end_date}"],
                    policy_clause="C-18"
                )
        except ValueError:
            return PolicyRuleResult(
                rule_id="R-006",
                status=RuleStatusEnum.UNKNOWN,
                finding="Invalid date format provided for policy validity check.",
                evidence=[],
                policy_clause="C-18"
            )

    @classmethod
    def rule_007_required_fir_for_theft(cls, request: ClaimSubmissionRequest) -> PolicyRuleResult:
        if request.claim_type != ClaimTypeEnum.THEFT:
            return PolicyRuleResult(
                rule_id="R-007",
                status=RuleStatusEnum.PASS,
                finding="Not a theft claim; FIR requirement does not strictly apply.",
                evidence=[f"Claim Type: {request.claim_type}"],
                policy_clause="C-10"
            )
        if "fir" in request.evidence_doc_text.lower() or "first information report" in request.evidence_doc_text.lower():
            return PolicyRuleResult(
                rule_id="R-007",
                status=RuleStatusEnum.PASS,
                finding="FIR detected for theft claim.",
                evidence=["FIR keywords found in evidence document"],
                policy_clause="C-10"
            )
        return PolicyRuleResult(
            rule_id="R-007",
            status=RuleStatusEnum.FAIL,
            finding="FIR document is missing for a theft claim.",
            evidence=["Evidence document does not contain FIR indicators"],
            policy_clause="C-10"
        )

    @classmethod
    def rule_008_required_repair_estimate(cls, request: ClaimSubmissionRequest) -> PolicyRuleResult:
        if request.claim_type != ClaimTypeEnum.ACCIDENT:
            return PolicyRuleResult(
                rule_id="R-008",
                status=RuleStatusEnum.PASS,
                finding="Not an accident claim; Repair estimate requirement may not strictly apply.",
                evidence=[f"Claim Type: {request.claim_type}"],
                policy_clause="C-11"
            )
        
        keywords = ["estimate", "repair", "invoice", "garage", "bill"]
        text = request.evidence_doc_text.lower()
        if any(k in text for k in keywords) and not "[missing document]" in text:
            return PolicyRuleResult(
                rule_id="R-008",
                status=RuleStatusEnum.PASS,
                finding="Repair estimate detected for accident claim.",
                evidence=["Repair keywords found in evidence document"],
                policy_clause="C-11"
            )
        return PolicyRuleResult(
            rule_id="R-008",
            status=RuleStatusEnum.FAIL,
            finding="Itemized repair estimate is missing for an accident claim.",
            evidence=["Evidence document does not contain repair estimate indicators"],
            policy_clause="C-11"
        )

    @classmethod
    def rule_009_deductible_calculation(cls, request: ClaimSubmissionRequest) -> PolicyRuleResult:
        deductible = 2000 if request.vehicle_type == VehicleTypeEnum.CAR else 1000
        if request.claimed_amount is None:
            return PolicyRuleResult(
                rule_id="R-009",
                status=RuleStatusEnum.UNKNOWN,
                finding="Claimed amount is missing; cannot evaluate deductible application.",
                evidence=[],
                policy_clause="C-13"
            )
        if request.claimed_amount > deductible:
            return PolicyRuleResult(
                rule_id="R-009",
                status=RuleStatusEnum.PASS,
                finding=f"Claimed amount exceeds standard compulsory deductible (Rs {deductible}).",
                evidence=[f"Claimed: {request.claimed_amount}", f"Deductible: {deductible}"],
                policy_clause="C-13"
            )
        return PolicyRuleResult(
            rule_id="R-009",
            status=RuleStatusEnum.FAIL,
            finding=f"Claimed amount is less than or equal to the compulsory deductible (Rs {deductible}). Claim not payable.",
            evidence=[f"Claimed: {request.claimed_amount}", f"Deductible: {deductible}"],
            policy_clause="C-13"
        )

    @classmethod
    def rule_010_basic_coverage_eligibility(cls, request: ClaimSubmissionRequest) -> PolicyRuleResult:
        if request.claimed_amount is None or request.insured_declared_value is None:
            return PolicyRuleResult(
                rule_id="R-010",
                status=RuleStatusEnum.UNKNOWN,
                finding="Financial values missing for coverage eligibility check.",
                evidence=[],
                policy_clause="C-01"
            )
        if request.claimed_amount <= 0:
            return PolicyRuleResult(
                rule_id="R-010",
                status=RuleStatusEnum.FAIL,
                finding="Claimed amount must be greater than zero.",
                evidence=[f"Claimed: {request.claimed_amount}"],
                policy_clause="C-01"
            )
        return PolicyRuleResult(
            rule_id="R-010",
            status=RuleStatusEnum.PASS,
            finding="Basic financial and type parameters meet minimum eligibility criteria.",
            evidence=[f"Claimed: {request.claimed_amount}"],
            policy_clause="C-01"
        )
