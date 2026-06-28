import sys
from pathlib import Path
from datetime import datetime, timezone

# 1. Force the root directory into Python's path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.append(str(root_dir))

class Observer:
    def __init__(self) -> None:
        from src.memory.mongo import get_db
        self.db = get_db()
        self.collection = self.db["usage_logs"]

    def record(self, user_id: str, session_id: str, turn_id: str, scenario: str, 
               user_message: str, assistant_reply: str, model: str, 
               tokens_in: int, tokens_out: int, used_rag: bool, 
               is_cache_hit: bool = False, # <--- المتغير الجديد
               trace: list = None, latency_ms: int = 0, language: str = "ar", errors: list = None) -> None:
        
        cost = (tokens_in * 0.00000015) + (tokens_out * 0.00000060) + (0.00004 if used_rag else 0)
        
        event_doc = {
            "user_id": user_id,
            "session_id": session_id,
            "turn_id": turn_id,
            "timestamp": datetime.now(timezone.utc),
            "scenario": scenario,
            "model": model,
            "language": language,
            "latency_ms": latency_ms,
            "cost": cost,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "embedding_tokens": 2000 if used_rag else 0,
            "trace": trace or [],
            "user_message": user_message,
            "assistant_reply": assistant_reply,
            "errors": errors or [],
            "is_cache_hit": is_cache_hit # <--- حفظ الحالة في قاعدة البيانات
        }
        
        try:
            self.collection.insert_one(event_doc)
        except Exception as e:
            print(f"❌ Observer failed to write to MongoDB: {e}")
     