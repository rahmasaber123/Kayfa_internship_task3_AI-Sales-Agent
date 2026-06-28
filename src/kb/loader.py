import logging
from dataclasses import dataclass, field
from functools import cache
from src.memory.mongo import get_db

# إعداد الـ logger
logger = logging.getLogger("Kayfa.KB")

@dataclass
class MdDoc:
    name: str
    text: str
    topic: str
    # إضافة الحقل للغة بشكل ديناميكي
    language: str = "ar" 

@dataclass
class KnowledgeBase:
    courses: list[dict] = field(default_factory=list)
    roadmaps: list[dict] = field(default_factory=list)
    docs: list[MdDoc] = field(default_factory=list)

def _topic_from_filename(stem: str) -> str:
    s = stem.lower()
    mapping = {
        "policy": ["policy", "privacy", "faq"],
        "diploma": ["diploma"],
        "company": ["company"],
        "instructor": ["instructor"],
        "catalog": ["paid", "free", "track", "course"]
    }
    for topic, keywords in mapping.items():
        if any(k in s for k in keywords):
            return topic
    return "other"

@cache
def load_knowledge_base(force_refresh: bool = False) -> KnowledgeBase:
    """Load the full KB from MongoDB with robust error handling."""
    
    # إذا كنت تريد طريقة لتحديث الـ KB دون إعادة تشغيل:
    if force_refresh:
        load_knowledge_base.cache_clear()

    try:
        db = get_db()
        
        # استخدام projection لتقليل حجم البيانات المنقولة
        courses = list(db["courses"].find({}, {"_id": 0}))
        roadmaps = list(db["roadmaps"].find({}, {"_id": 0}))
        db_docs = list(db["docs"].find({}, {"_id": 0}))
        
        docs: list[MdDoc] = []
        for d in db_docs:
            # استخدام .get للحماية من الـ KeyError
            name = d.get("name", "unknown_doc")
            text = d.get("text", "")
            if not text:
                logger.warning(f"Document {name} is empty, skipping.")
                continue
                
            docs.append(
                MdDoc(
                    name=name,
                    text=text,
                    topic=d.get("topic", _topic_from_filename(name)),
                )
            )

        logger.info(f"✅ KB Loaded: {len(courses)} courses, {len(roadmaps)} roadmaps, {len(docs)} docs.")
        return KnowledgeBase(courses=courses, roadmaps=roadmaps, docs=docs)

    except Exception as e:
        logger.error(f"❌ Critical KB Load Error: {e}")
        return KnowledgeBase()
