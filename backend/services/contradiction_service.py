import json
import logging
from typing import List
from backend.models import (
    ClaimSubmissionRequest,
    ContradictionFinding,
    ContradictionDocument,
)
from backend.services.gemini_service import GeminiService

logger = logging.getLogger(__name__)

class ContradictionService:
    @classmethod
    def detect_contradictions(cls, request: ClaimSubmissionRequest, gemini_service: GeminiService = None) -> List[ContradictionFinding]:
        if gemini_service is None:
            gemini_service = GeminiService()
            
        if not gemini_service.is_configured:
            logger.warning("GeminiService not configured. Skipping LLM contradiction detection.")
            return []
            
        system_prompt = """
You are a strict Contradiction Detection Engine for insurance claims.
Analyze the provided documents (Claim Form, Incident Description, FIR, Repair Estimate) for contradictions.
IMPORTANT RULES:
- Do not invent contradictions. Only report contradictions supported by extracted evidence.
- Check important entities: accident date, accident time, vehicle registration, vehicle model, policy number, incident type, damage description, claim amount, repair amount, theft details.
- NEVER claim or use the word 'Fraud'. Use neutral language like 'inconsistency'.
- Output ONLY valid JSON containing an array of contradiction objects.

Schema for each contradiction object:
{
  "field": "name of the field (e.g. accident_date, vehicle_registration)",
  "document_a": {
      "source": "Name of first document",
      "value": "Extracted value"
  },
  "document_b": {
      "source": "Name of second document",
      "value": "Extracted value"
  },
  "severity": "HIGH | MEDIUM | LOW",
  "explanation": "Brief explanation of the contradiction"
}

Return an array of these objects: [...]
If no contradictions are found, return an empty array: []
"""
        user_prompt = f"""
=== Claim Form ===
{request.claim_form_text or 'N/A'}

=== Incident Description ===
{request.incident_description_text or 'N/A'}

=== Evidence Document (FIR/Repair Estimate) ===
{request.evidence_doc_text or 'N/A'}
"""
        try:
            raw_response = gemini_service.generate_content(user_prompt, system_instruction=system_prompt)
            # Clean up markdown formatting if present
            cleaned = raw_response.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            elif cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()
            
            # Find JSON array
            start = cleaned.find("[")
            end = cleaned.rfind("]") + 1
            if start >= 0 and end > start:
                cleaned = cleaned[start:end]
            
            data = json.loads(cleaned)
            findings = []
            for item in data:
                findings.append(ContradictionFinding(
                    field=item.get("field", "unknown"),
                    document_a=ContradictionDocument(**item.get("document_a", {})),
                    document_b=ContradictionDocument(**item.get("document_b", {})),
                    severity=item.get("severity", "MEDIUM"),
                    explanation=item.get("explanation", "")
                ))
            return findings
        except Exception as e:
            logger.error(f"Error detecting contradictions via Gemini: {e}")
            return []
