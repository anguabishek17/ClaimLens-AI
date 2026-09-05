"""
ClaimLens AI - Data Loader & Knowledge Base Validation Test
Verifies policy.json schema and all 3 sample claim directories without external Gemini API calls.
"""

import json
from pathlib import Path
from backend.config import settings
from backend.services.claim_analysis_service import ClaimAnalysisService
from backend.models import ClaimSubmissionRequest, VehicleTypeEnum, ClaimTypeEnum, RecommendationEnum


def test_load_policy_json():
    policy_path = settings.POLICY_DIR / "policy.json"
    assert policy_path.exists(), "policy.json does not exist in data/policy/"

    with open(policy_path, "r", encoding="utf-8") as f:
        clauses = json.load(f)

    assert isinstance(clauses, list), "policy.json must be a JSON array"
    assert len(clauses) >= 20, f"Expected 20-30 clauses, found {len(clauses)}"

    required_keys = {"clause_id", "title", "text", "category", "conditions", "supporting_evidence_requirements"}
    for idx, clause in enumerate(clauses):
        missing = required_keys - set(clause.keys())
        assert not missing, f"Clause index {idx} ({clause.get('clause_id')}) missing keys: {missing}"
        assert clause["clause_id"].startswith("C-"), f"Clause ID {clause['clause_id']} must follow C-XX pattern"


def test_sample_claims_structure():
    claims_dir = settings.CLAIMS_DIR
    claim_folders = ["claim_001", "claim_002", "claim_003"]

    for folder in claim_folders:
        folder_path = claims_dir / folder
        assert folder_path.exists(), f"Sample claim directory {folder} missing"

        claim_json_path = folder_path / "claim.json"
        assert claim_json_path.exists(), f"claim.json missing in {folder}"

        with open(claim_json_path, "r", encoding="utf-8") as f:
            claim_meta = json.load(f)

        assert "claim_id" in claim_meta
        assert "status_expected" in claim_meta

        # Verify claim files exist
        claim_form_file = folder_path / claim_meta["claim_form_file"]
        desc_file = folder_path / claim_meta["incident_description_file"]
        evidence_file = folder_path / claim_meta["evidence_doc_file"]

        assert claim_form_file.exists()
        assert desc_file.exists()
        assert evidence_file.exists()


def test_analyze_sample_claims_deterministically():
    service = ClaimAnalysisService()
    claims_dir = settings.CLAIMS_DIR

    # Claim 1: Valid
    with open(claims_dir / "claim_001" / "claim_form.txt", "r", encoding="utf-8") as f:
        cf1 = f.read()
    with open(claims_dir / "claim_001" / "incident_description.txt", "r", encoding="utf-8") as f:
        id1 = f.read()
    with open(claims_dir / "claim_001" / "repair_estimate.txt", "r", encoding="utf-8") as f:
        ev1 = f.read()

    req1 = ClaimSubmissionRequest(
        claim_id="CLM-001",
        vehicle_type=VehicleTypeEnum.CAR,
        claim_type=ClaimTypeEnum.ACCIDENT,
        incident_date="2026-09-01",
        claim_date="2026-09-03",
        insured_declared_value=750000.0,
        claimed_amount=32000.0,
        claim_form_text=cf1,
        evidence_doc_text=ev1,
        incident_description_text=id1
    )
    res1 = service.analyze_claim(req1)
    assert res1.recommendation == RecommendationEnum.APPROVE

    # Claim 2: Missing Documents
    with open(claims_dir / "claim_002" / "claim_form.txt", "r", encoding="utf-8") as f:
        cf2 = f.read()
    with open(claims_dir / "claim_002" / "incident_description.txt", "r", encoding="utf-8") as f:
        id2 = f.read()
    with open(claims_dir / "claim_002" / "repair_estimate.txt", "r", encoding="utf-8") as f:
        ev2 = f.read()

    req2 = ClaimSubmissionRequest(
        claim_id="CLM-002",
        vehicle_type=VehicleTypeEnum.TWO_WHEELER,
        claim_type=ClaimTypeEnum.THEFT,
        incident_date="2026-08-28",
        claim_date="2026-08-30",
        insured_declared_value=85000.0,
        claimed_amount=85000.0,
        claim_form_text=cf2,
        evidence_doc_text=ev2,
        incident_description_text=id2
    )
    res2 = service.analyze_claim(req2)
    # Evidence doc is [MISSING DOCUMENT] text which fails sufficiency check
    assert res2.recommendation in [RecommendationEnum.REQUEST_INFORMATION, RecommendationEnum.ESCALATE]

    # Claim 3: Contradictions (Escalate)
    with open(claims_dir / "claim_003" / "claim_form.txt", "r", encoding="utf-8") as f:
        cf3 = f.read()
    with open(claims_dir / "claim_003" / "incident_description.txt", "r", encoding="utf-8") as f:
        id3 = f.read()
    with open(claims_dir / "claim_003" / "repair_estimate.txt", "r", encoding="utf-8") as f:
        ev3 = f.read()

    req3 = ClaimSubmissionRequest(
        claim_id="CLM-003",
        vehicle_type=VehicleTypeEnum.CAR,
        claim_type=ClaimTypeEnum.ACCIDENT,
        incident_date="2026-08-25",
        claim_date="2026-08-27",
        insured_declared_value=550000.0,
        claimed_amount=45000.0,
        claim_form_text=cf3,
        evidence_doc_text=ev3,
        incident_description_text=id3
    )
    res3 = service.analyze_claim(req3)
    assert res3.recommendation == RecommendationEnum.ESCALATE
    assert res3.escalate_to_human is True
    assert len(res3.contradictions) > 0
