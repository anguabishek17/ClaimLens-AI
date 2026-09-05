"""
ClaimLens AI — Phase 4 Test Suite
Tests for: Gemini connection, embedding generation, local retrieval, structured response.

These tests are designed to work in TWO modes:
  1. With GEMINI_API_KEY set → full integration tests against Gemini API.
  2. Without GEMINI_API_KEY → graceful degradation tests (keyword fallback, error dicts).
"""

import os
import sys
import json
import pytest
import numpy as np
from pathlib import Path
from unittest.mock import patch, MagicMock

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.config import settings
from backend.services.gemini_service import GeminiService
from backend.services.retrieval_service import (
    RetrievalService,
    RetrievalResult,
    LocalVectorIndex,
    chunk_text,
    _content_hash,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

HAS_GEMINI_KEY = bool(
    (os.getenv("GEMINI_API_KEY") or settings.GEMINI_API_KEY or "").strip()
)

requires_gemini = pytest.mark.skipif(
    not HAS_GEMINI_KEY,
    reason="GEMINI_API_KEY not set — skipping live API tests"
)


# ===========================================================================
# 1. Gemini Connection Tests
# ===========================================================================

class TestGeminiConnection:
    """Verify Gemini API key loading and connection health."""

    def test_api_key_not_hardcoded(self):
        """API key must come from env / settings, never hardcoded."""
        import inspect
        source = inspect.getsource(GeminiService.__init__)
        # Should reference env/settings, not contain a literal key
        assert "AIza" not in source, "API key appears hardcoded in source!"
        assert "os.getenv" in source or "settings.GEMINI_API_KEY" in source

    def test_unconfigured_service_is_graceful(self):
        """Service with empty key must not crash, must report unconfigured."""
        svc = GeminiService(api_key="")
        assert svc.is_configured is False

    def test_unconfigured_embed_returns_zero_vector(self):
        svc = GeminiService(api_key="")
        vec = svc.embed_text("test")
        assert isinstance(vec, list)
        assert len(vec) == 768
        assert all(v == 0.0 for v in vec)

    def test_unconfigured_structured_analysis_returns_error(self):
        svc = GeminiService(api_key="")
        result = svc.generate_structured_analysis("evidence", "clauses")
        assert isinstance(result, dict)
        assert result.get("_error") is True
        assert result.get("_error_code") == "GEMINI_NOT_CONFIGURED"
        assert result["recommendation"] == "ESCALATE"

    def test_test_connection_unconfigured(self):
        svc = GeminiService(api_key="")
        status = svc.test_connection()
        assert status["status"] == "error"

    @requires_gemini
    def test_live_connection(self):
        svc = GeminiService()
        status = svc.test_connection()
        assert status["status"] == "ok"
        assert status["embedding_ok"] is True
        assert status["embedding_dimension"] > 0


# ===========================================================================
# 2. Embedding Generation Tests
# ===========================================================================

class TestEmbeddingGeneration:
    """Test embed_text() and embed_batch()."""

    @requires_gemini
    def test_embed_text_returns_vector(self):
        svc = GeminiService()
        vec = svc.embed_text("Motor insurance claim for front bumper damage")
        assert isinstance(vec, list)
        assert len(vec) > 0
        # Gemini embeddings are typically 768-dim
        assert len(vec) >= 256

    @requires_gemini
    def test_embed_batch_returns_list_of_vectors(self):
        svc = GeminiService()
        texts = ["Claim form for accident", "Repair estimate total Rs 32000"]
        vecs = svc.embed_batch(texts)
        assert len(vecs) == 2
        assert all(isinstance(v, list) for v in vecs)
        assert all(len(v) > 0 for v in vecs)

    @requires_gemini
    def test_similar_texts_have_higher_similarity(self):
        """Semantically similar texts should have higher cosine similarity."""
        svc = GeminiService()
        v1 = np.array(svc.embed_text("car accident damage claim"))
        v2 = np.array(svc.embed_text("vehicle collision insurance claim"))
        v3 = np.array(svc.embed_text("chocolate cake recipe"))

        sim_12 = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))
        sim_13 = np.dot(v1, v3) / (np.linalg.norm(v1) * np.linalg.norm(v3))
        # Similar texts should score higher
        assert sim_12 > sim_13

    def test_generate_embedding_alias(self):
        """generate_embedding should be an alias for embed_text."""
        svc = GeminiService(api_key="")
        v1 = svc.embed_text("test")
        v2 = svc.generate_embedding("test")
        assert v1 == v2


# ===========================================================================
# 3. Local Vector Index Tests (unit — no API needed)
# ===========================================================================

