"""Hybrid retrieval: Structure-Aware Markdown split + Atlas Vector Search, fused via RRF.

Build-once:  build_and_persist_chunks() — Structural chunking, embeds, stores in Mongo.
Per query:   HybridRetriever(...).search(query) — fused top-K optimized for precision.
"""
from __future__ import annotations
import re
import logging
import numpy as np
from dataclasses import dataclass
from functools import cache
from typing import Iterable
from openai import OpenAI
from rank_bm25 import BM25Okapi

from src.config import (
    OPENAI_API_KEY, EMBEDDING_MODEL, EMBEDDING_DIMS,
    COL_KB_CHUNKS, VECTOR_INDEX_NAME, RETRIEVER_TOP_K, RETRIEVER_RRF_K,
)
from src.memory.mongo import get_db
from src.kb.loader import KnowledgeBase, MdDoc

# ─────────────────────────────────────────────────────────────────────
# Logging Setup
# ─────────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("KayfaChat.Retriever")

@cache
def _openai() -> OpenAI:
    return OpenAI(api_key=OPENAI_API_KEY)


# ─────────────────────────────────────────────────────────────────────
# 🧠 Structure-Aware Chunking
# ─────────────────────────────────────────────────────────────────────

@dataclass
class Chunk:
    source: str       # md doc name
    chunk_index: int
    text: str
    topic: str
    language: str


def chunk_docs(kb: KnowledgeBase) -> list[Chunk]:
    chunks: list[Chunk] = []
    for d in kb.docs:
        # ATOMIC CHUNK: If file is manageable, don't split it.
        if len(d.text) < 8000:
            chunks.append(Chunk(source=d.name, chunk_index=0, text=d.text.strip(), topic=d.topic, language=d.language))
        else:
            # Only split massive files by header
            sections = d.text.split("\n## ")
            for i, sec in enumerate(sections):
                text = sec if i == 0 else "## " + sec
                chunks.append(Chunk(source=d.name, chunk_index=i, text=text.strip(), topic=d.topic, language=d.language))
    return chunks

# ─────────────────────────────────────────────────────────────────────
# Embeddings
# ─────────────────────────────────────────────────────────────────────

def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    resp = _openai().embeddings.create(
        model=EMBEDDING_MODEL,
        input=texts,
        dimensions=EMBEDDING_DIMS,
    )
    return [d.embedding for d in resp.data]


# ─────────────────────────────────────────────────────────────────────
# Build & Persist
# ─────────────────────────────────────────────────────────────────────

def build_and_persist_chunks(kb: KnowledgeBase, force: bool = False) -> dict:
    col = get_db()[COL_KB_CHUNKS]
    existing = col.count_documents({})
    if existing and not force:
        return {"status": "skipped", "existing_chunks": existing}

    if force:
        col.delete_many({})

    chunks = chunk_docs(kb)
    texts = [c.text for c in chunks]

    embeddings: list[list[float]] = []
    batch = 64
    for i in range(0, len(texts), batch):
        embeddings.extend(embed_texts(texts[i:i + batch]))

    docs = [{
        "source": c.source,
        "chunk_index": c.chunk_index,
        "text": c.text,
        "topic": c.topic,
        "language": c.language,
        "embedding": emb,
    } for c, emb in zip(chunks, embeddings)]

    if docs:
        col.insert_many(docs)
    return {"status": "built", "chunks": len(docs)}


# ─────────────────────────────────────────────────────────────────────
# Tokenizer & Hybrid Retriever
# ─────────────────────────────────────────────────────────────────────

def _tokenize(text: str) -> list[str]:
    text = text.lower()
    text = re.sub(r'[^\w\s]', '', text, flags=re.UNICODE)
    tokens = text.split()
    
    conversational_stop_words = {
        "وش", "لي", "يا", "طويل", "العمر", "الأنسب", "كام", "بكام", 
        "عايز", "أنا", "بقولك", "إيه", "أبغى", "عندكم", "تفاصيله"
    }
    
    out: list[str] = []
    for t in tokens:
        if t in conversational_stop_words:
            continue
        if len(t) > 3 and any("\u0600" <= ch <= "\u06ff" for ch in t):
            if t.startswith("ال"):
                t = t[2:]
            elif t and t[0] in "وفبكل":
                t = t[1:]
        if t:
            out.append(t)
    return out


