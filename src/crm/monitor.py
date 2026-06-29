# src/crm/monitor.py
from src.memory.mongo import get_db
from src.config import COL_EVENTS

def get_analytics():
    """Returns aggregated data for Cost Monitor tab."""
    db = get_db()
    return {
        # REPLACE all 3 aggregations — change collection and field names:

"per_session": list(db["usage_logs"].aggregate([
    {"$group": {
        "_id": "$session_id",
        "total_cost": {"$sum": "$cost"},
        "avg_latency": {"$avg": "$latency_ms"}
    }}
])),
"per_user": list(db["usage_logs"].aggregate([
    {"$group": {
        "_id": "$user_id",
        "total_cost": {"$sum": "$cost"},
        "llm_cost":   {"$sum": "$llm_cost"},
        "embed_cost": {"$sum": "$embedding_cost"},
        "convo_count": {"$addToSet": "$session_id"}
    }}
])),
"global_totals": list(db["usage_logs"].aggregate([
    {"$group": {
        "_id": None,
        "total_cost":      {"$sum": "$cost"},
        "total_tokens_in": {"$sum": "$input_tokens"},
        "total_tokens_out":{"$sum": "$output_tokens"}
    }}
]))
    }
