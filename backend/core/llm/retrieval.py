"""Lightweight text chunking and vector retrieval abstraction for NOVA Code Lab.

Prepares the embedding and retrieval pipeline:
Project files -> Chunking -> Embeddings -> Retrieval -> Relevant Context -> Coder / Debugger / Planner.
"""

from dataclasses import dataclass
import math
from typing import Dict, List, Optional, Tuple

from backend.core.llm.model_router import get_model_router


@dataclass
class CodeChunk:
    file_path: str
    chunk_index: int
    content: str
    embedding: Optional[List[float]] = None


def chunk_text(text: str, file_path: str = "", chunk_size: int = 600, overlap: int = 80) -> List[CodeChunk]:
    """Split file text into overlapping chunks for semantic embedding."""
    if not text or not text.strip():
        return []

    lines = text.splitlines()
    chunks: List[CodeChunk] = []
    curr_lines: List[str] = []
    curr_chars = 0
    idx = 0

    for line in lines:
        curr_lines.append(line)
        curr_chars += len(line) + 1
        if curr_chars >= chunk_size:
            chunk_content = "\n".join(curr_lines)
            chunks.append(CodeChunk(file_path=file_path, chunk_index=idx, content=chunk_content))
            idx += 1
            # Keep overlap lines
            overlap_lines = curr_lines[-max(1, int(len(curr_lines) * 0.2)):]
            curr_lines = list(overlap_lines)
            curr_chars = sum(len(l) + 1 for l in curr_lines)

    if curr_lines:
        chunk_content = "\n".join(curr_lines)
        chunks.append(CodeChunk(file_path=file_path, chunk_index=idx, content=chunk_content))

    return chunks


def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    """Compute cosine similarity between two float vectors."""
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    dot = sum(a * b for a, b in zip(v1, v2))
    norm1 = math.sqrt(sum(a * a for a in v1))
    norm2 = math.sqrt(sum(b * b for b in v2))
    if norm1 == 0.0 or norm2 == 0.0:
        return 0.0
    return dot / (norm1 * norm2)


class WorkspaceRetriever:
    """Retrieves relevant code chunks for agents using vector embeddings."""

    def __init__(self):
        self.router = get_model_router()
        self.chunks: List[CodeChunk] = []

    def index_files(self, files: Dict[str, str]) -> int:
        """Chunk and embed workspace files."""
        self.chunks = []
        texts_to_embed = []
        chunk_ptrs = []

        for path, content in files.items():
            file_chunks = chunk_text(content, file_path=path)
            for c in file_chunks:
                self.chunks.append(c)
                texts_to_embed.append(f"File: {c.file_path}\n{c.content}")
                chunk_ptrs.append(c)

        if texts_to_embed:
            try:
                embeddings = self.router.embed(texts=texts_to_embed)
                for ptr, emb in zip(chunk_ptrs, embeddings):
                    ptr.embedding = emb
            except Exception:
                pass

        return len(self.chunks)

    def retrieve(self, query: str, top_k: int = 3) -> List[CodeChunk]:
        """Find most semantically relevant code chunks for a given prompt/error query."""
        if not self.chunks or not query.strip():
            return []

        try:
            q_emb = self.router.embed(texts=[query])[0]
            scored = []
            for c in self.chunks:
                if c.embedding:
                    score = cosine_similarity(q_emb, c.embedding)
                    scored.append((score, c))
            scored.sort(key=lambda x: x[0], reverse=True)
            return [item[1] for item in scored[:top_k]]
        except Exception:
            # Fallback: simple text keyword matching
            q_lower = query.lower()
            matched = [c for c in self.chunks if any(w in c.content.lower() for w in q_lower.split()[:4])]
            return matched[:top_k]
