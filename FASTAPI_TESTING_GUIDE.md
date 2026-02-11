# PedalBot FastAPI Testing Guide

Complete guide to testing the full PedalBot system via FastAPI endpoints.

---

## 📋 Prerequisites

### 1. Verify Services are Running
```bash
docker-compose ps
```

**Expected output:**
- ✅ `pedalbot-redis` - Healthy
- ✅ `pedalbot-mongodb` - Running
- ✅ `pedalbot-celery-worker` - Running
- ✅ `pedalbot-celery-beat` - Running
- ✅ `pedalbot-flower` - Running

### 2. Check Environment Variables
Ensure your `.env` file has:
```bash
# Required for testing
GROQ_API_KEY=...
VOYAGEAI_API_KEY=...
PINECONE_API_KEY=...
REVERB_API_KEY=...
GOOGLE_API_KEY=...
LANGSMITH_API_KEY=...
LANGSMITH_TRACING=true
```

### 3. Verify Test PDFs
Check that you have PDFs in `uploads_dir/`:
```bash
ls uploads_dir/
```

---

## 🚀 Step 1: Start FastAPI Server

### Option A: Development Mode (Recommended)
```bash
uv run uvicorn backend.main:app --reload --port 8000
```

### Option B: Production Mode
```bash
docker-compose ps
```

**Verify it's running:**
- Open browser: http://localhost:8000/docs
- You should see the **Swagger UI** with all endpoints

---

## 🧪 Step 2: Test Manual Upload & Ingestion

### 2.1 Upload a PDF Manual

**Using cURL:**
```bash
curl -X POST "http://localhost:8000/api/manuals/upload" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@uploads_dir/GT-1_eng03_W.pdf" \
  -F "pedal_name=Boss GT-1" \
  -F "manufacturer=Boss"
```

**Using Python (httpx):**
```python
import httpx

with open("uploads_dir/GT-1_eng03_W.pdf", "rb") as f:
    response = httpx.post(
        "http://localhost:8000/api/manuals/upload",
        files={"file": ("GT-1_eng03_W.pdf", f, "application/pdf")},
        data={
            "pedal_name": "Boss GT-1",
            "manufacturer": "Boss"
        }
    )
    
print(response.json())
```

**Expected Response:**
```json
{
  "manual_id": "abc123...",
  "pedal_name": "Boss GT-1",
  "status": "pending",
  "message": "Manual uploaded successfully. Processing started."
}
```

**Save the `manual_id` - you'll need it!**

---

### 2.2 Monitor Ingestion Progress

#### Option 1: Flower Dashboard (Visual)
1. Open: http://localhost:5555
2. Go to **Tasks** tab
3. Find task with name `ingest_manual`
4. Click on the task ID to see details

**What to look for:**
- ✅ State: `SUCCESS`
- ✅ Result contains: `chunks`, `tokens`, `cost_usd`
- ❌ If `FAILURE`: Check the traceback

#### Option 2: Check Manual Status (API)
```bash
curl http://localhost:8000/api/manuals/{manual_id}
```

**Expected progression:**
1. `status: "pending"` → Just uploaded
2. `status: "processing"` → Celery worker is running
3. `status: "completed"` → ✅ Ready for queries!
4. `status: "failed"` → ❌ Check logs

#### Option 3: Worker Logs
```bash
docker logs -f pedalbot-celery-worker
```

**Look for:**
```
INFO:backend.workers.ingest_worker:Starting ingestion for manual: abc123...
INFO:backend.services.embeddings: Generated 14 embeddings...
INFO:backend.services.pinecone_client:Upserted batch 1: 14 vectors...
INFO:backend.workers.ingest_worker:✅ Ingestion complete
```

---

### 2.3 Verify Vectors in Pinecone

**Quick check:**
```bash
uv run python -c "
from backend.services.pinecone_client import PineconeClient
from backend.config.config import settings

pc = PineconeClient(settings.PINECONE_API_KEY, settings.PINECONE_INDEX_NAME)
stats = pc.get_namespace_stats('manual_YOUR_MANUAL_ID_HERE')
print(f'Vectors uploaded: {stats[\"vector_count\"]}')
"
```

