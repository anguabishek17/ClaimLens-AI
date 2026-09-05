"""
Unit tests for ClaimLens AI
Verifies /api/health and basic claim evaluation rules.
"""

from fastapi.testclient import TestClient
from app import app
from backend.models import ClaimSubmissionRequest, VehicleTypeEnum, ClaimTypeEnum
from backend.rules.policy_rules import PolicyRulesEngine

client = TestClient(app)


def test_health_check():
    """
    Verify GET /api/health returns status 200 and expected payload:
    {
      "status": "ok",
      "project": "ClaimLens AI"
    }
    """
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["project"] == "ClaimLens AI"


def test_policy_reporting_window_valid():
    request = ClaimSubmissionRequest(
        vehicle_type=VehicleTypeEnum.CAR,
        claim_type=ClaimTypeEnum.ACCIDENT,
        incident_date="2026-09-01",
        claim_date="2026-09-03",
        claim_form_text="Valid claim form text with more than 20 characters.",
        evidence_doc_text="Valid repair estimate text with more than 20 characters.",
        incident_description_text="Detailed customer description of accident."
    )
    finding = PolicyRulesEngine.check_reporting_window(request)
    assert finding is None  # Within 7 days window


def test_policy_reporting_window_exceeded():
    request = ClaimSubmissionRequest(
        vehicle_type=VehicleTypeEnum.CAR,
        claim_type=ClaimTypeEnum.ACCIDENT,
        incident_date="2026-08-01",
        claim_date="2026-09-01",
        claim_form_text="Valid claim form text with more than 20 characters.",
        evidence_doc_text="Valid repair estimate text with more than 20 characters.",
        incident_description_text="Detailed customer description of accident."
    )
    finding = PolicyRulesEngine.check_reporting_window(request)
    assert finding is not None
    assert finding.impact == "BLOCKS"
