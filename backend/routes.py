"""
ClaimLens AI - API Endpoints
Defines REST API routes including health check, claim review, retrieval, and Gemini pipeline.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from backend.models import (
    HealthResponse,
    ClaimSubmissionRequest,
    ClaimReviewResult,
    ClaimUploadRequest,
)
from backend.services.claim_analysis_service import ClaimAnalysisService
from backend.services.gemini_service import GeminiService
from backend.services.retrieval_service import RetrievalService

router = APIRouter(prefix="/api", tags=["Claims & Health"])

# Shared service instances (singleton per process)
_gemini_service = GeminiService()
_retrieval_service = RetrievalService(gemini_service=_gemini_service)
claim_service = ClaimAnalysisService(gemini_service=_gemini_service)


# ---------------------------------------------------------------------------
# Request / Response Models for Phase 4 endpoints
# ---------------------------------------------------------------------------

class PolicySearchRequest(BaseModel):
    query: str = Field(..., description="Natural language query to search policy clauses")
    top_k: int = Field(5, ge=1, le=20, description="Number of results to return")


class EvidenceDoc(BaseModel):
    text: str
    source: str = "unknown"
    document_id: str = "unknown"


class EvidenceSearchRequest(BaseModel):
    evidence_texts: List[EvidenceDoc]
    query: str
    top_k: int = Field(5, ge=1, le=20)


class StructuredAnalysisRequest(BaseModel):
    claim_evidence_text: str = Field(..., description="Combined claim evidence")
    relevant_clauses_text: str = Field(..., description="Relevant policy clauses text")
    deterministic_findings_text: str = Field("", description="Pre-verified deterministic findings")


# ---------------------------------------------------------------------------
# Health & Diagnostics
# ---------------------------------------------------------------------------

@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint returning system status and project name.
    """
    # Quick check if policy is loaded
    from pathlib import Path
    policy_loaded = (Path("data/policy/policy.json").exists())
    return HealthResponse(status="ok", project="ClaimLens AI")

@router.get("/claims")
async def get_all_claims():
    """
    Returns a list of all available claims for the dashboard.
    """
    import json
    from pathlib import Path
    
    claims_dir = Path("data/claims")
    claims_list = []
    
    # Try reading sample_claims.json first as it has summary data
    sample_claims_path = claims_dir / "sample_claims.json"
    if sample_claims_path.exists():
        with open(sample_claims_path, "r", encoding="utf-8") as f:
            sample_data = json.load(f)
            # Adapt it slightly for dashboard if needed
            for c in sample_data:
                claims_list.append({
                    "id": c.get("id"),
                    "name": c.get("name"),
                    "vehicle_type": c.get("vehicle_type"),
                    "incident_type": c.get("claim_type"),
                    "claimed_amount": c.get("claimed_amount"),
                    "status": "ESCALATION" if "Escalation" in c.get("name", "") else ("REQUEST INFORMATION" if "Missing" in c.get("name", "") else "APPROVE")
                })
    
    # If we want to read from directories directly:
    for d in claims_dir.glob("claim_*"):
        if d.is_dir():
            claim_json = d / "claim.json"
            if claim_json.exists():
                with open(claim_json, "r", encoding="utf-8") as f:
                    cdata = json.load(f)
                    # Check if already added by sample_claims
                    if not any(x["id"] == cdata.get("claim_id") for x in claims_list):
                        claims_list.append({
                            "id": cdata.get("claim_id"),
                            "name": cdata.get("name"),
                            "vehicle_type": cdata.get("vehicle_type"),
                            "incident_type": cdata.get("claim_type"),
                            "claimed_amount": cdata.get("claimed_amount"),
                            "status": cdata.get("status_expected", "REVIEW")
                        })
    return {"claims": claims_list, "count": len(claims_list)}

@router.get("/policy")
async def get_policy_clauses():
    """
    Returns all policy clauses.
    """
    import json
    from pathlib import Path
    
    policy_file = Path("data/policy/policy.json")
    if not policy_file.exists():
        return {"clauses": [], "count": 0}
        
    with open(policy_file, "r", encoding="utf-8") as f:
        clauses = json.load(f)
        return {"clauses": clauses, "count": len(clauses)}

@router.get("/evidence")
async def get_all_evidence():
    """
    Scans claims directories to return a list of available/missing evidence.
    """
    import json
    from pathlib import Path
    
    claims_dir = Path("data/claims")
    evidence_list = []
    
    for d in claims_dir.glob("claim_*"):
        if d.is_dir():
            claim_id = "unknown"
            claim_json = d / "claim.json"
            if claim_json.exists():
                with open(claim_json, "r", encoding="utf-8") as f:
                    cdata = json.load(f)
                    claim_id = cdata.get("claim_id", "unknown")
            else:
                claim_id = d.name.upper()

            # Check for specific files
            files_to_check = {
                "claim_form.txt": "Claim Form",
                "incident_description.txt": "Incident Description",
                "repair_estimate.txt": "Repair Estimate",
                "fir.txt": "FIR"
            }
            
            for filename, doc_type in files_to_check.items():
                file_path = d / filename
                if file_path.exists():
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    evidence_list.append({
                        "claim_id": claim_id,
                        "document_type": doc_type,
                        "status": "Available",
                        "content": content
                    })
                else:
                    evidence_list.append({
                        "claim_id": claim_id,
                        "document_type": doc_type,
                        "status": "Missing",
                        "content": ""
                    })
                    
    return {"evidence": evidence_list, "count": len(evidence_list)}


