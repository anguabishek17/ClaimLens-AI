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
    return HealthResponse(status="ok", project="ClaimLens AI")


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