class TestLocalVectorIndex:
    """Test the NumPy-backed LocalVectorIndex without any API calls."""

    def test_empty_index(self):
        idx = LocalVectorIndex()
        assert not idx.is_built
        assert idx.size == 0
        assert idx.search([1.0, 0.0, 0.0]) == []

    def test_build_and_search(self):
        idx = LocalVectorIndex()
        vectors = [
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
            [0.7, 0.7, 0.0],
        ]
        metadata = [
            {"clause_id": "C-01", "text": "accident coverage"},
            {"clause_id": "C-02", "text": "theft coverage"},
            {"clause_id": "C-03", "text": "fire coverage"},
            {"clause_id": "C-04", "text": "collision coverage"},
        ]
        idx.build(vectors, metadata, content_hash="test123")
        assert idx.is_built
        assert idx.size == 4

        # Search for vector close to [1, 0, 0]
        results = idx.search([1.0, 0.1, 0.0], top_k=2)
        assert len(results) == 2
        # First result should be C-01 or C-04 (both have large x component)
        top_meta, top_score = results[0]
        assert top_score > 0.5
        assert top_meta["clause_id"] in ("C-01", "C-04")

    def test_save_and_load(self, tmp_path):
        idx = LocalVectorIndex()
        vectors = [[1.0, 0.0], [0.0, 1.0]]
        metadata = [{"id": "a"}, {"id": "b"}]
        idx.build(vectors, metadata, content_hash="hash42")
        idx.save(tmp_path / "test_index")

        idx2 = LocalVectorIndex()
        assert idx2.load(tmp_path / "test_index")
        assert idx2.is_built
        assert idx2.size == 2
        assert idx2.matches_hash("hash42")
        assert not idx2.matches_hash("different")

    def test_load_nonexistent(self, tmp_path):
        idx = LocalVectorIndex()
        assert not idx.load(tmp_path / "nonexistent")


# ===========================================================================
# 4. Chunking Tests
# ===========================================================================

class TestChunking:
    """Test text chunking utility."""

    def test_short_text_single_chunk(self):
        chunks = chunk_text("Hello world")
        assert len(chunks) == 1
        assert chunks[0] == "Hello world"

    def test_empty_text(self):
        assert chunk_text("") == []
        assert chunk_text("   ") == []

    def test_long_text_multiple_chunks(self):
        words = " ".join([f"word{i}" for i in range(500)])
        chunks = chunk_text(words, max_tokens=100, overlap=20)
        assert len(chunks) > 1
        # Each chunk should have <= 100 words
        for chunk in chunks:
            assert len(chunk.split()) <= 100

    def test_content_hash_deterministic(self):
        items = ["hello", "world"]
        h1 = _content_hash(items)
        h2 = _content_hash(items)
        assert h1 == h2
        assert len(h1) == 16

    def test_content_hash_changes(self):
        h1 = _content_hash(["hello"])
        h2 = _content_hash(["world"])
        assert h1 != h2


# ===========================================================================
# 5. RetrievalResult Structure Tests
# ===========================================================================

class TestRetrievalResult:
    """Every result must contain required fields."""

    def test_required_fields(self):
        r = RetrievalResult(
            source="policy",
            text="The insurer will indemnify...",
            similarity_score=0.9123456,
            document_id="policy.json",
            clause_id="C-01",
        )
        d = r.to_dict()
        assert "source" in d
        assert "text" in d
        assert "similarity_score" in d
        assert "document_id" in d
        assert "clause_id" in d
        assert d["similarity_score"] == 0.912346  # rounded to 6 places

    def test_clause_id_optional(self):
        r = RetrievalResult(
            source="claim_form",
            text="Vehicle DL-01-AB-1234",
            similarity_score=0.75,
            document_id="DOC-ABC123",
        )
        d = r.to_dict()
        assert d["clause_id"] is None


# ===========================================================================
# 6. Retrieval Service Integration Tests
# ===========================================================================

