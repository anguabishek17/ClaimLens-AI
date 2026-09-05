"""
ClaimLens AI - Document Ingestion & Evidence Extraction Service
Phase 3: Accepts PDF, TXT, JSON, Markdown documents, extracts text,
identifies document type, creates evidence chunks with full provenance.

Pipeline position:
  documents → extraction → chunking → retrieval → relevant evidence → Gemini
"""

import json
import re
import uuid
import hashlib
from pathlib import Path
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass, field, asdict
from enum import Enum


# ---------------------------------------------------------------------------
# Enums & Data Classes
# ---------------------------------------------------------------------------

class SupportedFormat(str, Enum):
    PDF = "pdf"
    TXT = "txt"
    JSON = "json"
    MARKDOWN = "md"


class DocumentCategory(str, Enum):
    CLAIM_FORM = "claim_form"
    INCIDENT_DESCRIPTION = "incident_description"
    REPAIR_ESTIMATE = "repair_estimate"
    FIR = "fir"
    POLICY = "policy"
    UNKNOWN = "unknown"


@dataclass
class EvidenceSection:
    """A single chunk of evidence extracted from a document."""
    section_id: str
    page: Optional[int]
    text: str
    source_reference: str


@dataclass
class DocumentEvidence:
    """Normalized internal representation of an ingested document."""
    document_id: str
    document_type: str
    claim_id: str
    original_filename: str
    file_format: str
    sections: List[EvidenceSection] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class IngestionError:
    """Structured error returned when a document cannot be processed."""
    document_id: str
    filename: str
    error_code: str
    error_message: str
    recoverable: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class IngestionResult:
    """Wrapper holding either evidence or an error."""
    success: bool
    evidence: Optional[DocumentEvidence] = None
    error: Optional[IngestionError] = None

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {"success": self.success}
        if self.evidence:
            d["evidence"] = self.evidence.to_dict()
        if self.error:
            d["error"] = self.error.to_dict()
        return d


# ---------------------------------------------------------------------------
# Text Extractors (per format)
# ---------------------------------------------------------------------------

