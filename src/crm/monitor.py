# src/crm/monitor.py
from src.memory.mongo import get_db
from src.config import COL_EVENTS

def get_analytics():
    """Returns aggregated data for Cost Monitor tab."""
    db = get_db()
    return {
        "per_session": list(db[COL_EVENTS].aggregate([
            {"$group": {
                "_id": "$session_id",
                "total_cost": {"$sum": "$financials.total_cost_usd"},
                "avg_latency": {"$avg": "$latency_ms"}
            }}
        ])),
        "per_user": list(db[COL_EVENTS].aggregate([
            {"$group": {
                "_id": "$user_id",
                "total_cost": {"$sum": "$financials.total_cost_usd"},
                "convo_count": {"$addToSet": "$session_id"}
            }}
        ])),
        "global_totals": list(db[COL_EVENTS].aggregate([
            {"$group": {
                "_id": None,
                "total_cost": {"$sum": "$financials.total_cost_usd"},
                "total_tokens_in": {"$sum": "$metadata.input_tokens"},
                "total_tokens_out": {"$sum": "$metadata.output_tokens"}
            }}
        ]))
    }
