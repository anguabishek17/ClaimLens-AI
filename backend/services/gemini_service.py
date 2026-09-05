"""
ClaimLens AI — Gemini AI Service (Phase 4)
Integrates with Google Gemini API for embeddings and structured claim analysis.

Constraints:
- Gemini is the ONLY external API permitted.
- Embedding model: gemini-embedding-001
- LLM model: gemini-1.5-flash (configurable via settings)
- API key from GEMINI_API_KEY environment variable — NEVER hardcoded.
- Structured JSON responses only — no free-form LLM output controls the app.
"""

import os
import json
import logging
from typing import List, Optional, Dict, Any
from backend.config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Structured Analysis Schema
# ---------------------------------------------------------------------------

ANALYSIS_SCHEMA = {
    "findings": "list of evidence observations",
    "missing_documents": "list of documents that are absent or incomplete",
    "contradictions": "list of cross-document inconsistencies",
    "applicable_clauses": "list of policy clauses relevant to this claim",
    "recommendation": "one of: APPROVE, REJECT, REQUEST INFORMATION, ESCALATE",
    "escalation_required": "boolean — true if human review needed",
    "reasoning": "list of step-by-step reasoning chains",
}


class GeminiService:
    """
    Dedicated wrapper for Gemini API operations (Embeddings & LLM).
    Adheres strictly to PS02 constraints:
    - Only external API permitted: Gemini
    - Embedding model: gemini-embedding-001
    - API key loaded from GEMINI_API_KEY environment variable
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY") or settings.GEMINI_API_KEY
        self._client = None
        self._is_configured = False
        if self.api_key and self.api_key.strip():
            try:
                from google import genai
                self._client = genai.Client(api_key=self.api_key.strip())
                self._is_configured = True
            except Exception as e:
                logger.warning(f"Failed to initialize google.genai Client: {e}")

    @property
    def is_configured(self) -> bool:
        return self._is_configured

    # ------------------------------------------------------------------
    # Connection / Health Check
    # ------------------------------------------------------------------

    def test_connection(self) -> Dict[str, Any]:
        """
        Verify that the Gemini API key is valid and the service is reachable.
        Returns a status dict with connection details.
        """
        if not self.is_configured or self._client is None:
            return {
                "status": "error",
                "message": "Gemini API key not configured. Set GEMINI_API_KEY in environment.",
                "embedding_model": settings.EMBEDDING_MODEL,
                "llm_model": settings.LLM_MODEL,
            }
        try:
            # Quick embedding test with a minimal string
            response = self._client.models.embed_content(
                model=settings.EMBEDDING_MODEL,
                contents="test"
            )
            embedding_ok = False
            dim = 0
            if hasattr(response, "embedding") and response.embedding:
                embedding_ok = True
                dim = len(response.embedding.values or [])
            elif hasattr(response, "embeddings") and response.embeddings:
                embedding_ok = True
                dim = len(response.embeddings[0].values or [])

            return {
                "status": "ok",
                "embedding_model": settings.EMBEDDING_MODEL,
                "llm_model": settings.LLM_MODEL,
                "embedding_ok": embedding_ok,
                "embedding_dimension": dim,
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Gemini connection test failed: {e}",
                "embedding_model": settings.EMBEDDING_MODEL,
                "llm_model": settings.LLM_MODEL,
            }

    # ------------------------------------------------------------------
    # Embeddings
    # ------------------------------------------------------------------

    def embed_text(self, text: str, model: Optional[str] = None) -> List[float]:
        """
        Generate a vector embedding for a single text string using gemini-embedding-001.
        Returns a zero vector if the API is unavailable (graceful degradation).
        """
        if not self.is_configured or self._client is None:
            logger.warning("Gemini API key not configured. Returning zero vector.")
            return [0.0] * 768

        target_model = model or settings.EMBEDDING_MODEL
        try:
            response = self._client.models.embed_content(
                model=target_model,
                contents=text
            )
            if hasattr(response, "embedding") and response.embedding:
                return response.embedding.values or []
            if hasattr(response, "embeddings") and response.embeddings:
                return response.embeddings[0].values or []
            return [0.0] * 768
        except Exception as e:
            logger.error(f"Error generating embedding with {target_model}: {e}")
            return [0.0] * 768

    def embed_batch(self, texts: List[str], model: Optional[str] = None) -> List[List[float]]:
        """
        Generate embeddings for multiple texts. Calls embed_text per item.
        A production version could batch via the API; kept simple for hackathon.
        """
        return [self.embed_text(t, model) for t in texts]

    # Keep old name as alias so existing code that calls generate_embedding still works
    def generate_embedding(self, text: str, model: Optional[str] = None) -> List[float]:
        """Alias for embed_text — backward compatibility."""
        return self.embed_text(text, model)

    # ------------------------------------------------------------------
    # LLM — Raw Content Generation
    # ------------------------------------------------------------------

    def generate_content(self, prompt: str, system_instruction: Optional[str] = None) -> str:
        """
        Executes grounded reasoning with Gemini LLM. Returns raw text.
        """
        if not self.is_configured or self._client is None:
            return "Gemini API key not set. Please provide GEMINI_API_KEY in environment."

        try:
            config = {}
            if system_instruction:
                config["system_instruction"] = system_instruction
            response = self._client.models.generate_content(
                model=settings.LLM_MODEL,
                contents=prompt,
                config=config if config else None
            )
            return response.text if response and response.text else ""
        except Exception as e:
            logger.error(f"Error calling Gemini LLM: {e}")
            return f"Error executing AI analysis: {str(e)}"

    # ------------------------------------------------------------------
    # LLM — Structured Claim Analysis (Phase 4)
    # ------------------------------------------------------------------

    def generate_structured_analysis(
        self,
        claim_evidence_text: str,
        relevant_clauses_text: str,
        deterministic_findings_text: str = "",
    ) -> Dict[str, Any]:
        """
        Send curated evidence + relevant clauses to Gemini and demand
        structured JSON back. Free-form responses do NOT control the app.

        Returns a dict matching ANALYSIS_SCHEMA on success, or a graceful
        error dict on failure.
        """
        if not self.is_configured or self._client is None:
            return self._error_response(
                "GEMINI_NOT_CONFIGURED",
                "Gemini API key not set. Structured analysis unavailable."
            )

        system_instruction = self._build_system_prompt()
        user_prompt = self._build_user_prompt(
            claim_evidence_text,
            relevant_clauses_text,
            deterministic_findings_text,
        )

        try:
            config = {"system_instruction": system_instruction}
            response = self._client.models.generate_content(
                model=settings.LLM_MODEL,
                contents=user_prompt,
                config=config,
            )

            raw_text = response.text if response and response.text else ""
            if not raw_text.strip():
                return self._error_response(
                    "EMPTY_RESPONSE",
                    "Gemini returned an empty response."
                )

            return self._parse_structured_response(raw_text)

        except Exception as e:
            logger.error(f"Gemini structured analysis failed: {e}")
            return self._error_response("GEMINI_ERROR", str(e))

    # ------------------------------------------------------------------
    # Prompt Construction
    # ------------------------------------------------------------------

    @staticmethod
    def _build_system_prompt() -> str:
        return (
            "You are ClaimLens AI, an insurance claims evidence review assistant.\n"
            "Your task is to analyze motor insurance claim evidence against policy clauses.\n\n"
            "RULES:\n"
            "1. You MUST respond with ONLY valid JSON — no markdown, no commentary.\n"
            "2. Use the exact schema below.\n"
            "3. Base every finding on the evidence provided. Cite sources.\n"
            "4. If documents are contradictory, list each contradiction with severity.\n"
            "5. Never allege fraud. Flag inconsistencies for human review.\n"
            "6. recommendation must be one of: APPROVE, REJECT, REQUEST INFORMATION, ESCALATE.\n"
            "7. Set escalation_required to true when contradictions exist or claim amount is suspicious.\n\n"
            "RESPONSE SCHEMA:\n"
            "{\n"
            '  "findings": [\n'
            '    {"observation": "...", "source_document": "...", "impact": "SUPPORTS|BLOCKS|CONDITIONAL"}\n'
            "  ],\n"
            '  "missing_documents": [\n'
            '    {"document_name": "...", "reason": "..."}\n'
            "  ],\n"
            '  "contradictions": [\n'
            '    {"source_a": "...", "source_b": "...", "description": "...", "severity": "HIGH|MEDIUM|LOW"}\n'
            "  ],\n"
            '  "applicable_clauses": [\n'
            '    {"clause_id": "...", "clause_title": "...", "impact": "SUPPORTS|BLOCKS|CONDITIONAL", "reasoning": "..."}\n'
            "  ],\n"
            '  "recommendation": "APPROVE|REJECT|REQUEST INFORMATION|ESCALATE",\n'
            '  "escalation_required": false,\n'
            '  "reasoning": ["step 1...", "step 2..."]\n'
            "}"
        )

    @staticmethod
    def _build_user_prompt(
        claim_evidence: str,
        relevant_clauses: str,
        deterministic_findings: str,
    ) -> str:
        parts = [
            "=== CLAIM EVIDENCE ===",
            claim_evidence,
            "",
            "=== RELEVANT POLICY CLAUSES ===",
            relevant_clauses,
        ]
        if deterministic_findings.strip():
            parts.extend([
                "",
                "=== DETERMINISTIC RULE-CHECK FINDINGS (already verified) ===",
                deterministic_findings,
            ])
        parts.extend([
            "",
            "Analyze the above evidence against the policy clauses.",
            "Return ONLY the JSON object as specified in the system instructions.",
        ])
        return "\n".join(parts)

    # ------------------------------------------------------------------
    # Response Parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_structured_response(raw_text: str) -> Dict[str, Any]:
        """
        Parse Gemini's text output into structured JSON.
        Handles common issues: markdown fences, trailing commas, BOM, etc.
        """
        cleaned = raw_text.strip()

        # Strip markdown code fences if present
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            # Remove first line (```json or ```) and last line (```)
            lines = [l for l in lines if not l.strip().startswith("```")]
            cleaned = "\n".join(lines).strip()

        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError:
            # Last-resort: try to find JSON object in the text
            start = cleaned.find("{")
            end = cleaned.rfind("}") + 1
            if start >= 0 and end > start:
                try:
                    parsed = json.loads(cleaned[start:end])
                except json.JSONDecodeError as e:
                    return {
                        "findings": [],
                        "missing_documents": [],
                        "contradictions": [],
                        "applicable_clauses": [],
                        "recommendation": "ESCALATE",
                        "escalation_required": True,
                        "reasoning": [f"Failed to parse Gemini response as JSON: {e}"],
                        "_raw_response": raw_text[:500],
                        "_parse_error": True,
                    }
            else:
                return {
                    "findings": [],
                    "missing_documents": [],
                    "contradictions": [],
                    "applicable_clauses": [],
                    "recommendation": "ESCALATE",
                    "escalation_required": True,
                    "reasoning": ["Gemini did not return valid JSON."],
                    "_raw_response": raw_text[:500],
                    "_parse_error": True,
                }

        # Ensure all expected keys exist with defaults
        defaults: Dict[str, Any] = {
            "findings": [],
            "missing_documents": [],
            "contradictions": [],
            "applicable_clauses": [],
            "recommendation": "ESCALATE",
            "escalation_required": False,
            "reasoning": [],
        }
        for key, default in defaults.items():
            if key not in parsed:
                parsed[key] = default

        return parsed

    @staticmethod
    def _error_response(code: str, message: str) -> Dict[str, Any]:
        """Return a structured error response instead of crashing."""
        return {
            "findings": [],
            "missing_documents": [],
            "contradictions": [],
            "applicable_clauses": [],
            "recommendation": "ESCALATE",
            "escalation_required": True,
            "reasoning": [f"[{code}] {message}"],
            "_error": True,
            "_error_code": code,
        }
