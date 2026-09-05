import pytest
from backend.models import ClaimSubmissionRequest, ClaimTypeEnum, VehicleTypeEnum, RuleStatusEnum
from backend.rules.policy_rules import PolicyRulesEngine

def test_rule_001_reporting_window():
    # Pass case
    req = ClaimSubmissionRequest(
        claim_form_text="", evidence_doc_text="", incident_description_text="",
        incident_date="2023-01-01", claim_date="2023-01-05", claim_type=ClaimTypeEnum.ACCIDENT
    )
    res = PolicyRulesEngine.rule_001_reporting_window(req)
    assert res.status == RuleStatusEnum.PASS

    # Fail case
    req.claim_date = "2023-01-10"
    res = PolicyRulesEngine.rule_001_reporting_window(req)
    assert res.status == RuleStatusEnum.FAIL

    # Unknown case
    req.incident_date = None
    res = PolicyRulesEngine.rule_001_reporting_window(req)
    assert res.status == RuleStatusEnum.UNKNOWN

def test_rule_002_required_documents():
    req = ClaimSubmissionRequest(
        claim_form_text="Valid claim form with enough text to pass the twenty chars limit",
        incident_description_text="Valid incident description here",
        evidence_doc_text="Valid evidence document text that is long enough"
    )
    res = PolicyRulesEngine.rule_002_required_documents(req)
    assert res.status == RuleStatusEnum.PASS

    req.claim_form_text = "short"
    res = PolicyRulesEngine.rule_002_required_documents(req)
    assert res.status == RuleStatusEnum.FAIL

def test_rule_003_vehicle_registration_match():
    req = ClaimSubmissionRequest(
        claim_form_text="My car DL01AB1234 was hit.",
        incident_description_text="Car DL01AB1234 is damaged.",
        evidence_doc_text="Repair for DL01AB1234"
    )
    res = PolicyRulesEngine.rule_003_vehicle_registration_match(req)
    assert res.status == RuleStatusEnum.PASS

    policy_data = {"vehicle_registration": "DL01AB1234"}
    res = PolicyRulesEngine.rule_003_vehicle_registration_match(req, policy_data)
    assert res.status == RuleStatusEnum.PASS

    policy_data_fail = {"vehicle_registration": "MH12CD3456"}
    res = PolicyRulesEngine.rule_003_vehicle_registration_match(req, policy_data_fail)
    assert res.status == RuleStatusEnum.FAIL

    req.evidence_doc_text = "Repair for MH12CD3456"
    res = PolicyRulesEngine.rule_003_vehicle_registration_match(req)
    assert res.status == RuleStatusEnum.FAIL

def test_rule_004_policy_number_match():
    req = ClaimSubmissionRequest(
        claim_form_text="Policy Number: POL-1234-XYZ",
        incident_description_text="",
        evidence_doc_text=""
    )
    res = PolicyRulesEngine.rule_004_policy_number_match(req)
    assert res.status == RuleStatusEnum.PASS

    policy_data = {"policy_number": "POL-1234-XYZ"}
    res = PolicyRulesEngine.rule_004_policy_number_match(req, policy_data)
    assert res.status == RuleStatusEnum.PASS

    policy_data_fail = {"policy_number": "POL-9999-ABC"}
    res = PolicyRulesEngine.rule_004_policy_number_match(req, policy_data_fail)
    assert res.status == RuleStatusEnum.FAIL

    req.claim_form_text = "No policy number here."
    res = PolicyRulesEngine.rule_004_policy_number_match(req)
    assert res.status == RuleStatusEnum.UNKNOWN

def test_rule_005_idv_vs_claimed_amount():
    req = ClaimSubmissionRequest(
        claim_form_text="", evidence_doc_text="", incident_description_text="",
        insured_declared_value=500000, claimed_amount=40000
    )
    res = PolicyRulesEngine.rule_005_idv_vs_claimed_amount(req)
    assert res.status == RuleStatusEnum.PASS

    req.claimed_amount = 600000
    res = PolicyRulesEngine.rule_005_idv_vs_claimed_amount(req)
    assert res.status == RuleStatusEnum.FAIL

    req.claimed_amount = None
    res = PolicyRulesEngine.rule_005_idv_vs_claimed_amount(req)
    assert res.status == RuleStatusEnum.UNKNOWN