@router.get("/health/gemini")
async def gemini_health():
    """
    Check Gemini API connectivity and configuration status.
    Does NOT expose the API key.
    """
    return _gemini_service.test_connection()


# ---------------------------------------------------------------------------
# Claim Review (main orchestration)
# ---------------------------------------------------------------------------

@router.post("/claims/review", response_model=ClaimReviewResult)
async def review_claim(request: ClaimSubmissionRequest):
    """
    Evaluates motor insurance claim documents against policy rules and clauses.
    """
    try:
        result = claim_service.analyze_claim(request)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Claim review failed: {str(e)}")

@router.post("/review/upload", response_model=ClaimReviewResult)
async def upload_and_review_claim(request: ClaimUploadRequest):
    """
    Accepts base64 encoded files, extracts text, and runs the claim analysis pipeline.
    """
    import base64
    import uuid
    from backend.services.document_ingestor import DocumentIngestor
    
    try:
        ingestor = DocumentIngestor()
        temp_claim_id = f"UP-{uuid.uuid4().hex[:6].upper()}"
        
        claim_form_text = ""
        incident_description_text = ""
        evidence_doc_text = ""
        
        for f in request.files:
            content_bytes = base64.b64decode(f.content_b64)
            result = ingestor.ingest_content(content=content_bytes, filename=f.filename, claim_id=temp_claim_id)
            
            if result.success and result.evidence:
                extracted_text = "\n".join(s.text for s in result.evidence.sections)
                
                if f.document_type == "claim_form":
                    claim_form_text += extracted_text + "\n"
                elif f.document_type == "incident_description":
                    incident_description_text += extracted_text + "\n"
                elif f.document_type in ["fir", "repair_estimate"]:
                    evidence_doc_text += extracted_text + "\n\n"
                    
        # Default missing docs to "Missing" instead of empty string if they are completely empty
        # But the analysis service handles empty strings. Let's just pass what we extracted.
        
        submission_req = ClaimSubmissionRequest(
            claim_id=temp_claim_id,
            vehicle_type="CAR", # We can default to CAR or extract it later.
            claim_type=request.claim_type,
            claim_form_text=claim_form_text.strip() if claim_form_text else "[MISSING DOCUMENT]",
            evidence_doc_text=evidence_doc_text.strip() if evidence_doc_text else "[MISSING DOCUMENT]",
            incident_description_text=incident_description_text.strip() if incident_description_text else "[MISSING DOCUMENT]",
        )
        
        analysis_result = claim_service.analyze_claim(submission_req)
        return analysis_result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload and review failed: {str(e)}")


# ---------------------------------------------------------------------------
# Phase 4: Retrieval Pipeline Endpoints
# ---------------------------------------------------------------------------

@router.post("/retrieval/build-index")
async def build_policy_index(force: bool = False):
    """
    Build or rebuild the local policy clause vector index.
    Uses precomputed cache to avoid re-embedding on every call.
    """
    try:
        result = _retrieval_service.build_policy_index(force=force)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Index build failed: {str(e)}")


@router.post("/retrieval/search-policy")
async def search_policy(request: PolicySearchRequest):
    """
    Semantic search over policy clauses using Gemini embeddings + local NumPy index.
    Returns structured results with source, text, similarity_score, document_id, clause_id.
    """
    try:
        results = _retrieval_service.search_policy(request.query, top_k=request.top_k)
        return {"results": [r.to_dict() for r in results], "count": len(results)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Policy search failed: {str(e)}")


@router.post("/retrieval/search-evidence")
async def search_claim_evidence(request: EvidenceSearchRequest):
    """
    Build an ephemeral vector index over claim evidence documents and search.
    """
    try:
        evidence_dicts = [{"text": e.text, "source": e.source, "document_id": e.document_id} for e in request.evidence_texts]
        results = _retrieval_service.search_claim_evidence(evidence_dicts, request.query, top_k=request.top_k)
        return {"results": [r.to_dict() for r in results], "count": len(results)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Evidence search failed: {str(e)}")


# ---------------------------------------------------------------------------
# Phase 4: Gemini Structured Analysis Endpoint
# ---------------------------------------------------------------------------

@router.post("/analysis/structured")
async def structured_analysis(request: StructuredAnalysisRequest):
    """
    Send evidence + policy clauses to Gemini for structured JSON reasoning.
    Returns the structured analysis schema — never free-form text.
    """
    try:
        result = _gemini_service.generate_structured_analysis(
            claim_evidence_text=request.claim_evidence_text,
            relevant_clauses_text=request.relevant_clauses_text,
            deterministic_findings_text=request.deterministic_findings_text,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Structured analysis failed: {str(e)}")
