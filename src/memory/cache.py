import json
from datetime import datetime, timezone
from pymongo.operations import SearchIndexModel
from pymongo.errors import OperationFailure

from src.memory.mongo import get_db
from src.kb.retriever import embed_texts
from src.config import EMBEDDING_DIMS

CACHE_COL = "semantic_cache"
CACHE_INDEX = "cache_vector_idx"

def setup_cache_index() -> None:
    """Creates the Vector Search index for the cache collection."""
    db = get_db()
    col = db[CACHE_COL]
    
    # 1. Create Vector Search Index
    try:
        existing = list(col.list_search_indexes())
        if not any(idx.get("name") == CACHE_INDEX for idx in existing):
            model = SearchIndexModel(
                definition={
                    "fields": [
                        {"type": "vector", "path": "embedding", "numDimensions": EMBEDDING_DIMS, "similarity": "cosine"},
                        {"type": "filter", "path": "tool_name"}
                    ]
                },
                name=CACHE_INDEX,
                type="vectorSearch",
            )
            col.create_search_index(model=model)
    except OperationFailure:
        pass 

def get_cached_tool_result(tool_name: str, query: str, threshold: float = 0.92) -> list | dict | None:
    db = get_db()
    try:
        query_emb = embed_texts([query])[0]
    except Exception:
        return None

    pipeline = [
        {
            "$vectorSearch": {
                "index": CACHE_INDEX,
                "path": "embedding",
                "queryVector": query_emb,
                "numCandidates": 10,
                "limit": 1
            }
        },
        {"$match": {"tool_name": tool_name}},
        {"$project": {"_id": 0, "result": 1, "score": {"$meta": "vectorSearchScore"}}}
    ]
    
    results = list(db[CACHE_COL].aggregate(pipeline))
    
    if results and results[0].get("score", 0) >= threshold:
        return json.loads(results[0]["result"])
    return None

def set_cached_tool_result(tool_name: str, query: str, result: list | dict) -> None:
    db = get_db()
    query_emb = embed_texts([query])[0]
    
    db[CACHE_COL].insert_one({
        "tool_name": tool_name,
        "query": query,
        "embedding": query_emb,
        "result": json.dumps(result, ensure_ascii=False),
        "timestamp": datetime.now(timezone.utc) # الحقل الضروري للـ TTL
    })