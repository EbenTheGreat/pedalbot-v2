# PedalBot API Quick Reference

## 🚀 Simplified Workflow

### 1. Upload a PDF (Auto-ingests)
**One call does it all!** Just upload the PDF and it automatically starts processing.

```bash
POST /api/ingest/upload
```

**Example (Swagger UI):**
1. Go to `http://localhost:8000/docs`
2. Click on `POST /api/ingest/upload`
3. Click "Try it out"
4. Choose your PDF file
5. Click "Execute"

**Response:**
```json
{
  "manual_id": "manual_9908b8c1c300",
  "pedal_name": "Boss DS-1",
  "pinecone_namespace": "manual_boss_ds_1",
  "status": "processing",
  "message": "✅ Manual uploaded and auto-ingestion started! Check /status/manual_9908b8c1c300 for progress."
}
```

---

### 2. Check Status
```bash
GET /api/ingest/status/{manual_id}
```

**Example:**
```
http://localhost:8000/api/ingest/status/manual_9908b8c1c300
```

**Response:**
```json
{
  "manual_id": "manual_9908b8c1c300",
  "status": "completed",
  "progress": 100.0,
  "chunks_processed": 87,
  "total_cunks": 87,
  "error": null,
  "started_at": "2026-01-16T12:00:00Z",
  "completed_at": "2026-01-16T12:02:34Z"
}
```

---

### 3. List All Manuals
```bash
GET /api/ingest/manuals
```

**Example:**
```
http://localhost:8000/api/ingest/manuals
```

**Optional filter by status:**
```
http://localhost:8000/api/ingest/manuals?status=completed
```

**Response:**
```json
{
  "manuals": [
    {
      "manual_id": "manual_9908b8c1c300",
      "pedal_name": "Boss DS-1",
      "manufacturer": null,
      "status": "completed",
      "chunk_count": 87,
      "file_size_bytes": 2456789,
      "uploaded_at": "2026-01-16T12:00:00Z",
      "indexed_at": "2026-01-16T12:02:34Z"
    }
  ],
  "total": 1
}
```

---

## 📋 Complete API Endpoints

### Ingestion
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/ingest/upload` | Upload PDF (auto-starts ingestion) |
| `GET` | `/api/ingest/status/{manual_id}` | Check ingestion progress |
| `GET` | `/api/ingest/manuals` | List all manuals |
| `GET` | `/api/ingest/manuals?status=completed` | Filter by status |

### Query (Agent) - Simplified API! 🎉
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/query/pedals` | **List available pedals** (call this first!) |
| `POST` | `/api/query/` | Ask a question to PedalBot |
| `POST` | `/api/query/stream` | Ask with streaming response |
| `GET` | `/api/query/conversations/{id}` | Get conversation history |

**Smart Defaults:**
- ✅ `user_id`: Auto-generated (no need to provide!)
- ✅ `conversation_id`: Auto-generated for new conversations
- ✅ `pedal_name`: Required for first message, inherited for follow-ups

---

## 🎯 Typical Workflow

```bash
# 1. Upload PDF
curl -X POST "http://localhost:8000/api/ingest/upload" \
  -F "pdf_file=@Boss_DS-1_manual.pdf"

# 2. Wait a few seconds, then check status
curl "http://localhost:8000/api/ingest/status/manual_9908b8c1c300"

# 3. List available pedals (NEW!)
curl "http://localhost:8000/api/query/pedals"

# 4. Query the agent (simplified - no user_id needed!)
curl -X POST "http://localhost:8000/api/query/" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is the input impedance?",
    "pedal_name": "Boss DS-1"
  }'

# Response includes conversation_id for follow-ups:
# {
#   "answer": "The input impedance is...",
#   "conversation_id": "conv_abc123def456",
#   "user_id": "anon_xyz789",
#   "pedal_name": "Boss DS-1",
#   ...
# }

# 5. Follow-up question (pedal_name inherited from conversation!)
curl -X POST "http://localhost:8000/api/query/" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What about the output impedance?",
    "conversation_id": "conv_abc123def456"
  }'

# 6. List all manuals anytime
curl "http://localhost:8000/api/ingest/manuals"
```

---

## 🔧 Running the Server

```bash
# Start server (no workers on Windows!)
uv run uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

# Or use your alias for Docker
docker-rebuild
```

---

## 📊 Status Values

- `pending` - Uploaded but not started
- `processing` - Currently being ingested
- `completed` - Successfully indexed to Pinecone
- `failed` - Error occurred (check error field)