**Expected:** `vector_count > 0` (e.g., 14, 50, 100+ depending on PDF size)

---

## 💬 Step 3: Test Agent Chat Queries

### 3.1 Ask a Manual Question

**Using cURL:**
```bash
curl -X POST "http://localhost:8000/api/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is the input impedance of the Boss GT-1?",
    "pedal_name": "Boss GT-1",
    "user_id": "test_user"
  }'
```

**Using Python:**
```python
import httpx

response = httpx.post(
    "http://localhost:8000/api/chat",
    json={
        "query": "What is the input impedance of the Boss GT-1?",
        "pedal_name": "Boss GT-1",
        "user_id": "test_user"
    }
)

result = response.json()
print(f"Intent: {result['intent']}")
print(f"Answer: {result['answer']}")
print(f"Confidence: {result['confidence']}")
```

**Expected Response:**
```json
{
  "answer": "The Boss GT-1 has an input impedance of 1 MΩ...",
  "intent": "manual_question",
  "confidence": 0.92,
  "agent_path": ["router", "manual_agent", "quality_check", "synthesizer"],
  "hallucination_flag": false,
  "retrieved_chunks": [...],
  "conversation_id": "conv_abc123"
}
```

---

### 3.2 Ask a Pricing Question

```bash
curl -X POST "http://localhost:8000/api/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "How much does a used Boss GT-1 cost?",
    "pedal_name": "Boss GT-1",
    "user_id": "test_user"
  }'
```

**Expected Response:**
```json
{
  "answer": "Based on 50 active listings on Reverb, the Boss GT-1 currently sells for an average of $249.99...",
  "intent": "pricing",
  "price_info": {
    "avg_price": 249.99,
    "min_price": 180.00,
    "max_price": 350.00,
    "total_listings": 50
  },
  "agent_path": ["router", "pricing_agent", "quality_check", "synthesizer"]
}
```

---

### 3.3 Test Hybrid Query (Manual + Pricing)

```bash
curl -X POST "http://localhost:8000/api/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Is the Boss GT-1 worth $300 given its features?",
    "pedal_name": "Boss GT-1",
    "user_id": "test_user"
  }'
```

**Expected:**
- Intent: `hybrid`
- Agent path includes both `manual_agent` and `pricing_agent`

---

## 📊 Step 4: Monitor in LangSmith

### 4.1 Access LangSmith Dashboard
1. Go to: https://smith.langchain.com/
2. Select project: **pedalbot** (from your `.env`)
3. View recent traces

### 4.2 What to Check
- ✅ **Trace appears** for each query
- ✅ **Agent path** matches expected flow
- ✅ **Latency** is reasonable (<5s for most queries)
- ✅ **Token usage** is tracked
- ✅ **No errors** in trace

### 4.3 Analyze a Trace
Click on a trace to see:
- Router decision (intent classification)
- Pinecone search results (similarity scores)
- LLM prompts and responses
- Quality check validation
- Total cost and latency

---

## 🔍 Step 5: Advanced Testing

### 5.1 Test Conversation Context

**First message:**
```bash
curl -X POST "http://localhost:8000/api/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What effects does the Boss GT-1 have?",
    "pedal_name": "Boss GT-1",
    "user_id": "test_user"
  }'
```

**Follow-up (using same conversation_id):**
```bash
curl -X POST "http://localhost:8000/api/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "How do I save a preset?",
    "pedal_name": "Boss GT-1",
    "user_id": "test_user",
    "conversation_id": "conv_abc123"  # From first response
  }'
```

**Expected:** Agent understands context from previous message.

---

### 5.2 Test Quality Check (Hallucination Detection)

**Ask an unanswerable question:**
```bash
curl -X POST "http://localhost:8000/api/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Can the Boss GT-1 make coffee?",
    "pedal_name": "Boss GT-1",
    "user_id": "test_user"
  }'
```

**Expected:**
```json
{
  "answer": "I don't have that information in the manual.",
  "hallucination_flag": true,
  "confidence": 0.0,
  "agent_path": ["router", "manual_agent", "quality_check", "fallback"]
}
```