def test_rule_006_policy_validity():
    req = ClaimSubmissionRequest(
        claim_form_text="", evidence_doc_text="", incident_description_text="",
        incident_date="2023-06-15"
    )
    policy_data = {
        "policy_start_date": "2023-01-01",
        "policy_end_date": "2023-12-31"
    }
    res = PolicyRulesEngine.rule_006_policy_validity(req, policy_data)
    assert res.status == RuleStatusEnum.PASS

    req.incident_date = "2024-01-15"
    res = PolicyRulesEngine.rule_006_policy_validity(req, policy_data)
    assert res.status == RuleStatusEnum.FAIL

    res = PolicyRulesEngine.rule_006_policy_validity(req, None)
    assert res.status == RuleStatusEnum.UNKNOWN

def test_rule_007_required_fir_for_theft():
    req = ClaimSubmissionRequest(
        claim_form_text="", evidence_doc_text="first information report", incident_description_text="",
        claim_type=ClaimTypeEnum.THEFT
    )
    res = PolicyRulesEngine.rule_007_required_fir_for_theft(req)
    assert res.status == RuleStatusEnum.PASS

    req.evidence_doc_text = "Just a generic document"
    res = PolicyRulesEngine.rule_007_required_fir_for_theft(req)
    assert res.status == RuleStatusEnum.FAIL

    req.claim_type = ClaimTypeEnum.ACCIDENT
    res = PolicyRulesEngine.rule_007_required_fir_for_theft(req)
    assert res.status == RuleStatusEnum.PASS

def test_rule_008_required_repair_estimate():
    req = ClaimSubmissionRequest(
        claim_form_text="", evidence_doc_text="repair invoice for the damage", incident_description_text="",
        claim_type=ClaimTypeEnum.ACCIDENT
    )
    res = PolicyRulesEngine.rule_008_required_repair_estimate(req)
    assert res.status == RuleStatusEnum.PASS

    req.evidence_doc_text = "no r_epair info here"
    res = PolicyRulesEngine.rule_008_required_repair_estimate(req)
    assert res.status == RuleStatusEnum.FAIL

    req.claim_type = ClaimTypeEnum.THEFT
    res = PolicyRulesEngine.rule_008_required_repair_estimate(req)
    assert res.status == RuleStatusEnum.PASS

def test_rule_009_deductible_calculation():
    req = ClaimSubmissionRequest(
        claim_form_text="", evidence_doc_text="", incident_description_text="",
        vehicle_type=VehicleTypeEnum.CAR, claimed_amount=5000
    )
    res = PolicyRulesEngine.rule_009_deductible_calculation(req)
    assert res.status == RuleStatusEnum.PASS

    req.claimed_amount = 1500
    res = PolicyRulesEngine.rule_009_deductible_calculation(req)
    assert res.status == RuleStatusEnum.FAIL

    req.claimed_amount = None
    res = PolicyRulesEngine.rule_009_deductible_calculation(req)
    assert res.status == RuleStatusEnum.UNKNOWN

def test_rule_010_basic_coverage_eligibility():
    req = ClaimSubmissionRequest(
        claim_form_text="", evidence_doc_text="", incident_description_text="",
        insured_declared_value=500000, claimed_amount=5000
    )
    res = PolicyRulesEngine.rule_010_basic_coverage_eligibility(req)
    assert res.status == RuleStatusEnum.PASS

    req.claimed_amount = -100
    res = PolicyRulesEngine.rule_010_basic_coverage_eligibility(req)
    assert res.status == RuleStatusEnum.FAIL

    req.insured_declared_value = None
    res = PolicyRulesEngine.rule_010_basic_coverage_eligibility(req)
    assert res.status == RuleStatusEnum.UNKNOWN

def test_run_policy_rules():
    req = ClaimSubmissionRequest(
        claim_form_text="Policy Number: POL-1234-XYZ Valid claim form with enough text",
        incident_description_text="Valid incident description here",
        evidence_doc_text="first information report",
        incident_date="2023-06-15", claim_date="2023-06-16",
        claim_type=ClaimTypeEnum.THEFT, vehicle_type=VehicleTypeEnum.CAR,
        insured_declared_value=500000, claimed_amount=50000
    )
    policy_data = {
        "policy_start_date": "2023-01-01",
        "policy_end_date": "2023-12-31",
        "policy_number": "POL-1234-XYZ"
    }
    
    results = PolicyRulesEngine.run_policy_rules(req, policy_data)
    assert len(results) == 10
    
    # Check what rule ran, evidence, policy clause for at least one rule to ensure schema correctness
    rule_7 = next(r for r in results if r.rule_id == "R-007")
    assert rule_7.status == RuleStatusEnum.PASS
    assert "FIR keywords found in evidence document" in rule_7.evidence
    assert rule_7.policy_clause == "C-10"
