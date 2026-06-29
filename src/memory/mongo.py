"""MongoDB connection + one-time collection / index provisioning."""
from functools import cache
from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.operations import SearchIndexModel
from pymongo.errors import OperationFailure
from src.config import (
    MONGODB_URI, DB_NAME, EMBEDDING_DIMS, VECTOR_INDEX_NAME,
    COL_SESSIONS, COL_MESSAGES, COL_PROFILES, COL_SUMMARIES,
    COL_KB_CHUNKS, COL_TICKETS, COL_EVENTS,
)

@cache
def get_client() -> MongoClient:
    return MongoClient(MONGODB_URI)

@cache
def get_db():
    """Returns the main application database."""
    return get_client()[DB_NAME]

def get_analytics_collection():
    """Returns the analytics collection for monitoring."""
    # نستخدم get_db() لضمان الاتصال بنفس قاعدة البيانات
    return get_db()["analytics_logs"]

def setup_collections() -> dict[str, int]:
    """Ensure collections + standard indexes exist. Idempotent. Returns counts."""
    db = get_db()

    # Standard Indexes
    db[COL_SESSIONS].create_index([("session_id", ASCENDING)], unique=True)
    db[COL_SESSIONS].create_index([("last_active_at", DESCENDING)])
    db[COL_MESSAGES].create_index([("session_id", ASCENDING), ("timestamp", ASCENDING)])
    db[COL_PROFILES].create_index([("session_id", ASCENDING)], unique=True)
    db[COL_SUMMARIES].create_index([("session_id", ASCENDING), ("created_at", DESCENDING)])
    db[COL_TICKETS].create_index([("ticket_id", ASCENDING)], unique=True)
    db[COL_TICKETS].create_index([("type", ASCENDING), ("created_at", DESCENDING)])
    db[COL_TICKETS].create_index([("session_id", ASCENDING)])
    db[COL_EVENTS].create_index([("session_id", ASCENDING), ("timestamp", DESCENDING)])
    db[COL_EVENTS].create_index([("type", ASCENDING)])
    db[COL_KB_CHUNKS].create_index([("source", ASCENDING)])
    # ADD after: db[COL_EVENTS].create_index([("type", ASCENDING)])
    db["usage_logs"].create_index([("user_id", ASCENDING), ("timestamp", DESCENDING)])
    db["usage_logs"].create_index([("conversation_id", ASCENDING)])
    db["usage_logs"].create_index([("session_id", ASCENDING)])

    return {c: db[c].count_documents({}) for c in [
        COL_SESSIONS, COL_MESSAGES, COL_PROFILES, COL_SUMMARIES,
        COL_KB_CHUNKS, COL_TICKETS, COL_EVENTS,
    ]}

def setup_vector_index() -> str:
    """Create the Atlas Vector Search index for kb_chunks if missing."""
    db = get_db()
    col = db[COL_KB_CHUNKS]

    try:
        existing = list(col.list_search_indexes())
        for idx in existing:
            if idx.get("name") == VECTOR_INDEX_NAME:
                return f"already exists ({VECTOR_INDEX_NAME})"
    except OperationFailure:
        pass

    model = SearchIndexModel(
        definition={
            "fields": [
                {
                    "type": "vector",
                    "path": "embedding",
                    "numDimensions": EMBEDDING_DIMS,
                    "similarity": "cosine",
                },
                {"type": "filter", "path": "topic"},
                {"type": "filter", "path": "language"},
            ]
        },
        name=VECTOR_INDEX_NAME,
        type="vectorSearch",
    )
    col.create_search_index(model=model)
    return f"created ({VECTOR_INDEX_NAME}) — note: takes ~1 min to become queryable"
