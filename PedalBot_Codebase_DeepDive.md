# PedalBot Codebase Deep Dive
### A Complete Guide to Understanding Every File

---

## Table of Contents
1. [Project Structure Overview](#project-structure-overview)
2. [Entry Points](#entry-points)
3. [Configuration Layer](#configuration-layer)
4. [Database Layer](#database-layer)
5. [Services Layer](#services-layer)  
6. [Agents Layer (The AI Brain)](#agents-layer-the-ai-brain)
7. [Workers Layer (Background Jobs)](#workers-layer-background-jobs)
8. [API Routers Layer](#api-routers-layer)
9. [State Management](#state-management)
10. [How It All Connects](#how-it-all-connects)

---

## Project Structure Overview

```
pedalbot-langgraph/
├── backend/                    # All backend code
│   ├── main.py                # FastAPI entry point
│   ├── state.py               # Shared state for agents
│   ├── agents/                # AI agents (the brain)
│   │   ├── graph.py           # LangGraph orchestration
│   │   ├── router_agent.py    # Intent classification
│   │   ├── manual_agent.py    # RAG for manuals
│   │   ├── pricing_agent.py   # Market pricing
│   │   └── quality_check.py   # Answer validation
│   ├── services/              # Core business logic
│   │   ├── pinecone_client.py # Vector database client
│   │   ├── embeddings.py      # VoyageAI embeddings
│   │   ├── pdf_processor.py   # PDF text extraction
│   │   └── pedal_registry.py  # Pedal name resolution
│   ├── workers/               # Background tasks
│   │   ├── celery_app.py      # Celery configuration
│   │   ├── ingest_worker.py   # PDF processing worker
│   │   ├── pricing_worker.py  # Price refresh worker
│   │   └── email_worker.py    # Email notifications
│   ├── routers/               # API endpoints
│   │   ├── query.py           # /api/query endpoints
│   │   └── ingest.py          # /api/ingest endpoints
│   ├── db/                    # Database layer
│   │   ├── mongodb.py         # MongoDB client
│   │   └── models.py          # Pydantic schemas
│   └── config/                # Configuration
│       └── config.py          # Environment settings
├── docker-compose.yml         # Docker orchestration
└── requirements.txt           # Python dependencies
```

---

## Entry Points

### `backend/main.py` - The Front Door
This is where everything starts. When you run `uvicorn backend.main:app`, this file is loaded.

**What it does:**
1. **Creates the FastAPI app** - The web server that handles HTTP requests
2. **Connects to MongoDB** on startup - Uses the lifespan context manager
3. **Registers all routers** - Links `/api/query` and `/api/ingest` endpoints
4. **Adds CORS middleware** - Allows frontend apps to talk to the API

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # STARTUP: Connect MongoDB
    await MongoDB.connect(uri=settings.MONGODB_URI, db_name=settings.MONGODB_DB_NAME)
    yield
    # SHUTDOWN: Close MongoDB
    await MongoDB.close()
```

**Key insight:** The `lifespan` function ensures MongoDB is connected before any requests are served, and cleaned up when the server stops.

---

## Configuration Layer

### `backend/config/config.py` - The Settings Hub
This file loads all environment variables from `.env` and provides type-safe access to them.

**How it works:**
1. Uses `pydantic-settings` to parse environment variables
2. Provides defaults for optional settings
3. Validates required settings (will fail fast if missing)

**Key settings groups:**
| Group | Examples | Purpose |
|-------|----------|---------|
| Database | `MONGODB_URI`, `MONGODB_DB_NAME` | Connect to MongoDB |
| Vector DB | `PINECONE_API_KEY`, `PINECONE_INDEX_NAME` | Connect to Pinecone |
| LLM | `GROQ_API_KEY`, `VOYAGEAI_API_KEY` | AI model access |
| Redis | `REDIS_URI` | Background task queue |
| Ingestion | `PDF_CHUNK_SIZE`, `PDF_CHUNK_OVERLAP` | How PDFs are split |

**Usage pattern:**
```python
from backend.config.config import settings

# Access any setting
api_key = settings.GROQ_API_KEY
chunk_size = settings.PDF_CHUNK_SIZE
```

---

## Database Layer

### `backend/db/mongodb.py` - The MongoDB Client
A singleton manager for MongoDB connections.

**Why a singleton?**
- Connections are expensive to create
- Connection pooling improves performance
- Ensures consistent access across the app

**Key methods:**
| Method | Purpose |
|--------|---------|
| `connect()` | Initialize connection with pooling |
| `close()` | Clean shutdown |
| `get_database()` | Get the database instance |
| `_create_indexes()` | Create indexes on startup |

**Indexes created:**
- `users.user_id` (unique)
- `manuals.pedal_name` 
- `pricing.pedal_name` (with 24h TTL for auto-expiry)
- And more...

---

### `backend/db/models.py` - The Data Schemas
Pydantic models that define the shape of all data in MongoDB.

**Collections and their models:**

#### 1. `UserDocument` - Users collection
```python
class UserDocument(BaseModel):
    user_id: str          # "user_a1b2c3d4e5f6"
    email: EmailStr
    hashed_password: str
    role: UserRole        # free, pro, store, admin
    preferences: UserPreferences
    queries_count: int
```

#### 2. `ConversationDocument` - Chat history
```python
class ConversationDocument(BaseModel):
    conversation_id: str
    user_id: str
    messages: List[Message]   # [{"role": "user", "content": "..."}, ...]
    pedal_context: str        # Current pedal being discussed
```

#### 3. `ManualDocument` - Uploaded manuals
```python
class ManualDocument(BaseModel):
    manual_id: str
    pedal_name: str           # "Boss DS-1"
    pinecone_namespace: str   # "boss_ds_1"
    status: ManualStatus      # pending, processing, completed, failed
    chunk_count: int
    ocr_required: bool
```

#### 4. `IngestionJobDocument` - Background job tracking
```python
class IngestionJobDocument(BaseModel):
    job_id: str
    manual_id: str
    status: JobStatus         # queued, in_progress, completed, failed
    progress: float           # 0-100
    chunks_processed: int
```

#### 5. `PricingDocument` - Cached market prices
```python
class PricingDocument(BaseModel):
    pedal_name: str
    avg_price: float
    min_price: float
    max_price: float
    total_listings: int
    updated_at: datetime      # TTL index deletes after 24h
```

---

## Services Layer

### `backend/services/pinecone_client.py` - Vector Database Client
Handles all communication with Pinecone (the vector database).

**Core operations:**

#### 1. `upsert_chunks()` - Store vectors
```python
def upsert_chunks(self, namespace, chunks, embeddings, metadata_list):
    """
    Store text chunks as vectors in Pinecone.
    
    Each chunk becomes a vector with:
    - id: "boss_ds1_chunk_0"
    - values: [0.1, 0.2, ...] (the embedding)
    - metadata: {"text": "...", "page_number": 5, ...}
    """
```

#### 2. `search()` - Find similar content
```python
def search(self, query_embedding, namespace, top_k=5):
    """
    Find the most similar chunks to a query.
    
    Returns: List[SearchResult] with:
    - chunk_id
    - text (the actual content)
    - score (0.0 to 1.0 similarity)
    - metadata
    """
```

**Namespaces explained:**  
Each pedal manual gets its own "namespace" in Pinecone. This isolates searches:
- `manual_boss_ds_1` - Only Boss DS-1 content
- `manual_helix` - Only Helix content

---

### `backend/services/embeddings.py` - Text to Vectors
Converts text into mathematical vectors using VoyageAI.

**What are embeddings?**  
Embeddings are lists of numbers that represent the "meaning" of text. Similar text has similar numbers.

```
"What is the input impedance?" → [0.1, 0.2, 0.3, ...]
"What's the input Z?"          → [0.11, 0.19, 0.31, ...]  (similar!)
"What color is it?"            → [0.9, 0.1, 0.2, ...]     (different)
```

**Key class: `EmbeddingService`**
```python
class EmbeddingService:
    async def embed_texts(self, texts: List[str]) -> EmbeddingResult:
        """
        Convert text to vectors.
        
        Args:
            texts: ["What is the impedance?", "How do I connect it?"]
        
        Returns:
            EmbeddingResult with:
            - embeddings: [[0.1, 0.2...], [0.3, 0.4...]]
            - token_count: 25
            - cost_usd: 0.0001
        """
```

**Cost tracking:**  
Every embedding call tracks tokens and cost. This helps monitor API spend.

---

### `backend/services/pdf_processor.py` - PDF Text Extraction
Extracts text from PDFs and splits it into searchable chunks.

**The chunking problem:**  
LLMs have context limits. A 500-page manual won't fit. Solution: break it into overlapping pieces.

**Process:**
1. **Open PDF** using PyMuPDF
2. **Extract text** page by page
3. **Quality check** - Is the text readable or is it an image-based PDF?
4. **OCR fallback** - If quality is low, use Google Vision API
5. **Chunking** - Split into ~500 token pieces with 50 token overlap
6. **Section detection** - Identify "Specifications", "Controls", etc.

**The `PdfChunk` dataclass:**
```python
@dataclass
class PdfChunk:
    text: str              # The actual content
    chunk_index: int       # Which chunk (0, 1, 2...)
    page_number: int       # Page in the PDF
    section: Optional[str] # "specifications", "controls", etc.
    token_estimate: int    # Rough token count
```

**Why overlap?**  
If a user asks about something that spans two chunks, the overlap ensures context isn't lost.

---

### `backend/services/pedal_registry.py` - Name Resolution
Bridges user input to system identifiers.

**The problem:**  
User says: `"Helix"`  
Namespace is: `"manual_helix_3.80_owner's_manual___english"`

**Solution: Fuzzy matching**
```python
async def resolve(self, user_input: str) -> Optional[PedalInfo]:
    """
    User input: "Helix"
    
    Matching attempts:
    1. Exact: "helix" in cache? No
    2. Prefix: starts with "helix"? Yes! → Found
    3. Substring: contains "helix"? 
    4. Word match: shared words?
    
    Returns: PedalInfo(
        display_name="Helix 3.80 Owner's Manual",
        namespace="manual_helix_3.80_...",
        pedal_type=MULTI_EFFECTS
    )
    """
```

**Pedal types matter:**  
Multi-effects units (Helix, GT-10) ALWAYS need retrieval because their features are documented in the manual.

---

## Agents Layer (The AI Brain)

### `backend/state.py` - Shared State
The "memory" that travels through the entire agent workflow.

```python
class AgentState(BaseModel):
    # Input
    user_id: str
    conversation_id: str
    query: str                    # "What's the input impedance?"
    pedal_name: str               # "Boss DS-1"
    
    # Routing
    intent: Optional[AgentIntent] # MANUAL_QUESTION, PRICING, EXPLANATION
    
    # Retrieval results
    pinecone_namespace: str
    retrieved_chunks: List[str]   # The manual excerpts found
    retrieval_scores: List[float] # Relevance scores
    
    # Outputs
    raw_answer: Optional[str]     # Draft answer from agent
    final_answer: Optional[str]   # Approved answer
    price_info: Optional[Dict]    # Pricing data
    
    # Quality
    hallucination_flag: bool      # Was the answer made up?
    confidence_score: float       # 0.0 to 1.0
    needs_human_review: bool
    
    # Debugging
    agent_path: List[str]         # ["router", "manual_agent", "synthesizer"]
    error: Optional[str]
```

**Key insight:** Every agent reads AND writes to this state. The state IS the communication mechanism.

---

### `backend/agents/graph.py` - The LangGraph Orchestrator
The conductor that coordinates all agents.

**The workflow:**
```
User Query
    ↓
┌────────────────┐
│  Router Agent  │ → Classifies intent
└───────┬────────┘
        ↓
    ┌───┴────────────────┬─────────────────┐
    ↓                    ↓                 ↓
┌─────────┐      ┌─────────────┐    ┌──────────┐
│ Manual  │      │   Pricing   │    │Explanation│
│ Agent   │      │   Agent     │    │  Agent   │
└────┬────┘      └──────┬──────┘    └─────┬────┘
     ↓                  ↓                 ↓
     └──────────────────┼─────────────────┘
                        ↓
              ┌─────────────────┐
              │ Quality Check   │ → Validates answer
              └────────┬────────┘
                       ↓
            ┌──────────┴──────────┐
            ↓                     ↓
      ┌───────────┐         ┌──────────┐
      │Synthesizer│         │ Fallback │
      └─────┬─────┘         └────┬─────┘
            ↓                    ↓
         Answer               Safe error message
```

**The `PedalBotGraph` class:**
```python
class PedalBotGraph:
    def __init__(self, router_agent, manual_agent, pricing_agent, quality_check_agent):
        self.graph = self._build_graph()  # Compile the workflow
    
    def _build_graph(self):
        workflow = StateGraph(AgentState)
        
        # Add nodes
        workflow.add_node("router", self._router_node)
        workflow.add_node("manual_agent", self._manual_agent_node)
        workflow.add_node("pricing_agent", self._pricing_agent_node)
        workflow.add_node("quality_check", self._quality_check_node)
        workflow.add_node("synthesizer", self._synthesizer_node)
        workflow.add_node("fallback", self._fallback_node)
        
        # Add edges (the flow)
        workflow.set_entry_point("router")
        workflow.add_conditional_edges("router", self._route_after_router, {...})
        workflow.add_edge("manual_agent", "quality_check")
        workflow.add_conditional_edges("quality_check", self._route_after_quality_check, {...})
        
        return workflow.compile()
```

**Conditional routing:**  
The router decides which specialist to invoke based on intent:
- `MANUAL_QUESTION` → Manual Agent
- `PRICING` → Pricing Agent
- `HYBRID` → Multiple agents

---

### `backend/agents/router_agent.py` - Intent Classification
Analyzes the user's question to determine what kind of answer is needed.

**Intents:**
| Intent | Example Question | Next Agent |
|--------|------------------|------------|
| `MANUAL_QUESTION` | "What's the input impedance?" | Manual Agent |
| `PRICING` | "How much does it cost?" | Pricing Agent |
| `EXPLANATION` | "What does fuzz sound like?" | Explainer Agent |
| `HYBRID` | "Is it worth $100?" | Multiple agents |

**How it works:**
```python
async def route(self, state: AgentState) -> AgentState:
    # 1. Build prompt with user query
    user_prompt = f"Query: {state.query}\nPedal context: {state.pedal_name}"
    
    # 2. Ask LLM to classify
    response = await self.llm.ainvoke([
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=user_prompt)
    ])
    
    # 3. Parse JSON response
    result = self._parse_response(response.content)
    # {"intent": "MANUAL_QUESTION", "confidence": 0.95, ...}
    
    # 4. Update state
    state.intent = AgentIntent(result["intent"].lower())
    state.confidence_score = result["confidence"]
    state.agent_path.append("router")
    
    return state
```

---

### `backend/agents/manual_agent.py` - RAG (Retrieval-Augmented Generation)
The workhorse agent that answers questions from manual content.

**The RAG pipeline:**
```
1. QUERY: "What's the input impedance?"
       ↓
2. EMBED: Convert to vector [0.1, 0.2, 0.3, ...]
       ↓
3. SEARCH: Find similar chunks in Pinecone
       ↓
4. RETRIEVE: Get top 5 most relevant chunks
       ↓
5. GENERATE: Ask LLM to answer using ONLY these chunks
       ↓
6. ANSWER: "The input impedance is 1MΩ (per the specifications)."
```

**Key constraint (in the system prompt):**
```
You are an expert guitar pedal assistant.
Your task is to answer using ONLY the information explicitly stated 
in the provided manual excerpts.

CRITICAL RULES:
1. Use ONLY facts from the manual excerpts
2. Do NOT infer or assume
3. If information is NOT present, say "I don't have that information"
4. Cite page numbers when available
```

**Why so strict?** To prevent hallucinations. The agent is ONLY allowed to use retrieved content.

---

### `backend/agents/pricing_agent.py` - Market Data
Fetches real-time pricing from Reverb.

**Data flow:**
1. Check MongoDB cache (24h TTL)
2. If cache miss, call Reverb API
3. Parse listings and compute stats
4. Cache result
5. Return formatted price info

**Price info structure:**
```python
{
    "pedal_name": "Boss DS-1",
    "avg_price": 54.99,
    "min_price": 35.00,
    "max_price": 89.99,
    "median_price": 55.00,
    "total_listings": 127,
    "source": "reverb"
}
```

---

### `backend/agents/quality_check.py` - Answer Validation
The last line of defense against hallucinations.

**What it checks:**
1. **Hallucinations** - Is info in the answer actually in the sources?
2. **Contradictions** - Does the answer conflict with sources?
3. **Accuracy** - Are specific numbers correct?
4. **Completeness** - Did it miss important info?

**The gate:**
```python
def should_reject_answer(state: AgentState) -> bool:
    # Reject if hallucination detected
    if state.hallucination_flag:
        return True
    
    # Reject if confidence too low
    if state.confidence_score < 0.3:
        return True
    
    # Reject if error occurred
    if state.error:
        return True
    
    return False
```

**If rejected:** Goes to fallback node which returns a safe message:
> "I couldn't find reliable information about that in the manual."

---

## Workers Layer (Background Jobs)

### `backend/workers/celery_app.py` - Task Configuration
Configures Celery for background task processing.

**Queues:**
| Queue | Purpose | Task Examples |
|-------|---------|---------------|
| `ingestion` | PDF processing | `ingest_manual` |
| `pricing` | Price refresh | `refresh_pricing` |
| `notifications` | Emails | `send_welcome_email` |

**Why separate queues?**  
Different priorities and resource needs. Ingestion is heavy; emails are lightweight.

**Scheduled tasks (Celery Beat):**
```python
beat_schedule = {
    "refresh-all-pricing": {
        "task": "refresh_all_pricing_task",
        "schedule": crontab(hour=2, minute=0),  # Daily at 2 AM
    },
    "cleanup-old-jobs": {
        "task": "cleanup_old_jobs",
        "schedule": crontab(day_of_week=1, hour=3),  # Weekly
    }
}
```

---

### `backend/workers/ingest_worker.py` - PDF Processing Worker
The heavy lifter that processes uploaded PDFs.

**The full ingestion pipeline:**
```python
@app.task(name="ingest_manual")
def process_manual_task(manual_id: str):
    """
    1. Connect to MongoDB
    2. Get manual record
    3. Process PDF:
       - Extract text (with OCR fallback)
       - Split into chunks
       - Update progress: 30%
    4. Generate embeddings:
       - Call VoyageAI for each chunk
       - Update progress: 60%
    5. Upload to Pinecone:
       - Upsert vectors with metadata
       - Update progress: 90%
    6. Update manual status:
       - Set status = "completed"
       - Record chunk count
       - Update progress: 100%
    """
```

**Error handling:**
```python
except Exception as e:
    # Retry with exponential backoff
    # 1st retry: 60 seconds
    # 2nd retry: 120 seconds
    # 3rd retry: 240 seconds
    raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))
```

---

## API Routers Layer

### `backend/routers/query.py` - Query Endpoints
The main interface for asking questions.

**Endpoints:**

#### `GET /api/query/pedals` - List available pedals
```json
{
    "pedals": [
        {"pedal_name": "Boss DS-1", "chunk_count": 87, ...},
        {"pedal_name": "Helix", "chunk_count": 342, ...}
    ],
    "total": 2
}
```

#### `POST /api/query/` - Ask a question
**Request:**
```json
{
    "query": "What is the input impedance?",
    "pedal_name": "Boss DS-1"
}
```

**Response:**
```json
{
    "answer": "The input impedance is 1MΩ according to the specifications.",
    "conversation_id": "conv_abc123",
    "user_id": "anon_xyz789",
    "intent": "manual_question",
    "confidence": 0.92,
    "agent_path": ["router", "manual_agent", "quality_check", "synthesizer"],
    "hallucination_flag": false,
    "latency_ms": 1243,
    "sources": ["[Page 12] Specifications: Input impedance: 1MΩ..."]
}
```

#### `POST /api/query/stream` - Streaming response
Returns Server-Sent Events (SSE) for real-time updates:
```
data: {"type": "session", "conversation_id": "conv_123", "user_id": "anon_456"}
data: {"type": "node", "node": "router"}
data: {"type": "node", "node": "manual_agent"}
data: {"type": "answer", "text": "The input impedance is..."}
data: {"type": "done"}
```

---

### `backend/routers/ingest.py` - Ingestion Endpoints
API for uploading and processing manuals.

**Endpoints:**

#### `POST /api/ingest/upload` - Upload a PDF
```python
# Upload: Boss_DS-1_manual.pdf
# Pedal name extracted: "Boss DS-1"
# Namespace generated: "manual_boss_ds_1"
# Processing automatically triggered
```

#### `GET /api/ingest/status/{manual_id}` - Check progress
```json
{
    "manual_id": "manual_abc123",
    "status": "in_progress",
    "progress": 60.0,
    "chunks_processed": 0,
    "total_chunks": 87
}
```

#### `GET /api/ingest/manuals` - List all manuals
```json
{
    "manuals": [
        {"pedal_name": "Boss DS-1", "status": "completed", "chunk_count": 87},
        {"pedal_name": "Helix", "status": "processing", "chunk_count": 0}
    ],
    "total": 2
}
```

---

## How It All Connects

### Flow 1: Uploading a Manual

```
┌────────────────────────────────────────────────────────────────────────┐
│                         UPLOAD FLOW                                    │
├────────────────────────────────────────────────────────────────────────┤
│                                                                        │
│   User                                                                 │
│     │                                                                  │
│     ▼                                                                  │
│   POST /api/ingest/upload                                              │
│   (with PDF file)                                                      │
│     │                                                                  │
│     ▼                                                                  │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ ingest.py                                                       │   │
│  │  1. Validate PDF (is it a PDF? Size OK?)                        │   │
│  │  2. Extract pedal name from filename                            │   │
│  │  3. Save file to uploads_dir/                                   │   │
│  │  4. Create ManualDocument in MongoDB (status=pending)           │   │
│  │  5. Send "ingest_manual" task to Redis queue                    │   │
│  │  6. Return immediately with manual_id                           │   │
│  └───────────────────────────┬─────────────────────────────────────┘   │
│                              │                                         │
│                              ▼                                         │
│                         Redis Queue                                    │
│                              │                                         │
│                              ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ ingest_worker.py (Celery Worker)                                │   │
│  │  1. Get manual from MongoDB                                     │   │
│  │  2. Process PDF (extract text, detect sections)          → 30%  │   │
│  │  3. Generate embeddings via VoyageAI                      → 60%  │   │
│  │  4. Upsert vectors to Pinecone                            → 90%  │   │
│  │  5. Update manual status = completed                      → 100% │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                        │
│                              ▼                                         │
│                    Manual is now queryable!                            │
│                                                                        │
└────────────────────────────────────────────────────────────────────────┘
```

---

### Flow 2: Asking a Question

```
┌────────────────────────────────────────────────────────────────────────┐
│                          QUERY FLOW                                    │
├────────────────────────────────────────────────────────────────────────┤
│                                                                        │
│   User: "What's the input impedance of the Boss DS-1?"                 │
│     │                                                                  │
│     ▼                                                                  │
│   POST /api/query/                                                     │
│   {"query": "...", "pedal_name": "Boss DS-1"}                          │
│     │                                                                  │
│     ▼                                                                  │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ query.py                                                        │   │
│  │  1. Generate user_id and conversation_id                        │   │
│  │  2. Create AgentState with query                                │   │
│  │  3. Call graph.run(state)                                       │   │
│  └───────────────────────────┬─────────────────────────────────────┘   │
│                              │                                         │
│                              ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ graph.py (LangGraph Workflow)                                   │   │
│  │                                                                 │   │
│  │  ┌──────────────┐                                               │   │
│  │  │ Router Agent │ → intent = MANUAL_QUESTION                    │   │
│  │  └──────┬───────┘                                               │   │
│  │         │                                                       │   │
│  │         ▼                                                       │   │
│  │  ┌──────────────┐                                               │   │
│  │  │ Manual Agent │                                               │   │
│  │  │  1. Resolve namespace (pedal_registry)                       │   │
│  │  │  2. Embed query (embeddings.py)                              │   │
│  │  │  3. Search Pinecone (pinecone_client.py)                     │   │
│  │  │  4. Generate answer with context                             │   │
│  │  └──────┬───────┘                                               │   │
│  │         │                                                       │   │
│  │         ▼                                                       │   │
│  │  ┌──────────────┐                                               │   │
│  │  │Quality Check │ → hallucination_flag = false, confidence = 0.9│   │
│  │  └──────┬───────┘                                               │   │
│  │         │                                                       │   │
│  │         ▼                                                       │   │
│  │  ┌──────────────┐                                               │   │
│  │  │ Synthesizer  │ → final_answer = raw_answer                   │   │
│  │  └──────────────┘                                               │   │
│  │                                                                 │   │
│  └───────────────────────────┬─────────────────────────────────────┘   │
│                              │                                         │
│                              ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ query.py                                                        │   │
│  │  1. Save conversation to MongoDB                                │   │
│  │  2. Save answer for analytics                                   │   │
│  │  3. Return QueryResponse                                        │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                        │
│   Response:                                                            │
│   {                                                                    │
│     "answer": "The input impedance is 1MΩ...",                         │
│     "confidence": 0.92,                                                │
│     "agent_path": ["router", "manual_agent", "quality_check", ...]     │
│   }                                                                    │
│                                                                        │
└────────────────────────────────────────────────────────────────────────┘
```

---

## Summary: The Mental Model

Think of PedalBot as a **well-organized office**:

| Role | File(s) | Job |
|------|---------|-----|
| **Receptionist** | `main.py`, `routers/*.py` | Accepts requests, routes them |
| **Filing Cabinet** | `mongodb.py`, `models.py` | Stores records (users, manuals, jobs) |
| **Memory Bank** | `pinecone_client.py` | Stores and retrieves knowledge |
| **Translator** | `embeddings.py` | Converts text to numbers |
| **Document Processor** | `pdf_processor.py` | Reads and organizes manuals |
| **Manager** | `graph.py` | Coordinates the team |
| **Specialists** | `*_agent.py` | Each expert at one thing |
| **Quality Inspector** | `quality_check.py` | Catches mistakes |
| **Background Staff** | `workers/*.py` | Handles slow tasks offline |
| **Address Book** | `pedal_registry.py` | Knows who's who |

**The key insight:**  
Data flows through `AgentState`. Each agent reads from it, does its work, and writes back. The `graph.py` orchestrator decides the order.
