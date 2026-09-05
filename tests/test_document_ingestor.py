"""
ClaimLens AI - Tests for Document Ingestion & Evidence Extraction (Phase 3)
Tests: valid document, empty document, unsupported file, malformed input,
       directory ingestion, document type classification, PDF fallback.
"""

import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

# Ensure project root is on the path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.services.document_ingestor import (
    DocumentIngestor,
    DocumentEvidence,
    DocumentTypeClassifier,
    DocumentCategory,
    TextExtractor,
    IngestionResult,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def ingestor(tmp_path):
    """Create a DocumentIngestor writing to a temp processed dir."""
    return DocumentIngestor(processed_dir=tmp_path / "processed")


@pytest.fixture
def sample_claim_form_txt():
    return (
        "MOTOR INSURANCE CLAIM FORM\n"
        "Claim Reference: CLM-2026-TEST\n"
        "Vehicle Type: Private Car\n"
        "Registration Number: DL-01-AB-1234\n"
        "Policy Number: POL-99887766-CAR\n"
        "\n"
        "INCIDENT & DRIVER DETAILS:\n"
        "Date of Incident: 2026-09-01\n"
        "Driver Name: Test Driver\n"
        "\n"
        "DAMAGE REPORTED:\n"
        "Front bumper cracked.\n"
        "Estimated Repair Amount: Rs. 32,000.\n"
    )


@pytest.fixture
def sample_json_content():
    return json.dumps({
        "claim_id": "CLM-TEST-001",
        "policy_id": "MIP-2026-001",
        "claimant_name": "Test User",
        "vehicle_registration": "MH12AB1234",
        "incident_date": "2026-08-10",
        "claim_type": "accident",
        "claimed_amount": 85000,
    })


@pytest.fixture
def sample_markdown_content():
    return (
        "# Incident Report\n\n"
        "On 10th August 2026, the vehicle was involved in an accident.\n\n"
        "## Damage Details\n\n"
        "Front bumper and headlight damaged.\n\n"
        "## Claim Amount\n\n"
        "Rs. 85,000.\n"
    )


# ---------------------------------------------------------------------------
# 1. Valid Document Ingestion
# ---------------------------------------------------------------------------

class TestValidDocumentIngestion:

    def test_ingest_valid_txt_file(self, ingestor, sample_claim_form_txt, tmp_path):
        """A valid TXT claim form should produce sections with correct provenance."""
        fp = tmp_path / "claim_form.txt"
        fp.write_text(sample_claim_form_txt, encoding="utf-8")

        result = ingestor.ingest_file(fp, claim_id="CLM-TEST-001")

        assert result.success is True
        assert result.error is None
        assert result.evidence is not None
        assert result.evidence.claim_id == "CLM-TEST-001"
        assert result.evidence.file_format == "txt"
        assert len(result.evidence.sections) > 0
        # Every section must have required fields
        for section in result.evidence.sections:
            assert section.section_id
            assert section.text
            assert section.source_reference

    def test_ingest_valid_json_file(self, ingestor, sample_json_content, tmp_path):
        """A valid JSON file should be parsed into flattened key-value sections."""
        fp = tmp_path / "claim.json"
        fp.write_text(sample_json_content, encoding="utf-8")

        result = ingestor.ingest_file(fp, claim_id="CLM-TEST-001")

        assert result.success is True
        ev = result.evidence
        assert ev is not None
        assert ev.file_format == "json"
        assert len(ev.sections) >= 5  # at least 5 fields
        # Check that claim_id field was extracted
        texts = [s.text for s in ev.sections]
        assert any("CLM-TEST-001" in t for t in texts)

    def test_ingest_valid_markdown_file(self, ingestor, sample_markdown_content, tmp_path):
        """A valid markdown file should be split on headings."""
        fp = tmp_path / "report.md"
        fp.write_text(sample_markdown_content, encoding="utf-8")

        result = ingestor.ingest_file(fp, claim_id="CLM-TEST-001")

        assert result.success is True
        ev = result.evidence
        assert ev is not None
        assert ev.file_format == "md"
        assert len(ev.sections) >= 3  # 3 headings

    def test_ingest_content_directly(self, ingestor, sample_claim_form_txt):
        """Ingesting raw content without a file path should work."""
        result = ingestor.ingest_content(
            content=sample_claim_form_txt,
            filename="claim_form.txt",
            claim_id="CLM-INLINE-001",
        )

        assert result.success is True
        assert result.evidence.claim_id == "CLM-INLINE-001"
        assert len(result.evidence.sections) > 0

    def test_evidence_persisted_to_disk(self, ingestor, sample_claim_form_txt, tmp_path):
        """Processed evidence JSON must be saved to the processed directory."""
        fp = tmp_path / "claim_form.txt"
        fp.write_text(sample_claim_form_txt, encoding="utf-8")

        result = ingestor.ingest_file(fp, claim_id="CLM-PERSIST-001")
        assert result.success is True

        # Check file exists in processed directory
        claim_dir = ingestor.processed_dir / "CLM-PERSIST-001"
        assert claim_dir.exists()
        json_files = list(claim_dir.glob("*.json"))
        assert len(json_files) >= 1

        # Verify JSON is loadable
        with open(json_files[0], "r") as f:
            data = json.load(f)
        assert data["claim_id"] == "CLM-PERSIST-001"
        assert len(data["sections"]) > 0