class TextExtractor:
    """Strategy-based text extraction from different file formats."""

    @staticmethod
    def extract_txt(content: Union[str, bytes], **_kwargs: Any) -> List[EvidenceSection]:
        """Extract text from plaintext content."""
        if isinstance(content, bytes):
            content = content.decode("utf-8", errors="replace")
        if not content.strip():
            return []

        sections: List[EvidenceSection] = []
        paragraphs = re.split(r"\n{2,}", content.strip())
        for idx, para in enumerate(paragraphs, start=1):
            cleaned = para.strip()
            if cleaned:
                sections.append(EvidenceSection(
                    section_id=f"SEC-{idx:03d}",
                    page=None,
                    text=cleaned,
                    source_reference=f"Text Section {idx}"
                ))
        return sections

    @staticmethod
    def extract_json(content: Union[str, bytes], **_kwargs: Any) -> List[EvidenceSection]:
        """Extract text from JSON documents by recursively flattening values."""
        if isinstance(content, bytes):
            content = content.decode("utf-8", errors="replace")
        if not content.strip():
            return []

        data = json.loads(content)
        flat_parts = TextExtractor._flatten_json(data)
        sections: List[EvidenceSection] = []
        for idx, (key, value) in enumerate(flat_parts, start=1):
            sections.append(EvidenceSection(
                section_id=f"SEC-{idx:03d}",
                page=None,
                text=f"{key}: {value}",
                source_reference=f"JSON field '{key}'"
            ))
        return sections

    @staticmethod
    def _flatten_json(data: Any, prefix: str = "") -> List[tuple]:
        """Recursively flatten a JSON object into (key, value) pairs."""
        parts: List[tuple] = []
        if isinstance(data, dict):
            for k, v in data.items():
                full_key = f"{prefix}.{k}" if prefix else k
                if isinstance(v, (dict, list)):
                    parts.extend(TextExtractor._flatten_json(v, full_key))
                else:
                    parts.append((full_key, str(v)))
        elif isinstance(data, list):
            for i, item in enumerate(data):
                full_key = f"{prefix}[{i}]"
                if isinstance(item, (dict, list)):
                    parts.extend(TextExtractor._flatten_json(item, full_key))
                else:
                    parts.append((full_key, str(item)))
        else:
            parts.append((prefix or "value", str(data)))
        return parts

    @staticmethod
    def extract_markdown(content: Union[str, bytes], **_kwargs: Any) -> List[EvidenceSection]:
        """Extract text from Markdown by splitting on heading boundaries."""
        if isinstance(content, bytes):
            content = content.decode("utf-8", errors="replace")
        if not content.strip():
            return []

        sections: List[EvidenceSection] = []
        # Split on markdown headings
        parts = re.split(r"^(#{1,6}\s+.+)$", content.strip(), flags=re.MULTILINE)

        current_heading = "Document Header"
        buffer = []
        idx = 0

        for part in parts:
            part_stripped = part.strip()
            if re.match(r"^#{1,6}\s+", part_stripped):
                # Flush buffer for previous section
                if buffer:
                    idx += 1
                    sections.append(EvidenceSection(
                        section_id=f"SEC-{idx:03d}",
                        page=None,
                        text="\n".join(buffer).strip(),
                        source_reference=f"Markdown: {current_heading}"
                    ))
                    buffer = []
                current_heading = re.sub(r"^#+\s*", "", part_stripped)
            else:
                if part_stripped:
                    buffer.append(part_stripped)

        # Flush remaining
        if buffer:
            idx += 1
            sections.append(EvidenceSection(
                section_id=f"SEC-{idx:03d}",
                page=None,
                text="\n".join(buffer).strip(),
                source_reference=f"Markdown: {current_heading}"
            ))
        return sections

    @staticmethod
    def extract_pdf(content: bytes, **_kwargs: Any) -> List[EvidenceSection]:
        """
        Extract text from PDF using PyPDF2/pypdf if available.
        Falls back to a structured error if the library is missing.
        """
        try:
            import pypdf
        except ImportError:
            try:
                import PyPDF2 as pypdf  # type: ignore
            except ImportError:
                # Return a single section with an explanatory note
                return [EvidenceSection(
                    section_id="SEC-001",
                    page=None,
                    text="[PDF extraction unavailable — pypdf/PyPDF2 not installed]",
                    source_reference="PDF extraction error"
                )]

        import io
        reader = pypdf.PdfReader(io.BytesIO(content))
        sections: List[EvidenceSection] = []
        for page_num, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            text = text.strip()
            if text:
                sections.append(EvidenceSection(
                    section_id=f"SEC-{page_num:03d}",
                    page=page_num,
                    text=text,
                    source_reference=f"PDF Page {page_num}"
                ))
        return sections


# ---------------------------------------------------------------------------
# Document Type Classifier
# ---------------------------------------------------------------------------

class DocumentTypeClassifier:
    """Heuristic classifier that identifies what kind of claim document this is."""

    # Keyword patterns per category (case-insensitive)
    _PATTERNS: Dict[DocumentCategory, List[str]] = {
        DocumentCategory.CLAIM_FORM: [
            r"claim\s*form", r"claim\s*reference", r"policy\s*number",
            r"insured\s*declared\s*value", r"date\s*of\s*claim",
        ],
        DocumentCategory.INCIDENT_DESCRIPTION: [
            r"incident\s*statement", r"incident\s*description",
            r"customer\s*statement", r"policyholder",
        ],
        DocumentCategory.REPAIR_ESTIMATE: [
            r"repair\s*estimate", r"repair\s*bill", r"garage",
            r"itemized", r"labor\s*charges", r"service\s*center",
        ],
        DocumentCategory.FIR: [
            r"first\s*information\s*report", r"\bfir\b", r"police\s*station",
            r"complainant", r"offence",
        ],
        DocumentCategory.POLICY: [
            r"policy\s*document", r"clause", r"insurer\s*shall",
            r"deductible", r"insured\s*declared\s*value.*maximum",
        ],
    }

    @classmethod
    def classify(cls, text: str, filename: str = "") -> DocumentCategory:
        """Classify document category from its text content and filename hints."""
        combined = (text + " " + filename).lower()

        scores: Dict[DocumentCategory, int] = {}
        for category, patterns in cls._PATTERNS.items():
            score = sum(1 for p in patterns if re.search(p, combined, re.IGNORECASE))
            if score > 0:
                scores[category] = score

        if not scores:
            return DocumentCategory.UNKNOWN
        return max(scores, key=scores.get)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Main Document Ingestor Service