---

### 5.3 Bulk Testing Script

Create `test_bulk_queries.py`:
```python
import httpx
import asyncio

queries = [
    "What is the input impedance?",
    "How much does it cost?",
    "What effects does it have?",
    "How do I connect it to my amp?",
    "Is it true bypass?"
]

async def test_query(query: str):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/api/chat",
            json={
                "query": query,
                "pedal_name": "Boss GT-1",
                "user_id": "bulk_test"
            }
        )
        result = response.json()
        print(f"\n{'='*60}")
        print(f"Q: {query}")
        print(f"Intent: {result['intent']}")
        print(f"A: {result['answer'][:150]}...")
        print(f"Confidence: {result['confidence']:.2f}")

async def main():
    for query in queries:
        await test_query(query)
        await asyncio.sleep(1)  # Rate limiting

asyncio.run(main())
```

**Run:**
```bash
uv run python test_bulk_queries.py
```

---

## 🐛 Troubleshooting

### Issue: Manual upload returns 500 error
**Check:**
1. File size < 100MB (see `MAX_UPLOAD_SIZE_MB` in `.env`)
2. File is a valid PDF
3. Celery worker is running: `docker ps | grep celery-worker`

**Fix:**
```bash
docker-compose restart celery-worker
```

---

### Issue: Ingestion stuck in "processing"
**Check Celery logs:**
```bash
docker logs pedalbot-celery-worker --tail 50
```

**Common causes:**
- Google Vision API quota exceeded
- Pinecone API error
- MongoDB connection lost

**Fix:**
```bash
# Restart worker
docker-compose restart celery-worker

# Check task in Flower
# http://localhost:5555
```

---

### Issue: Agent returns "No manual found"
**Verify manual status:**
```bash
curl http://localhost:8000/api/manuals/{manual_id}
```

**Check:**
- `status` is `"completed"` (not `"pending"` or `"failed"`)
- `pinecone_namespace` is set
- `chunk_count > 0`

**Fix:**
Re-upload the manual if status is `"failed"`.

---

### Issue: Pricing returns stale data
**Clear cache:**
```bash
uv run python -c "
from backend.db.mongodb import MongoDB
from backend.config.config import settings
import asyncio

async def clear():
    await MongoDB.connect(settings.MONGODB_URI, settings.MONGODB_DB_NAME)
    db = MongoDB.get_database()
    await db.pricing.delete_many({})
    print('✅ Pricing cache cleared')
    await MongoDB.close()

asyncio.run(clear())
"
```

---

### Issue: LangSmith traces not appearing
**Check `.env`:**
```bash
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=lsv2_...
LANGSMITH_PROJECT=pedalbot
```

**Restart server:**
```bash
# Kill uvicorn (Ctrl+C)
# Restart
uv run uvicorn backend.main:app --reload --port 8000
```

---

## ✅ Success Criteria

Your system is **fully functional** if:

1. ✅ Manual uploads successfully
2. ✅ Ingestion completes with `status: "completed"`
3. ✅ Vectors appear in Pinecone (`vector_count > 0`)
4. ✅ Manual questions return relevant answers
5. ✅ Pricing questions return current market data
6. ✅ Quality check rejects hallucinations
7. ✅ LangSmith traces appear for all queries
8. ✅ Flower shows all tasks as `SUCCESS`

---

## 📚 Additional Resources

- **API Documentation:** http://localhost:8000/docs
- **Flower Dashboard:** http://localhost:5555
- **LangSmith:** https://smith.langchain.com/
- **Pinecone Console:** https://app.pinecone.io/

---

## 🎯 Next Steps After Testing

1. **Production Deployment:**
   - Set up S3 for PDF storage
   - Configure custom email domain in Resend
   - Deploy to cloud (AWS, GCP, Azure)

2. **Feature Enhancements:**
   - Add user authentication (JWT)
   - Implement rate limiting
   - Add caching layer (Redis)
   - Build frontend UI

3. **Monitoring:**
   - Set up error tracking (Sentry)
   - Add performance monitoring (DataDog, New Relic)
   - Configure alerts for failed tasks

---

**Happy Testing! 🚀**
