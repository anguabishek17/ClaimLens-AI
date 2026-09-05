"""
ClaimLens AI — Local Vector Retrieval Service (Phase 4)

Implements the full Gemini + Local Retrieval Pipeline:

    policy clauses + claim evidence
            ↓
       chunking
            ↓
    Gemini embeddings (gemini-embedding-001)
            ↓
     local vector index (NumPy)
            ↓
     semantic retrieval (cosine similarity)
            ↓
     top relevant evidence

Key features:
- Precomputed, persisted policy index — NOT re-embedded on every request.
- Separate claim-evidence index built per claim, also cached.
- Every result carries: source, text, similarity_score, document_id, clause_id.
- Graceful fallback to keyword matching when Gemini API is unavailable.

Constraints:
- NO external vector databases (no Pinecone, Weaviate, etc.)
- ONLY Gemini API for embeddings
- Lightweight NumPy cosine similarity
"""

import json
import hashlib
import logging
import time
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

import numpy as np

from backend.config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data Structures
# ---------------------------------------------------------------------------

class RetrievalResult:
    """Structured search result — every field required by hackathon spec."""

    __slots__ = ("source", "text", "similarity_score", "document_id", "clause_id")

    def __init__(
        self,
        source: str,
        text: str,
        similarity_score: float,
        document_id: str,
        clause_id: Optional[str] = None,
    ):
        self.source = source
        self.text = text
        self.similarity_score = round(similarity_score, 6)
        self.document_id = document_id
        self.clause_id = clause_id

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "text": self.text,
            "similarity_score": self.similarity_score,
            "document_id": self.document_id,
            "clause_id": self.clause_id,
        }


# ---------------------------------------------------------------------------
# Chunking Utilities
# ---------------------------------------------------------------------------

def chunk_text(text: str, max_tokens: int = 300, overlap: int = 50) -> List[str]:
    """
    Split text into overlapping word-level chunks suitable for embedding.
    Keeps chunks roughly ≤ max_tokens words with `overlap` words carried over.
    """
    if not text or not text.strip():
        return []
    words = text.split()
    if len(words) <= max_tokens:
        return [text.strip()]

    chunks: List[str] = []
    start = 0
    while start < len(words):
        end = min(start + max_tokens, len(words))
        chunk = " ".join(words[start:end])
        if chunk.strip():
            chunks.append(chunk.strip())
        start += max_tokens - overlap
    return chunks


def _content_hash(items: List[str]) -> str:
    """Deterministic hash of a list of strings (for cache-busting)."""
    hasher = hashlib.sha256()
    for item in items:
        hasher.update(item.encode("utf-8", errors="replace"))
    return hasher.hexdigest()[:16]


# ---------------------------------------------------------------------------
# Local Vector Index (NumPy-backed)
# ---------------------------------------------------------------------------