# ---------------------------------------------------------------------------

class DocumentIngestor:
    """
    Accepts a document (file path, raw content, or uploaded bytes),
    extracts text, identifies type, stores extracted text, and creates
    evidence chunks with full provenance.

    Usage:
        ingestor = DocumentIngestor()
        result = ingestor.ingest_file(path, claim_id="CLM-001")
        result = ingestor.ingest_content(text, filename="claim_form.txt", claim_id="CLM-001")
    """

    SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".json", ".md", ".markdown"}

    def __init__(self, processed_dir: Optional[Path] = None):
        from backend.config import settings
        self.processed_dir = processed_dir or settings.PROCESSED_DIR
        self.processed_dir.mkdir(parents=True, exist_ok=True)

    # ---- Public API ----

    def ingest_file(self, file_path: Union[str, Path], claim_id: str) -> IngestionResult:
        """Ingest a document from the filesystem."""
        file_path = Path(file_path)
        doc_id = self._generate_doc_id(file_path.name)

        # Validate existence
        if not file_path.exists():
            return IngestionResult(
                success=False,
                error=IngestionError(
                    document_id=doc_id,
                    filename=file_path.name,
                    error_code="FILE_NOT_FOUND",
                    error_message=f"File does not exist: {file_path}",
                    recoverable=False
                )
            )

        # Validate extension
        ext = file_path.suffix.lower()
        if ext not in self.SUPPORTED_EXTENSIONS:
            return IngestionResult(
                success=False,
                error=IngestionError(
                    document_id=doc_id,
                    filename=file_path.name,
                    error_code="UNSUPPORTED_FORMAT",
                    error_message=f"Unsupported file extension '{ext}'. Supported: {', '.join(sorted(self.SUPPORTED_EXTENSIONS))}",
                    recoverable=False
                )
            )

        # Read file
        try:
            if ext == ".pdf":
                raw = file_path.read_bytes()
            else:
                raw = file_path.read_text(encoding="utf-8")
        except Exception as e:
            return IngestionResult(
                success=False,
                error=IngestionError(
                    document_id=doc_id,
                    filename=file_path.name,
                    error_code="READ_ERROR",
                    error_message=f"Cannot read file: {e}",
                    recoverable=False
                )
            )

        return self._process(raw, file_path.name, ext, claim_id, doc_id)

    def ingest_content(
        self,
        content: Union[str, bytes],
        filename: str,
        claim_id: str,
        file_format: Optional[str] = None,
    ) -> IngestionResult:
        """Ingest raw content (e.g. from upload or in-memory)."""
        doc_id = self._generate_doc_id(filename)

        ext = file_format or Path(filename).suffix.lower()
        if not ext.startswith("."):
            ext = f".{ext}"

        if ext not in self.SUPPORTED_EXTENSIONS:
            return IngestionResult(
                success=False,
                error=IngestionError(
                    document_id=doc_id,
                    filename=filename,
                    error_code="UNSUPPORTED_FORMAT",
                    error_message=f"Unsupported format '{ext}'. Supported: {', '.join(sorted(self.SUPPORTED_EXTENSIONS))}",
                    recoverable=False
                )
            )

        if not content:
            return IngestionResult(
                success=False,
                error=IngestionError(
                    document_id=doc_id,
                    filename=filename,
                    error_code="EMPTY_DOCUMENT",
                    error_message="Document content is empty.",
                    recoverable=True
                )
            )

        return self._process(content, filename, ext, claim_id, doc_id)

    def ingest_claim_directory(self, claim_dir: Union[str, Path], claim_id: str) -> List[IngestionResult]:
        """Ingest all supported files in a claim directory."""
        claim_dir = Path(claim_dir)
        results: List[IngestionResult] = []
        if not claim_dir.is_dir():
            results.append(IngestionResult(
                success=False,
                error=IngestionError(
                    document_id="N/A",
                    filename=str(claim_dir),
                    error_code="DIR_NOT_FOUND",
                    error_message=f"Claim directory does not exist: {claim_dir}",
                    recoverable=False
                )
            ))
            return results

        for fp in sorted(claim_dir.iterdir()):
            if fp.is_file() and fp.suffix.lower() in self.SUPPORTED_EXTENSIONS:
                results.append(self.ingest_file(fp, claim_id))
        return results

    # ---- Internal Processing ----

    def _process(
        self,
        content: Union[str, bytes],
        filename: str,
        ext: str,
        claim_id: str,
        doc_id: str,
    ) -> IngestionResult:
        """Core processing: extract → classify → chunk → store."""

        # 1. Extract text sections
        try:
            sections = self._extract(content, ext)
        except json.JSONDecodeError as e:
            return IngestionResult(
                success=False,
                error=IngestionError(
                    document_id=doc_id,
                    filename=filename,
                    error_code="MALFORMED_JSON",
                    error_message=f"Invalid JSON: {e}",
                    recoverable=False
                )
            )
        except Exception as e:
            return IngestionResult(
                success=False,
                error=IngestionError(
                    document_id=doc_id,
                    filename=filename,
                    error_code="EXTRACTION_ERROR",
                    error_message=f"Text extraction failed: {e}",
                    recoverable=False
                )
            )

        if not sections:
            return IngestionResult(
                success=False,
                error=IngestionError(
                    document_id=doc_id,
                    filename=filename,
                    error_code="EMPTY_DOCUMENT",
                    error_message="No extractable text found in document.",
                    recoverable=True
                )
            )

        # 2. Classify document type from extracted text
        full_text = "\n".join(s.text for s in sections)
        doc_category = DocumentTypeClassifier.classify(full_text, filename)

        # 3. Build DocumentEvidence
        evidence = DocumentEvidence(
            document_id=doc_id,
            document_type=doc_category.value,
            claim_id=claim_id,
            original_filename=filename,
            file_format=ext.lstrip("."),
            sections=sections,
        )

        # 4. Persist to processed directory
        self._store(evidence)

        return IngestionResult(success=True, evidence=evidence)

    def _extract(self, content: Union[str, bytes], ext: str) -> List[EvidenceSection]:
        """Dispatch to the correct extractor based on file extension."""
        extractors = {
            ".txt": TextExtractor.extract_txt,
            ".json": TextExtractor.extract_json,
            ".md": TextExtractor.extract_markdown,
            ".markdown": TextExtractor.extract_markdown,
            ".pdf": TextExtractor.extract_pdf,
        }
        extractor = extractors.get(ext)
        if not extractor:
            raise ValueError(f"No extractor for extension '{ext}'")
        return extractor(content)

    def _store(self, evidence: DocumentEvidence) -> Path:
        """Persist extracted evidence to the processed directory as JSON."""
        claim_dir = self.processed_dir / evidence.claim_id
        claim_dir.mkdir(parents=True, exist_ok=True)
        out_path = claim_dir / f"{evidence.document_id}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(evidence.to_dict(), f, indent=2, ensure_ascii=False)
        return out_path

    @staticmethod
    def _generate_doc_id(filename: str) -> str:
        """Generate a deterministic but unique document ID."""
        hash_part = hashlib.md5(f"{filename}-{uuid.uuid4().hex[:8]}".encode()).hexdigest()[:10]
        return f"DOC-{hash_part.upper()}"
