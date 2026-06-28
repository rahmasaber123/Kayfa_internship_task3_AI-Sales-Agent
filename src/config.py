"""Central config: paths, model IDs, constants, secrets."""
from pathlib import Path
import os
from dotenv import load_dotenv

# Load .env file automatically if it exists
load_dotenv(override=True)

# ── Paths ─────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
PROMPTS_DIR = ROOT / "prompts"
RUNS_DIR = ROOT / "runs"

# ── Secrets (must be set in environment) ──────────────────────────────
def _require(key: str) -> str:
    v = os.environ.get(key)
    if not v:
        # وفرنا رسالة توضيحية بدلاً من مجرد الانهيار
        raise RuntimeError(f"Missing env var: {key}. Please ensure .env file exists in the root folder.")
    return v

OPENAI_API_KEY = _require("OPENAI_API_KEY")
MONGODB_URI = _require("MONGODB_URI")

# ── Models ────────────────────────────────────────────────────────────
MAIN_MODEL = "openai-chat:gpt-4o-mini"
SUMMARIZER_MODEL = "groq:llama-3.1-8b-instant"
EMBEDDING_MODEL = "text-embedding-3-large"
EMBEDDING_DIMS = 1024

# ── MongoDB ───────────────────────────────────────────────────────────
DB_NAME = "users"
COSL_USERS = "users"
COL_DOC = "docs"
COL_SESSIONS = "sessions"
COL_MESSAGES = "messages"
COL_PROFILES = "user_profiles"
COL_SUMMARIES = "summaries"
COL_KB_CHUNKS = "kb_chunks"
COL_TICKETS = "tickets"
COL_EVENTS = "events"
VECTOR_INDEX_NAME = "kb_chunks"
COL_USAGE_LOGS = "usage_logs"

COL_COURSES = "courses"
COL_ROADMAPS = "roadmaps"
# ── Behavior ──────────────────────────────────────────────────────────
RETRIEVER_TOP_K = 3
RETRIEVER_RRF_K = 60          # standard RRF constant
SUMMARY_TRIGGER_TURNS = 10
SUMMARY_KEEP_RECENT = 4
MAX_USER_MESSAGE_CHARS = 2000
CHUNK_TARGET_TOKENS = 400     # ~rough; we split by sections then size

# ── Pricing ──────────────────────────────────────────────────────────
PRICE_LLM_IN_PER_TOKEN = 0.00000015
PRICE_LLM_OUT_PER_TOKEN = 0.0000006
PRICE_EMBEDDING_PER_TOKEN = 0.00000002

# ── Competitor list (lowercased substrings, AR + EN) ──────────────────
COMPETITORS = [
    "udemy", "coursera", "edx", "udacity", "datacamp",
    "almentor", "edraak", "rwaq", "nagwa", "skillshare",
    "linkedin learning", "pluralsight",
    "المنتور", "إدراك", "رواق", "نجوى",
]