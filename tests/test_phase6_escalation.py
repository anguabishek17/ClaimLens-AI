import os
import pytest
from backend.models import ClaimSubmissionRequest
from backend.services.claim_analysis_service import ClaimAnalysisService
from backend.services.gemini_service import GeminiService
from backend.config import settings

HAS_GEMINI_KEY = bool((os.getenv("GEMINI_API_KEY") or settings.GEMINI_API_KEY or "").strip())
requires_gemini = pytest.mark.skipif(not HAS_GEMINI_KEY, reason="GEMINI_API_KEY not set")

@requires_gemini
def test_claim_003_contradictions_and_escalation():
    """
    Test Phase 6 specifically using claim_003 logic.
    Make sure the difficult claim generates: CONTRADICTION -> EVIDENCE -> ESCALATION
    """
    
    # claim_003 data as strings
    claim_form_text = """
    MOTOR INSURANCE CLAIM FORM
    Claim Reference: CLM-2026-003
    Vehicle Type: Private Car
    Registration Number: MH-12-AB-1234
    Make / Model: Maruti Suzuki Swift ZXi
    Insured Declared Value (IDV): Rs. 5,50,000
    Policy Number: POL-55443322-CAR
    
    INCIDENT & DRIVER DETAILS:
    Date of Incident: 2026-08-25
    Time of Incident: 16:30 IST
    Date of Claim Filing: 2026-08-27
    Driver Name: Vikram Patil
    Driver Licence Number: MH-12-2019008812
    
    DAMAGE REPORTED:
    Front bumper collision and front radiator grill damage sustained while parking inside garage.
    Claimed Amount: Rs. 45,000.
    """
    
    incident_description_text = """
    CUSTOMER INCIDENT STATEMENT
    Policyholder: Vikram Patil
    Vehicle Reg: MH-12-AB-1234
    
    On the afternoon of August 20, 2026 at around 4:30 PM, I was driving my Maruti Swift on the Pune-Mumbai highway. A passing heavy commercial truck swerved into my lane and clipped my right side wing mirror and scratched the right front and rear door panels. The side mirror glass snapped off. I managed to control the car and brought it back home.
    """
    
    repair_estimate_text = """
    GARAGE REPAIR ESTIMATE & FINAL BILL
    Bill No: INV-2026-0815
    Invoice Date: 2026-08-15
    Vehicle Reg No: MH-12-AB-1235
    Model: Maruti Suzuki Swift
    
    ITEMIZED REPAIR BILL:
    1. Rear Bumper Assembly Replacement: Rs. 24,000.00
    2. Rear Tail Lamp Assembly Left & Right: Rs. 16,000.00
    3. Rear Boot Lid Dents Repair & Painting: Rs. 18,000.00
    4. Painting & Labor Charges: Rs. 10,000.00
    ---------------------------------------------------
    TOTAL AMOUNT INVOICED: Rs. 68,000.00
    
    Work completed and handed over to customer on 2026-08-15.
    """

    request = ClaimSubmissionRequest(
        claim_id="CLM-003",
        claim_form_text=claim_form_text,
        incident_description_text=incident_description_text,
        evidence_doc_text=repair_estimate_text,
        incident_date="2026-08-25",
        claim_date="2026-08-27",
        insured_declared_value=550000.0,
        claimed_amount=45000.0,
        vehicle_type="CAR",
        claim_type="ACCIDENT"
    )

    gemini_service = GeminiService()
    service = ClaimAnalysisService(gemini_service=gemini_service)
    
    result = service.analyze_claim(request)

    # Validate Phase 6 Logic
    
    # 1. Contradictions exist and are extracted properly
    assert len(result.contradictions) > 0, "Expected contradictions to be found by LLM."
    
    # 2. Assert severity is found
    has_high_severity = any(c.severity == "HIGH" for c in result.contradictions)
    
    # 3. Escalation
    assert result.escalate_to_human is True, "Claim 003 should be escalated."
    assert result.escalation is not None
    assert result.escalation.escalation_required is True
    
    # 4. Check that fraud is not mentioned in human_action
    assert "fraud" not in result.escalation.human_action.lower()
    
    # It must contain the specific string for contradictions if high-risk contradiction exists
    if has_high_severity:
        assert result.escalation.human_action == "Potential inconsistency requiring investigator review."
