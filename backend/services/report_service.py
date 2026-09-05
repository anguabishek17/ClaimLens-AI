"""
ClaimLens AI - Report Generation Service
Builds audit-ready evidence review summaries with exact citations.
"""

from typing import Dict, Any
from backend.models import ClaimReviewResult


class ReportService:
    """
    Generates human-readable audit summaries for insurance claim adjusters.
    """

    @staticmethod
    def generate_markdown_report(result: ClaimReviewResult) -> str:
        lines = [
            f"# ClaimLens AI — Claim Review Report [{result.claim_id}]",
            f"**Recommendation:** `{result.recommendation.value}`",
            f"**Human Escalation Required:** {'YES' if result.escalate_to_human else 'NO'}",
        ]
        if result.escalation_reason:
            lines.append(f"**Escalation Reason:** {result.escalation_reason}")

        lines.append("\n## 1. Document Completeness")
        for doc in result.document_completeness:
            status = "✅ Present" if doc.is_present else "❌ Missing"
            lines.append(f"- **{doc.document_name}**: {status}")

        if result.contradictions:
            lines.append("\n## 2. Surfaced Contradictions")
            for c in result.contradictions:
                lines.append(f"- **Conflict between [{c.source_a}] and [{c.source_b}]:** {c.description}")

        lines.append("\n## 3. Applicable Policy Clauses")
        for cl in result.applicable_clauses:
            lines.append(f"- **{cl.clause_id} ({cl.clause_title})** [{cl.impact.value}]: {cl.reasoning} *(Ref: {cl.source_citation})*")

        lines.append(f"\n## 4. Assessment Summary\n{result.summary_notes}")
        return "\n".join(lines)