# ---------------------------------------------------------------------------
# 2. Empty Document Handling
# ---------------------------------------------------------------------------

class TestEmptyDocumentHandling:

    def test_empty_txt_file(self, ingestor, tmp_path):
        """An empty TXT file should return EMPTY_DOCUMENT error."""
        fp = tmp_path / "empty.txt"
        fp.write_text("", encoding="utf-8")

        result = ingestor.ingest_file(fp, claim_id="CLM-EMPTY")

        assert result.success is False
        assert result.error is not None
        assert result.error.error_code == "EMPTY_DOCUMENT"
        assert result.error.recoverable is True

    def test_whitespace_only_txt(self, ingestor, tmp_path):
        """A file with only whitespace should return EMPTY_DOCUMENT error."""
        fp = tmp_path / "whitespace.txt"
        fp.write_text("   \n\n   \t  \n", encoding="utf-8")

        result = ingestor.ingest_file(fp, claim_id="CLM-WS")

        assert result.success is False
        assert result.error.error_code == "EMPTY_DOCUMENT"

    def test_empty_content_direct(self, ingestor):
        """Empty string passed directly should return EMPTY_DOCUMENT error."""
        result = ingestor.ingest_content(
            content="",
            filename="nothing.txt",
            claim_id="CLM-EMPTY-2"
        )

        assert result.success is False
        assert result.error.error_code == "EMPTY_DOCUMENT"


# ---------------------------------------------------------------------------
# 3. Unsupported File Types
# ---------------------------------------------------------------------------

class TestUnsupportedFileTypes:

    def test_unsupported_extension_docx(self, ingestor, tmp_path):
        """A .docx file should return UNSUPPORTED_FORMAT error."""
        fp = tmp_path / "document.docx"
        fp.write_text("fake docx content", encoding="utf-8")

        result = ingestor.ingest_file(fp, claim_id="CLM-DOCX")

        assert result.success is False
        assert result.error.error_code == "UNSUPPORTED_FORMAT"
        assert ".docx" in result.error.error_message

    def test_unsupported_extension_xlsx(self, ingestor, tmp_path):
        """A .xlsx file should return UNSUPPORTED_FORMAT error."""
        fp = tmp_path / "data.xlsx"
        fp.write_bytes(b"fake xlsx")

        result = ingestor.ingest_file(fp, claim_id="CLM-XLSX")

        assert result.success is False
        assert result.error.error_code == "UNSUPPORTED_FORMAT"

    def test_unsupported_via_content(self, ingestor):
        """Unsupported format via ingest_content should also fail gracefully."""
        result = ingestor.ingest_content(
            content="some content",
            filename="report.docx",
            claim_id="CLM-UNSUP",
        )

        assert result.success is False
        assert result.error.error_code == "UNSUPPORTED_FORMAT"


# ---------------------------------------------------------------------------
# 4. Malformed Input
# ---------------------------------------------------------------------------

class TestMalformedInput:

    def test_malformed_json(self, ingestor, tmp_path):
        """Invalid JSON should return MALFORMED_JSON error."""
        fp = tmp_path / "bad.json"
        fp.write_text("{broken json content 123", encoding="utf-8")

        result = ingestor.ingest_file(fp, claim_id="CLM-BADJSON")

        assert result.success is False
        assert result.error.error_code == "MALFORMED_JSON"

    def test_file_not_found(self, ingestor):
        """A non-existent file path should return FILE_NOT_FOUND error."""
        result = ingestor.ingest_file(
            Path("/nonexistent/path/file.txt"),
            claim_id="CLM-NOFILE"
        )

        assert result.success is False
        assert result.error.error_code == "FILE_NOT_FOUND"

    def test_directory_not_found(self, ingestor):
        """Ingesting from a non-existent directory should return DIR_NOT_FOUND."""
        results = ingestor.ingest_claim_directory(
            Path("/nonexistent/claim_dir"),
            claim_id="CLM-NODIR"
        )

        assert len(results) == 1
        assert results[0].success is False
        assert results[0].error.error_code == "DIR_NOT_FOUND"