class TestRetrievalServiceUnit:
    """Unit tests for RetrievalService (keyword fallback, no API key needed)."""

    def test_keyword_fallback_search_policy(self):
        """Without API key, search_policy should use keyword fallback."""
        svc = RetrievalService(gemini_service=GeminiService(api_key=""))
        results = svc.search_policy("theft burglary stolen vehicle FIR", top_k=3)
        # Should return results via keyword matching
        assert isinstance(results, list)
        if results:
            r = results[0]
            assert isinstance(r, RetrievalResult)
            assert r.source is not None
            assert r.text is not None
            assert r.similarity_score >= 0

    def test_keyword_fallback_search_evidence(self):
        svc = RetrievalService(gemini_service=GeminiService(api_key=""))
        evidence = [
            {"text": "Vehicle DL-01-AB-1234 had front bumper damage on 2026-09-01", "source": "claim_form", "document_id": "DOC-001"},
            {"text": "Repair estimate Rs 32000 for bumper and headlight", "source": "repair_estimate", "document_id": "DOC-002"},
        ]
        results = svc.search_claim_evidence(evidence, "bumper damage repair", top_k=2)
        assert isinstance(results, list)

    def test_search_relevant_clauses_backward_compat(self):
        """Legacy method should still return list of dicts."""
        svc = RetrievalService(gemini_service=GeminiService(api_key=""))
        results = svc.search_relevant_clauses("accident damage collision", top_k=3)
        assert isinstance(results, list)
        assert len(results) <= 3
        if results:
            assert isinstance(results[0], dict)

    def test_build_policy_index_no_key(self):
        svc = RetrievalService(gemini_service=GeminiService(api_key=""))
        result = svc.build_policy_index()
        assert result["status"] in ("degraded", "error")
        assert result["clause_count"] > 0


class TestRetrievalServiceLive:
    """Live integration tests requiring GEMINI_API_KEY."""

    @requires_gemini
    def test_build_policy_index(self):
        svc = RetrievalService()
        result = svc.build_policy_index(force=True)
        assert result["status"] == "ok"
        assert result["index_size"] > 0
        assert result["clause_count"] > 0

    @requires_gemini
    def test_search_policy_returns_structured_results(self):
        svc = RetrievalService()
        svc.build_policy_index()
        results = svc.search_policy("theft and burglary coverage FIR requirement", top_k=3)
        assert len(results) > 0
        for r in results:
            assert isinstance(r, RetrievalResult)
            d = r.to_dict()
            assert d["source"] is not None
            assert d["text"] != ""
            assert 0 <= d["similarity_score"] <= 1.0
            assert d["document_id"] is not None
            assert d["clause_id"] is not None

    @requires_gemini
    def test_search_claim_evidence_returns_structured_results(self):
        svc = RetrievalService()
        evidence = [
            {
                "text": "Vehicle Reg: DL-01-AB-1234. Model: Hyundai i20. Date of incident: 2026-09-01. "
                        "Minor collision with median barrier causing front bumper and headlight crack.",
                "source": "claim_form",
                "document_id": "DOC-CF-001",
            },
            {
                "text": "Authorized Service Center Estimate. Front bumper assembly Rs 18,000, "
                        "Right headlight unit Rs 8,500, Labor charges Rs 5,500. Total: Rs 32,000.",
                "source": "repair_estimate",
                "document_id": "DOC-RE-001",
            },
        ]
        results = svc.search_claim_evidence(evidence, "bumper damage headlight repair cost", top_k=3)
        assert len(results) > 0
        for r in results:
            d = r.to_dict()
            assert "source" in d
            assert "similarity_score" in d
            assert "document_id" in d

    @requires_gemini
    def test_cached_index_reuse(self):
        """Second build should use cached index (no re-embedding)."""
        svc = RetrievalService()
        r1 = svc.build_policy_index(force=True)
        assert r1["status"] == "ok"
        assert r1["cached"] is False

        r2 = svc.build_policy_index(force=False)
        assert r2["status"] == "ok"
        assert r2["cached"] is True


# ===========================================================================
# 7. Structured Response Tests
# ===========================================================================

