# Kayfa Sales Agent — Final

Bilingual (Arabic/English) AI sales agent for Kayfa, built on **Agentic Hybrid RAG** with Pydantic AI, GPT-4o-mini, OpenAI embeddings, MongoDB Atlas, and Streamlit.

> Week 3 task · Agentic AI Internship @ Kayfa

## Stack

| Layer | Choice |
|---|---|
| Agent framework | Pydantic AI |
| Main LLM | OpenAI `gpt-4o-mini` (reliable structured outputs) |
| Summarizer | Groq `llama-3.1-8b-instant` |
| Embeddings | OpenAI `text-embedding-3-large` @ 1024 dims |
| Keyword retrieval | `rank-bm25` |
| Vector retrieval | MongoDB Atlas Vector Search |
| Fusion | Reciprocal Rank Fusion (RRF), source-deduped |
| Persistence | MongoDB Atlas (`users` database) |
| UI | Streamlit, Kayfa-branded, light + navy theme |

## Architecture

**Agentic Hybrid RAG with action tools.** One agent, **5 tools**:

| Tool | Purpose |
|---|---|
| `search_courses` | JSON filter on courses (track, level) |
| `search_roadmaps` | JSON filter on roadmaps (diplomas + tracks) |
| `search_knowledge` | Hybrid retrieval over all MD docs |
| `save_lead_ticket` | Action — Arabic ticket in MongoDB |
| `escalate_to_human` | Action — escalation ticket (with duplicate-prevention) |

**Architectural rule:** structured JSON → deterministic tools; all markdown documents (diplomas, policies, pricing, instructors, company overview, free content) → RAG.

Single consolidated system prompt at `prompts/snippets/skills.md` (~1,500 tokens). Dynamic per-turn instructions inject the live user profile, dialect, and competitor flag.

## File layout

```
kayfa-sales-agent/
├── app/                            # Streamlit UI
│   ├── streamlit_app.py            #   login gate + landing
│   ├── pages/
│   │   ├── 1_💬_Chat.py             #   chat with session history + observability
│   │   └── 2_🎫_Tickets.py          #   CRM dashboard (leads + escalations)
│   ├── ui/
│   │   ├── branding.py              #   Kayfa colors, logo, CSS
│   │   └── rtl.py                   #   per-message direction detection
│   └── assets/                      #   logo
│
├── notebook.ipynb                   # lab bench (sections 0–13)
├── data/                            # KB (48 courses, 13 roadmaps, 12 MD docs)
├── prompts/snippets/skills.md       # consolidated system prompt
├── src/                             # all logic — agent, kb, memory, crm, guardrails
├── .streamlit/
│   ├── config.toml                  # theme
│   └── secrets.toml.example         # secret template
├── .env.example                     # local dev env template
├── requirements.txt
└── README.md
```

## Local quickstart

```bash
# 1. Install
pip install -r requirements.txt

# 2. Configure secrets
cp .env.example .env
# edit .env with your OPENAI_API_KEY, GROQ_API_KEY, MONGODB_URI

# 3. Build the KB index (once)
python -c "from src.kb.loader import load_knowledge_base; from src.kb.retriever import build_and_persist_chunks; kb = load_knowledge_base(); print(build_and_persist_chunks(kb, force=True))"

# 4. Run Streamlit
streamlit run app/streamlit_app.py
```

## Deploy to Streamlit Community Cloud (HTTPS gate)

1. Push the repo to GitHub (private is fine — Community Cloud has access).
2. Go to https://share.streamlit.io → "New app" → connect the repo.
3. Set entry point: `app/streamlit_app.py`.
4. In **Advanced settings → Secrets**, paste the contents of `.streamlit/secrets.toml.example`, filling in real values.
5. Deploy. Streamlit Community Cloud serves on HTTPS by default.
6. Share the link — login gate protects the demo behind `DEMO_PASSWORD`.

## Colab quickstart (for notebook testing)

1. Upload `kayfa-sales-agent.zip` to `/content/`.
2. Set 3 secrets in 🔑 sidebar: `OPENAI_API_KEY`, `GROQ_API_KEY`, `MONGODB_URI`.
3. Open `notebook.ipynb`, run sections 0–13.

## Key design decisions

- **Structured data → tools, prose → RAG.** No exceptions, no special cases. The whole architecture follows this single rule.
- **One consolidated system prompt.** Earlier versions had 7 separate snippet files (~14k chars). Consolidated to one file (~6k chars) for token efficiency.
- **GPT-4o-mini over Qwen.** Qwen3-32B was stronger on Arabic dialects but unreliable at structured output. GPT-4o-mini handles Pydantic schemas rock-solid.
- **Per-message RTL.** Each message detects its own script and aligns accordingly — Arabic right-to-left, English left-to-right. Mixed conversations flow naturally.
- **Course links rendered as buttons.** The agent emits markdown links; CSS turns them into Kayfa-blue buttons inside chat.

## Deferred (v2+, post-internship)

- Cross-session semantic memory
- Semantic cache for high-frequency queries
- LangGraph migration (only if multi-agent supervisor becomes necessary)
- Cohere/BGE reranker (only if KB grows past 1 MB)
- FastAPI layer (only if a non-Streamlit client needs the agent)

## License

Internship deliverable for Kayfa. Not for redistribution.
