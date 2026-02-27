# 🎸 PedalBot

**AI-powered assistant for guitar pedal manuals.**

PedalBot lets you upload PDF manuals for any guitar pedal, then ask natural-language questions about settings, features, effects, and pricing — and get accurate, cited answers in seconds.

---

## What It Does

- **Ask anything about your pedal** — settings, signal chain, specs, built-in effects, presets, power requirements
- **Get market pricing** — real-time listings from Reverb.com
- **Upload any PDF manual** — automatically chunked, embedded, and indexed
- **Multi-turn conversations** — remembers context across your chat session
- **Source-cited answers** — every answer includes the page number and section from the manual
- **Typo-tolerant** — normalises your query before routing, so typos don't break lookups

---

## Architecture

```
┌─────────────────────────────────────────────┐
│              Streamlit Frontend              │
│   Home · Chat · Upload · Library · Settings │
└──────────────────┬──────────────────────────┘
                   │ HTTP (REST)
┌──────────────────▼──────────────────────────┐
│              FastAPI Backend                 │
│                                             │
│  ┌──────────┐   ┌──────────────────────┐   │
│  │  Router  │──▶│   Agent Graph        │   │
│  │  Agent   │   │  (LangGraph)         │   │
│  └──────────┘   │                      │   │
│                 │  ManualAgent ────────┼───┼──▶ Pinecone (RAG)
│                 │  PricingAgent ───────┼───┼──▶ Reverb API
│                 │  ExplainerAgent      │   │
│                 └──────────────────────┘   │
│                                             │
│  ┌──────────┐   ┌───────────────────────┐  │
│  │  Ingest  │──▶│  Celery Worker        │  │
│  │  Router  │   │  (PDF → chunks →      │  │
│  └──────────┘   │   embeddings → index) │  │
│                 └───────────────────────┘  │
└────────────┬───────────────────────────────┘
             │
   ┌─────────┼─────────┐
   ▼         ▼         ▼
MongoDB   Pinecone   Redis
(manuals) (vectors)  (broker/cache)
```

### Intent Routing

Every query is classified into one of four intents before being dispatched:

| Intent | Description | Agents Called |
|---|---|---|
| `MANUAL_QUESTION` | Specs, settings, features from the manual | ManualAgent → Pinecone RAG |
| `PRICING` | Market value, where to buy | PricingAgent → Reverb API |
| `EXPLANATION` | Tone, sound character, chain advice | ExplainerAgent (no retrieval) |
| `HYBRID` | Combines manual + pricing | ManualAgent + PricingAgent |

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Streamlit |
| Backend API | FastAPI |
| Agent Orchestration | LangGraph |
| LLM (routing) | Groq — `llama-3.1-8b-instant` |
| LLM (answers) | Groq — configurable via `GROQ_ANSWER_MODEL` |
| Embeddings | VoyageAI — `voyage-3.5-lite` |
| Vector DB | Pinecone |
| Database | MongoDB Atlas (Motor async driver) |
| PDF Storage | MongoDB GridFS |
| Background Jobs | Celery + Redis |
| OCR (optional) | Google Cloud Vision API |
| Pricing Data | Reverb API |
| Observability | LangSmith |
| Deployment | Railway |

---

## Project Structure

```
pedalbot-v2/
├── main.py                    # Entry point (imports backend app)
├── backend/
│   ├── main.py                # FastAPI app — CORS, routes, lifespan
│   ├── state.py               # AgentState, AgentIntent definitions
│   ├── config/
│   │   └── config.py          # Pydantic settings from env vars
│   ├── agents/
│   │   ├── graph.py           # LangGraph agent graph
│   │   ├── router_agent.py    # Intent classification
│   │   ├── manual_agent.py    # RAG over Pinecone
│   │   ├── pricing_agent.py   # Reverb.com pricing
│   │   └── quality_check.py   # Hallucination / confidence check
│   ├── routers/
│   │   ├── query.py           # /api/query endpoint
│   │   └── ingest.py          # /api/ingest/* endpoints
│   ├── services/
│   │   ├── pdf_processor.py   # PDF → text chunks (+ OCR fallback)
│   │   ├── embeddings.py      # VoyageAI embedding service
│   │   ├── pinecone_client.py # Pinecone upsert & query
│   │   ├── pedal_registry.py  # Cached pedal name → namespace map
│   │   ├── query_preprocessor.py  # Typo correction, query normalisation
│   │   └── gridfs_storage.py  # PDF storage in MongoDB GridFS
│   ├── workers/
│   │   ├── celery_app.py      # Celery application instance
│   │   ├── ingest_worker.py   # PDF ingestion task
│   │   ├── pricing_worker.py  # Async pricing fetch
│   │   └── email_worker.py    # Email notification worker
│   ├── db/
│   │   ├── mongodb.py         # Motor async client
│   │   └── models.py          # ManualDocument, IngestionJobDocument
│   ├── auth/
│   │   ├── models.py          # User model
│   │   ├── route.py           # Auth routes
│   │   └── hash_utils.py      # Password hashing
│   └── prompts/
│       └── manual_prompts.py  # LLM prompt templates
└── frontend/
    ├── Home.py                # Landing page + status overview
    ├── pages/
    │   ├── 1_💬_Chat.py       # Multi-turn chat interface
    │   ├── 2_📤_Upload.py     # PDF upload + ingestion status
    │   ├── 3_📚_Library.py    # Manage indexed manuals
    │   └── 4_⚙️_Settings.py  # API URL + config
    └── utils/
        ├── api_client.py      # HTTP client wrapping the FastAPI backend
        ├── styles.py          # Custom CSS
        ├── design_tokens.py   # Colour + typography tokens
        └── loading_components.py  # Skeleton loaders
```