class TestStructuredResponse:
    """Test Gemini structured analysis parsing and schema compliance."""

    def test_parse_valid_json(self):
        raw = json.dumps({
            "findings": [{"observation": "Bumper damaged", "source_document": "claim_form", "impact": "SUPPORTS"}],
            "missing_documents": [],
            "contradictions": [],
            "applicable_clauses": [{"clause_id": "C-01", "clause_title": "Accident Coverage", "impact": "SUPPORTS", "reasoning": "Applicable"}],
            "recommendation": "APPROVE",
            "escalation_required": False,
            "reasoning": ["Step 1: All docs present", "Step 2: No contradictions"],
        })
        result = GeminiService._parse_structured_response(raw)
        assert result["recommendation"] == "APPROVE"
        assert len(result["findings"]) == 1
        assert len(result["reasoning"]) == 2
        assert result["escalation_required"] is False

    def test_parse_json_with_markdown_fences(self):
        raw = "```json\n" + json.dumps({
            "findings": [],
            "missing_documents": [],
            "contradictions": [],
            "applicable_clauses": [],
            "recommendation": "REJECT",
            "escalation_required": False,
            "reasoning": ["Invalid licence"],
        }) + "\n```"
        result = GeminiService._parse_structured_response(raw)
        assert result["recommendation"] == "REJECT"

    def test_parse_garbage_returns_escalate(self):
        result = GeminiService._parse_structured_response("This is not JSON at all")
        assert result["recommendation"] == "ESCALATE"
        assert result["escalation_required"] is True
        assert result.get("_parse_error") is True

    def test_missing_keys_get_defaults(self):
        raw = json.dumps({"recommendation": "APPROVE"})
        result = GeminiService._parse_structured_response(raw)
        assert result["recommendation"] == "APPROVE"
        assert result["findings"] == []
        assert result["missing_documents"] == []
        assert result["contradictions"] == []
        assert result["applicable_clauses"] == []
        assert isinstance(result["reasoning"], list)

    def test_error_response_structure(self):
        result = GeminiService._error_response("TEST_ERROR", "Something went wrong")
        assert result["_error"] is True
        assert result["_error_code"] == "TEST_ERROR"
        assert result["recommendation"] == "ESCALATE"
        assert result["escalation_required"] is True
        assert len(result["reasoning"]) == 1

    @requires_gemini
    def test_live_structured_analysis(self):
        """End-to-end: send real evidence to Gemini and verify structured JSON back."""
        svc = GeminiService()
        result = svc.generate_structured_analysis(
            claim_evidence_text=(
                "Vehicle Reg: DL-01-AB-1234. Model: Hyundai i20. Incident date: 2026-09-01. "
                "Driver had valid DL. Minor collision with road divider. "
                "Repair estimate: Front bumper Rs 18,000, Headlight Rs 8,500, Labor Rs 5,500. Total Rs 32,000."
            ),
            relevant_clauses_text=(
                "C-01: Accidental Loss and Damage Coverage — covers collision damage. "
                "C-08: Claim must be reported within 7 days. "
                "C-12: IDV cap applies."
            ),
            deterministic_findings_text="All mandatory documents present. Reporting window: 2 days (within limit).",
        )
        # Must be a dict with all schema keys
        assert isinstance(result, dict)
        assert "findings" in result
        assert "recommendation" in result
        assert result["recommendation"] in ("APPROVE", "REJECT", "REQUEST INFORMATION", "ESCALATE")
        assert "reasoning" in result
        assert isinstance(result["reasoning"], list)


# ===========================================================================
# 8. API Route Tests (via FastAPI TestClient)
# ===========================================================================

class TestAPIRoutes:
    """Test Phase 4 API endpoints."""

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from app import app
        return TestClient(app)

    def test_health(self, client):
        r = client.get("/api/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_gemini_health(self, client):
        r = client.get("/api/health/gemini")
        assert r.status_code == 200
        data = r.json()
        assert "status" in data
        assert "embedding_model" in data
        # The actual API key VALUE must never appear in the response
        response_text = json.dumps(data)
        key = os.getenv("GEMINI_API_KEY", "")
        if key and len(key) > 10:
            assert key not in response_text, "Actual API key value leaked in /api/health/gemini!"

    def test_build_index_endpoint(self, client):
        r = client.post("/api/retrieval/build-index")
        assert r.status_code == 200
        data = r.json()
        assert "status" in data
        assert "clause_count" in data

    def test_search_policy_endpoint(self, client):
        r = client.post(
            "/api/retrieval/search-policy",
            json={"query": "theft coverage FIR requirement", "top_k": 3}
        )
        assert r.status_code == 200
        data = r.json()
        assert "results" in data
        assert "count" in data

    def test_search_evidence_endpoint(self, client):
        r = client.post(
            "/api/retrieval/search-evidence",
            json={
                "evidence_texts": [
                    {"text": "Front bumper damaged in collision", "source": "claim_form", "document_id": "D1"},
                ],
                "query": "bumper damage",
                "top_k": 2,
            }
        )
        assert r.status_code == 200
        data = r.json()
        assert "results" in data

    def test_structured_analysis_endpoint(self, client):
        r = client.post(
            "/api/analysis/structured",
            json={
                "claim_evidence_text": "Vehicle DL-01-AB-1234, bumper damage, Rs 32000",
                "relevant_clauses_text": "C-01: Accident coverage",
            }
        )
        assert r.status_code == 200
        data = r.json()
        # Should have schema keys or error keys
        assert "recommendation" in data or "_error" in data

    def test_api_key_not_exposed(self, client):
        """Ensure no endpoint leaks the API key."""
        endpoints = [
            ("/api/health", "GET"),
            ("/api/health/gemini", "GET"),
        ]
        for path, method in endpoints:
            if method == "GET":
                r = client.get(path)
            else:
                r = client.post(path)
            body = r.text
            key = os.getenv("GEMINI_API_KEY", "")
            if key and len(key) > 10:
                assert key not in body, f"API key leaked in {path}!"