def _rrf_fuse(rankings: list[list[str]], k: int = RETRIEVER_RRF_K) -> dict[str, float]:
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, doc_id in enumerate(ranking):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank + 1)
    return scores


class HybridRetriever:
    def __init__(self) -> None:
        col = get_db()[COL_KB_CHUNKS]
        all_data = list(col.find({}, {"text": 1, "topic": 1, "source": 1}))
        self.chunk_map = {str(c["_id"]): c for c in all_data}
        
        corpus_tokens = [_tokenize(c["text"]) for c in all_data]
        self.bm25 = BM25Okapi(corpus_tokens)
        self.ids = [str(c["_id"]) for c in all_data]
        logger.info(f"Retriever initialized with {len(all_data)} chunks.")

    def _bm25_top(self, query: str, top: int = 25) -> list[str]:
        scores = self.bm25.get_scores(_tokenize(query))
        ranked = sorted(zip(self.ids, scores), key=lambda x: x[1], reverse=True)
        return [doc_id for doc_id, score in ranked if score > 0][:top]

    def _vector_top(self, query_emb: list[float], top: int = 25, topic_filter: str | None = None) -> list[str]:
        pipeline = [{
            "$vectorSearch": {
                "index": VECTOR_INDEX_NAME,
                "path": "embedding",
                "queryVector": query_emb,
                "numCandidates": max(top * 10, 50),
                "limit": top,
            }
        }]
        if topic_filter:
            pipeline[0]["$vectorSearch"]["filter"] = {"topic": topic_filter}
        
        pipeline.append({"$project": {"_id": 1}})
        col = get_db()[COL_KB_CHUNKS]
        results = list(col.aggregate(pipeline))
        return [str(r["_id"]) for r in results]

    # ─────────────────────────────────────────────────────────────────
    # 💎 Semantic Cache Logic
    # ─────────────────────────────────────────────────────────────────
    def _check_cache(self, query: str) -> list[dict] | None:
        col = get_db()["semantic_cache"]
        emb = embed_texts([query])[0]
        pipeline = [{"$vectorSearch": {"index": "semantic_cache_index", "path": "embedding", "queryVector": emb, "numCandidates": 5, "limit": 1}}]
        res = list(col.aggregate(pipeline))
        # Threshold: 0.95
        if res and res[0].get("score", 0) > 0.95:
            return [{**item, "is_cache_hit": True} for item in res[0].get("results", [])]
        return None

    def _save_cache(self, query: str, results: list[dict]):
        col = get_db()["semantic_cache"]
        col.insert_one({"query": query, "embedding": embed_texts([query])[0], "results": results, "created_at": "$$NOW"})

    # ─────────────────────────────────────────────────────────────────
    # Main Search
    # ─────────────────────────────────────────────────────────────────
    def search(self, query: str, top_k: int = RETRIEVER_TOP_K, topic_filter: str | None = None, dedup_by_source: bool = True) -> list[dict]:
        # 1. Try Cache
        cached = self._check_cache(query)
        if cached: return cached

        # 2. Hybrid Search
        n_query = query.replace("فول ستاك", "Fullstack")
        logger.info(f"DEBUG: Search Query: '{query}' | Normalized: '{n_query}'")

        try:
            query_emb = embed_texts([n_query])[0]
        except Exception as e:
            logger.error(f"Embedding failed: {e}")
            return []

        bm25_ids = self._bm25_top(n_query)
        vec_ids = self._vector_top(query_emb, topic_filter=topic_filter)
        
        fused = _rrf_fuse([bm25_ids, vec_ids])
        ranked = sorted(fused.items(), key=lambda x: x[1], reverse=True)
        
        seen_sources: set[str] = set()
        out: list[dict] = []
        
        for doc_id, score in ranked:
            c = self.chunk_map.get(doc_id)
            if not c or score < 0.01: continue
            if dedup_by_source and c.get("source") in seen_sources: continue
            
            if c.get("source"): seen_sources.add(c["source"])
            out.append({
                "source": c.get("source", "unknown"),
                "topic": c.get("topic", "general"),
                "text": c.get("text", ""),
                "score": round(score, 5),
            })
            if len(out) >= top_k: break
        
        # 3. Save to Cache
        self._save_cache(query, out)
        
        # 4. Return results with defensive check (is_cache_hit must exist)
        return [{**item, "is_cache_hit": False} for item in out]