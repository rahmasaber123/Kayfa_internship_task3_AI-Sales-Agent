from dataclasses import dataclass, field
from typing import Any, Optional, Dict, List
from src.kb.loader import KnowledgeBase
from src.kb.retriever import HybridRetriever
from src.memory.profile import UserProfile
from src.observer import Observer

@dataclass
class AgentDeps:
    user_id: str
    session_id: str
    kb: KnowledgeBase
    retriever: HybridRetriever
    profile: UserProfile
    observer: Optional[Observer] = None
    is_cache_hit: bool = False
    language: str = "ar"
    dialect: Optional[str] = None
    competitor_flag: Optional[str] = None
    scenario: str = "ad_hoc"
    
    # 👈 Added isolated trace and tool counts
    trace_buffer: List[Dict[str, Any]] = field(default_factory=list)
    tool_call_counts: Dict[str, int] = field(default_factory=dict)