class LocalVectorIndex:
    """
    Minimal in-memory vector index backed by NumPy.
    Supports persistence to disk so embeddings are precomputed once.
    """

    def __init__(self):
        self.vectors: Optional[np.ndarray] = None       # (N, D)
        self.metadata: List[Dict[str, Any]] = []         # parallel list
        self._content_hash: str = ""

    @property
    def is_built(self) -> bool:
        return self.vectors is not None and len(self.metadata) > 0

    @property
    def size(self) -> int:
        return len(self.metadata)

    # ---- Build ----

    def build(
        self,
        vectors: List[List[float]],
        metadata: List[Dict[str, Any]],
        content_hash: str = "",
    ) -> None:
        if not vectors or not metadata:
            return
        self.vectors = np.array(vectors, dtype=np.float32)
        self.metadata = metadata
        self._content_hash = content_hash

    # ---- Search (cosine similarity) ----

    def search(self, query_vector: List[float], top_k: int = 5) -> List[Tuple[Dict[str, Any], float]]:
        """Return top_k (metadata, similarity_score) pairs."""
        if not self.is_built:
            return []

        q = np.array(query_vector, dtype=np.float32)
        q_norm = np.linalg.norm(q)
        if q_norm < 1e-9:
            return []

        norms = np.linalg.norm(self.vectors, axis=1)
        # Avoid divide-by-zero
        safe_norms = np.where(norms < 1e-9, 1.0, norms)
        similarities = np.dot(self.vectors, q) / (safe_norms * q_norm)

        top_k = min(top_k, len(similarities))
        top_indices = np.argsort(similarities)[::-1][:top_k]

        results: List[Tuple[Dict[str, Any], float]] = []
        for idx in top_indices:
            results.append((self.metadata[idx], float(similarities[idx])))
        return results

    # ---- Persistence ----

    def save(self, path: Path) -> None:
        """Persist index to disk (vectors + metadata)."""
        path.parent.mkdir(parents=True, exist_ok=True)
        np.save(str(path.with_suffix(".npy")), self.vectors)
        meta_path = path.with_suffix(".meta.json")
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(
                {"content_hash": self._content_hash, "metadata": self.metadata},
                f,
                indent=2,
                ensure_ascii=False,
            )

    def load(self, path: Path) -> bool:
        """Load a previously persisted index. Returns True on success."""
        npy_path = path.with_suffix(".npy")
        meta_path = path.with_suffix(".meta.json")
        if not npy_path.exists() or not meta_path.exists():
            return False
        try:
            self.vectors = np.load(str(npy_path)).astype(np.float32)
            with open(meta_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.metadata = data.get("metadata", [])
            self._content_hash = data.get("content_hash", "")
            return self.is_built
        except Exception as e:
            logger.warning(f"Failed to load index from {path}: {e}")
            return False

    def matches_hash(self, content_hash: str) -> bool:
        return self._content_hash == content_hash


# ---------------------------------------------------------------------------
# Main Retrieval Service
# ---------------------------------------------------------------------------

class RetrievalService:
    """
    Gemini + Local Retrieval Pipeline for ClaimLens AI.

    Provides:
      - embed_text(text)            → List[float]
      - build_policy_index()        → builds / loads precomputed policy index
      - search_policy(query, top_k) → List[RetrievalResult]
      - search_claim_evidence(evidence_texts, query, top_k) → List[RetrievalResult]

    Index lifecycle:
      - Policy index is built once at startup and cached to disk.
        Subsequent loads reuse the cache unless the source data changes.
      - Claim evidence index is built per-claim and kept in-memory.
    """

    INDEX_DIR_NAME = "vector_indices"

    def __init__(self, gemini_service: Optional[Any] = None):
        # Lazy import to avoid circular dependency
        if gemini_service is None:
            from backend.services.gemini_service import GeminiService
            gemini_service = GeminiService()
        self.gemini_service = gemini_service

        # Policy index (precomputed)
        self._policy_index = LocalVectorIndex()
        self._policy_clauses: List[Dict[str, Any]] = []

        # Claim evidence index (per-claim, in-memory)
        self._claim_index = LocalVectorIndex()
        self._claim_evidence_cache_key: str = ""

        # Index storage directory
        self._index_dir = settings.PROCESSED_DIR / self.INDEX_DIR_NAME
        self._index_dir.mkdir(parents=True, exist_ok=True)

        # Eagerly load policy data and try to reuse cached index
        self._load_and_build_policy_index()

    # ------------------------------------------------------------------
    # Public: embed_text
    # ------------------------------------------------------------------

    def embed_text(self, text: str) -> List[float]:
        """
        Generate a Gemini embedding for a single text string.
        Delegates to GeminiService.embed_text.
        """
        return self.gemini_service.embed_text(text)

    # ------------------------------------------------------------------
    # Public: build_policy_index
    # ------------------------------------------------------------------

    def build_policy_index(self, force: bool = False) -> Dict[str, Any]:
        """
        Build (or rebuild) the local vector index over policy clauses.
        Uses precomputed cache on disk to avoid redundant API calls.

        Returns a status dict with clause_count, index_size, cached flag.
        """
        clauses = self._load_policy_clauses()
        if not clauses:
            return {"status": "error", "message": "No policy clauses found.", "clause_count": 0}

        self._policy_clauses = clauses
        texts = self._clauses_to_texts(clauses)
        c_hash = _content_hash(texts)
        cache_path = self._index_dir / "policy_index"

        # Check disk cache
        if not force and self._policy_index.is_built and self._policy_index.matches_hash(c_hash):
            return {
                "status": "ok",
                "cached": True,
                "clause_count": len(clauses),
                "index_size": self._policy_index.size,
            }

        if not force and not self._policy_index.is_built:
            if self._policy_index.load(cache_path) and self._policy_index.matches_hash(c_hash):
                return {
                    "status": "ok",
                    "cached": True,
                    "clause_count": len(clauses),
                    "index_size": self._policy_index.size,
                }

        # Need fresh embeddings
        if not self.gemini_service.is_configured:
            return {
                "status": "degraded",
                "message": "Gemini API not configured. Keyword fallback active.",
                "clause_count": len(clauses),
                "index_size": 0,
            }

        logger.info(f"Building policy index for {len(texts)} chunks...")
        start = time.time()
        vectors = self.gemini_service.embed_batch(texts)
        elapsed = time.time() - start

        metadata = self._clauses_to_metadata(clauses, texts)
        self._policy_index.build(vectors, metadata, content_hash=c_hash)
        self._policy_index.save(cache_path)

        logger.info(f"Policy index built: {self._policy_index.size} vectors in {elapsed:.2f}s")
        return {
            "status": "ok",
            "cached": False,
            "clause_count": len(clauses),
            "index_size": self._policy_index.size,
            "embedding_time_s": round(elapsed, 2),
        }

    # ------------------------------------------------------------------
    # Public: search_policy
    # ------------------------------------------------------------------

    def search_policy(self, query: str, top_k: int = 5) -> List[RetrievalResult]:
        """
        Semantic search over policy clauses. Returns RetrievalResult list.
        Falls back to keyword matching if vector index is unavailable.
        """
        if not self._policy_clauses:
            self._policy_clauses = self._load_policy_clauses()
        if not self._policy_clauses:
            return []

        # Try vector search
        if self._policy_index.is_built and self.gemini_service.is_configured:
            try:
                q_vec = self.embed_text(query)
                raw_results = self._policy_index.search(q_vec, top_k=top_k)
                return [
                    RetrievalResult(
                        source=meta.get("source", "policy"),
                        text=meta.get("text", ""),
                        similarity_score=score,
                        document_id=meta.get("document_id", "policy.json"),
                        clause_id=meta.get("clause_id"),
                    )
                    for meta, score in raw_results
                ]
            except Exception as e:
                logger.warning(f"Vector search failed, falling back to keywords: {e}")

        # Keyword fallback
        return self._keyword_search_policy(query, top_k)

    # ------------------------------------------------------------------
    # Public: search_claim_evidence
    # ------------------------------------------------------------------

    def search_claim_evidence(
        self,
        evidence_texts: List[Dict[str, str]],
        query: str,
        top_k: int = 5,
    ) -> List[RetrievalResult]:
        """
        Build an ephemeral vector index over claim evidence documents and
        search for the most relevant chunks.

        evidence_texts: list of dicts with keys:
            - "text": the raw document text
            - "source": e.g. "claim_form", "repair_estimate"
            - "document_id": unique document identifier

        Returns RetrievalResult list.
        """
        if not evidence_texts:
            return []

        # Chunk all evidence
        all_chunks: List[str] = []
        all_meta: List[Dict[str, Any]] = []
        for doc in evidence_texts:
            raw_text = doc.get("text", "")
            source = doc.get("source", "unknown")
            doc_id = doc.get("document_id", "unknown")
            chunks = chunk_text(raw_text, max_tokens=200, overlap=30)
            for i, chunk in enumerate(chunks):
                all_chunks.append(chunk)
                all_meta.append({
                    "source": source,
                    "text": chunk,
                    "document_id": doc_id,
                    "clause_id": None,
                    "chunk_index": i,
                })

        if not all_chunks:
            return []

        cache_key = _content_hash(all_chunks)

        # Reuse if same evidence was already indexed
        if (
            self._claim_index.is_built
            and self._claim_evidence_cache_key == cache_key
        ):
            pass  # reuse existing index
        elif self.gemini_service.is_configured:
            vectors = self.gemini_service.embed_batch(all_chunks)
            self._claim_index.build(vectors, all_meta, content_hash=cache_key)
            self._claim_evidence_cache_key = cache_key
        else:
            # Keyword fallback for claim evidence
            return self._keyword_search_evidence(all_meta, query, top_k)

        # Vector search
        try:
            q_vec = self.embed_text(query)
            raw_results = self._claim_index.search(q_vec, top_k=top_k)
            return [
                RetrievalResult(
                    source=meta.get("source", "unknown"),
                    text=meta.get("text", ""),
                    similarity_score=score,
                    document_id=meta.get("document_id", "unknown"),
                    clause_id=meta.get("clause_id"),
                )
                for meta, score in raw_results
            ]
        except Exception as e:
            logger.warning(f"Claim evidence vector search failed: {e}")
            return self._keyword_search_evidence(all_meta, query, top_k)

    # ------------------------------------------------------------------
    # Legacy compatibility: search_relevant_clauses
    # ------------------------------------------------------------------

    def search_relevant_clauses(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """
        Backward-compatible wrapper used by ClaimAnalysisService.
        Returns raw clause dicts (not RetrievalResult).
        """
        results = self.search_policy(query, top_k=top_k)
        if results:
            # Map back to raw clause dicts for backward compatibility
            output = []
            for r in results:
                clause = self._find_clause_by_id(r.clause_id) if r.clause_id else None
                if clause:
                    output.append(clause)
                else:
                    # Construct a minimal clause dict from the result
                    output.append({
                        "clause_id": r.clause_id or "UNKNOWN",
                        "title": r.source,
                        "text": r.text,
                        "default_impact": "SUPPORTS",
                        "summary": r.text[:200],
                        "section": r.source,
                    })
            return output

        # Final fallback — return first top_k clauses
        if not self._policy_clauses:
            self._policy_clauses = self._load_policy_clauses()
        return self._policy_clauses[:top_k]

    # ------------------------------------------------------------------
    # Private: Policy clause loading
    # ------------------------------------------------------------------

    def _load_policy_clauses(self) -> List[Dict[str, Any]]:
        """Load policy clauses from JSON files in data/policy/."""
        policy_files = [
            settings.POLICY_DIR / "policy.json",
            settings.POLICY_DIR / "motor_policy_clauses.json",
        ]
        for pf in policy_files:
            if pf.exists():
                try:
                    with open(pf, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if isinstance(data, list) and data:
                        return data
                except Exception as e:
                    logger.warning(f"Failed to load {pf}: {e}")
        return []

    def _load_and_build_policy_index(self) -> None:
        """Called once at __init__ to eagerly prepare the policy index."""
        self._policy_clauses = self._load_policy_clauses()
        if not self._policy_clauses:
            return

        texts = self._clauses_to_texts(self._policy_clauses)
        c_hash = _content_hash(texts)
        cache_path = self._index_dir / "policy_index"

        # Try loading from disk first
        if self._policy_index.load(cache_path) and self._policy_index.matches_hash(c_hash):
            logger.info(f"Loaded cached policy index ({self._policy_index.size} vectors)")
            return

        # If Gemini is available, build now
        if self.gemini_service.is_configured:
            self.build_policy_index()
        else:
            logger.info("Gemini not configured — policy index will use keyword fallback.")

    # ------------------------------------------------------------------
    # Private: Conversion helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _clauses_to_texts(clauses: List[Dict[str, Any]]) -> List[str]:
        """Convert clause dicts to embeddable text strings (chunked)."""
        texts: List[str] = []
        for clause in clauses:
            parts = []
            if clause.get("title"):
                parts.append(clause["title"])
            if clause.get("text"):
                parts.append(clause["text"])
            if clause.get("conditions"):
                parts.append("Conditions: " + " | ".join(clause["conditions"]))
            if clause.get("summary"):
                parts.append(clause["summary"])
            full = ". ".join(parts)
            # Chunk if long
            chunks = chunk_text(full, max_tokens=250, overlap=40)
            texts.extend(chunks)
        return texts

    @staticmethod
    def _clauses_to_metadata(
        clauses: List[Dict[str, Any]],
        texts: List[str],
    ) -> List[Dict[str, Any]]:
        """Build metadata list parallel to the chunked texts."""
        metadata: List[Dict[str, Any]] = []
        text_idx = 0
        for clause in clauses:
            parts = []
            if clause.get("title"):
                parts.append(clause["title"])
            if clause.get("text"):
                parts.append(clause["text"])
            if clause.get("conditions"):
                parts.append("Conditions: " + " | ".join(clause["conditions"]))
            if clause.get("summary"):
                parts.append(clause["summary"])
            full = ". ".join(parts)
            chunks = chunk_text(full, max_tokens=250, overlap=40)
            for chunk in chunks:
                if text_idx < len(texts):
                    metadata.append({
                        "clause_id": clause.get("clause_id", "UNKNOWN"),
                        "source": clause.get("section", clause.get("category", "policy")),
                        "text": texts[text_idx],
                        "document_id": "policy.json",
                        "title": clause.get("title", ""),
                    })
                    text_idx += 1
        return metadata

    def _find_clause_by_id(self, clause_id: Optional[str]) -> Optional[Dict[str, Any]]:
        """Look up a raw clause dict by its clause_id."""
        if not clause_id:
            return None
        for clause in self._policy_clauses:
            if clause.get("clause_id") == clause_id:
                return clause
        return None

    # ------------------------------------------------------------------
    # Private: Keyword fallback searches
    # ------------------------------------------------------------------

    def _keyword_search_policy(self, query: str, top_k: int) -> List[RetrievalResult]:
        """Simple keyword overlap scoring when vector search is unavailable."""
        query_words = set(query.lower().split())
        scored: List[Tuple[float, Dict[str, Any]]] = []
        for clause in self._policy_clauses:
            text = (
                clause.get("title", "")
                + " " + clause.get("text", "")
                + " " + clause.get("summary", "")
            ).lower()
            score = sum(1 for w in query_words if w in text)
            if score > 0:
                scored.append((score, clause))
        scored.sort(key=lambda x: x[0], reverse=True)
        max_score = scored[0][0] if scored else 1.0

        results: List[RetrievalResult] = []
        for score, clause in scored[:top_k]:
            results.append(RetrievalResult(
                source=clause.get("section", clause.get("category", "policy")),
                text=clause.get("text", ""),
                similarity_score=score / max_score if max_score else 0.0,
                document_id="policy.json",
                clause_id=clause.get("clause_id"),
            ))
        return results

    @staticmethod
    def _keyword_search_evidence(
        meta_list: List[Dict[str, Any]],
        query: str,
        top_k: int,
    ) -> List[RetrievalResult]:
        """Keyword overlap search over evidence chunks."""
        query_words = set(query.lower().split())
        scored: List[Tuple[float, Dict[str, Any]]] = []
        for meta in meta_list:
            text = meta.get("text", "").lower()
            score = sum(1 for w in query_words if w in text)
            scored.append((score, meta))
        scored.sort(key=lambda x: x[0], reverse=True)
        max_score = scored[0][0] if scored else 1.0

        results: List[RetrievalResult] = []
        for score, meta in scored[:top_k]:
            results.append(RetrievalResult(
                source=meta.get("source", "unknown"),
                text=meta.get("text", ""),
                similarity_score=score / max_score if max_score else 0.0,
                document_id=meta.get("document_id", "unknown"),
                clause_id=meta.get("clause_id"),
            ))
        return results