# ---------------------------------------------------------------------------
# 5. Document Type Classification
# ---------------------------------------------------------------------------

class TestDocumentClassification:

    def test_classify_claim_form(self):
        text = "MOTOR INSURANCE CLAIM FORM\nClaim Reference: CLM-001\nPolicy Number: POL-123"
        assert DocumentTypeClassifier.classify(text) == DocumentCategory.CLAIM_FORM

    def test_classify_incident_description(self):
        text = "CUSTOMER INCIDENT STATEMENT\nPolicyholder: John Doe\nI was driving..."
        assert DocumentTypeClassifier.classify(text) == DocumentCategory.INCIDENT_DESCRIPTION

    def test_classify_repair_estimate(self):
        text = "GARAGE REPAIR ESTIMATE\nItemized parts: bumper, headlight\nLabor charges: Rs. 5000"
        assert DocumentTypeClassifier.classify(text) == DocumentCategory.REPAIR_ESTIMATE

    def test_classify_fir(self):
        text = "FIRST INFORMATION REPORT\nPolice Station: XYZ\nComplainant: John"
        assert DocumentTypeClassifier.classify(text) == DocumentCategory.FIR

    def test_classify_unknown(self):
        text = "Random content with no recognizable patterns whatsoever."
        assert DocumentTypeClassifier.classify(text) == DocumentCategory.UNKNOWN


# ---------------------------------------------------------------------------
# 6. Full Claim Directory Ingestion
# ---------------------------------------------------------------------------

class TestClaimDirectoryIngestion:

    def test_ingest_real_claim_001(self, ingestor):
        """Ingest all files from the actual claim_001 directory."""
        from backend.config import settings
        claim_dir = settings.CLAIMS_DIR / "claim_001"
        if not claim_dir.exists():
            pytest.skip("claim_001 directory not found")

        results = ingestor.ingest_claim_directory(claim_dir, claim_id="CLM-001")

        # Should have ingested at least the .txt and .json files
        successes = [r for r in results if r.success]
        assert len(successes) >= 2, f"Expected at least 2 successes, got {len(successes)}"

        # Every success should have sections
        for r in successes:
            assert len(r.evidence.sections) > 0

    def test_ingest_real_claim_003(self, ingestor):
        """Ingest claim_003 (the contradiction claim) and check extraction."""
        from backend.config import settings
        claim_dir = settings.CLAIMS_DIR / "claim_003"
        if not claim_dir.exists():
            pytest.skip("claim_003 directory not found")

        results = ingestor.ingest_claim_directory(claim_dir, claim_id="CLM-003")
        successes = [r for r in results if r.success]
        assert len(successes) >= 2


# ---------------------------------------------------------------------------
# 7. Evidence Serialization
# ---------------------------------------------------------------------------

class TestEvidenceSerialization:

    def test_to_dict_roundtrip(self, ingestor, sample_claim_form_txt, tmp_path):
        """DocumentEvidence.to_dict() should produce valid JSON-serializable output."""
        fp = tmp_path / "claim_form.txt"
        fp.write_text(sample_claim_form_txt, encoding="utf-8")

        result = ingestor.ingest_file(fp, claim_id="CLM-SERIAL")
        assert result.success is True

        d = result.evidence.to_dict()
        # Should be JSON serializable
        json_str = json.dumps(d)
        loaded = json.loads(json_str)
        assert loaded["claim_id"] == "CLM-SERIAL"
        assert isinstance(loaded["sections"], list)
        assert len(loaded["sections"]) > 0

    def test_ingestion_result_to_dict(self, ingestor, sample_claim_form_txt, tmp_path):
        """IngestionResult.to_dict() should be serializable for API responses."""
        fp = tmp_path / "claim_form.txt"
        fp.write_text(sample_claim_form_txt, encoding="utf-8")

        result = ingestor.ingest_file(fp, claim_id="CLM-RESULT")
        d = result.to_dict()
        json_str = json.dumps(d)
        loaded = json.loads(json_str)
        assert loaded["success"] is True
        assert "evidence" in loaded