---

## Getting Started

### Prerequisites

- Python 3.11+
- Redis (local or hosted)
- MongoDB Atlas cluster
- Pinecone account (index: `pedalbot`, dimension: `1024`, metric: `cosine`)
- Groq API key
- VoyageAI API key

### Setup

```bash
# 1. Clone the repo
git clone https://github.com/EbenTheGreat/pedalbot-v2.git
cd pedalbot-v2

# 2. Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env and fill in your API keys
```

### Running Locally

```bash
# Terminal 1 — FastAPI backend
uvicorn backend.main:app --reload --port 8000

# Terminal 2 — Celery worker (PDF ingestion)
celery -A backend.workers.celery_app worker --loglevel=info

# Terminal 3 — Streamlit frontend
cd frontend
streamlit run Home.py
```

Then open **http://localhost:8501** in your browser.

> **Note:** If Redis is unavailable, ingestion falls back to processing inline (no Celery needed for local testing).

---

## Environment Variables

Copy `.env.example` to `.env` and fill in:

| Variable | Required | Description |
|---|---|---|
| `MONGODB_URI` | ✅ | MongoDB Atlas connection string |
| `MONGODB_DB_NAME` | ✅ | Database name (default: `pedalbot_db`) |
| `PINECONE_API_KEY` | ✅ | Pinecone API key |
| `PINECONE_INDEX_NAME` | | Index name (default: `pedalbot`) |
| `GROQ_API_KEY` | ✅ | Groq API key |
| `GROQ_ROUTER_MODEL` | | Model for intent routing (default: `llama-3.1-8b-instant`) |
| `GROQ_ANSWER_MODEL` | | Model for answers |
| `VOYAGEAI_API_KEY` | ✅ | VoyageAI embeddings key |
| `JWT_SECRET_KEY` | ✅ | Generate with: `openssl rand -hex 32` |
| `REDIS_URL` | | Redis connection URL |
| `REVERB_API_KEY` | | Reverb.com API key (for pricing) |
| `GOOGLE_VISION_CREDENTIALS` | | Base64-encoded service account JSON (for OCR) |
| `LANGSMITH_API_KEY` | | LangSmith tracing |
| `ENV` | | `development` or `production` |

---

## PDF Ingestion Pipeline

When you upload a manual:

1. **Upload** — PDF is saved to disk and stored in MongoDB GridFS (for cross-service access)
2. **Extract** — Text is extracted with `pdfplumber`; if quality is low (< 0.3 confidence score), Google Vision OCR kicks in automatically
3. **Chunk** — Text is split into ~300-token chunks with 100-token overlap
4. **Embed** — Each chunk is embedded with VoyageAI `voyage-3.5-lite`
5. **Index** — Vectors are upserted to Pinecone under a unique namespace per manual
6. **Register** — Pedal name + namespace are cached in `PedalRegistry` for fast lookups

You can check progress at `/api/ingest/status/{manual_id}`.

---

## API Reference

### Query

```
POST /api/query
Body: { "query": "What is the input impedance?", "pedal_name": "Boss GT-1", "conversation_id": "uuid" }
```

### Ingest

```
POST /api/ingest/upload          — Upload a PDF manual
GET  /api/ingest/manuals         — List all indexed manuals
GET  /api/ingest/status/{id}     — Check ingestion progress
POST /api/ingest/retry/{id}      — Retry a failed ingestion
DELETE /api/ingest/{id}          — Delete a manual + its vectors
```

Full interactive docs available at `http://localhost:8000/docs`.

---

## Deployment (Railway)

The project is set up for Railway with three services:

| Service | Dockerfile | Purpose |
|---|---|---|
| `api` | `Dockerfile` | FastAPI backend |
| `worker` | `Dockerfile.celery` | Celery ingestion worker |
| `frontend` | *(Streamlit)* | Streamlit UI |

Add-ons: **MongoDB**, **Redis** (provided by Railway).

Environment variables are injected via Railway's service config. Production settings are validated on boot — the app exits immediately if any required variable is missing.

---

## License

MIT
