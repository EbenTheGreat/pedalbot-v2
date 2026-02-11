# How to Clear MongoDB and Pinecone Databases

## Quick Commands

### Option 1: Using the Clear Script (Recommended)

```bash
cd /Users/solomonolakulehin/Desktop/eben/pedalbot-langgraph-main
python3 backend/scripts/clear_databases.py
```

This script will:
- Show you what will be deleted
- Ask for confirmation before deleting
- Clear both MongoDB and Pinecone

---

### Option 2: Clear MongoDB Only

```bash
# Using mongosh
mongosh pedalbot_db --eval "db.dropDatabase()"

# OR using Docker
docker exec -it pedalbot-mongodb mongosh pedalbot_db --eval "db.dropDatabase()"
```

---

### Option 3: Clear Pinecone Only

```python
# In Python
from pinecone import Pinecone
import os

pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index = pc.Index("pedalbot-manuals")

# Delete all vectors from all namespaces
stats = index.describe_index_stats()
for namespace in stats.get('namespaces', {}).keys():
    index.delete(delete_all=True, namespace=namespace)
```

---

## What Gets Deleted

### MongoDB Collections
- `conversations` - Chat histories
- `queries` - Query logs
- `pedals` - Pedal metadata
- Any other collections in the database

### Pinecone Namespaces
- All manual vectors (e.g., `manual_helix_3.80...`)
- All pedal document embeddings
- Cannot be recovered after deletion

---

## After Clearing

You'll need to re-ingest data:

1. **Re-upload manuals**:
   ```bash
   # Via API endpoint
   curl -X POST http://localhost:8000/api/ingest/upload \
     -F "file=@/path/to/manual.pdf" \
     -F "pedal_name=Your Pedal"
   ```

2. **Or use Streamlit interface**:
   - Go to http://localhost:8501
   - Navigate to "📤 Upload Manual" page
   - Upload PDFs

---

## Safety Tips

⚠️ **Before clearing**:
- Make sure you have backup copies of important manuals
- Note which pedals you had ingested
- Consider exporting critical data if needed

✅ **The clearing script will**:
- Show what will be deleted
- Ask for confirmation (type "yes")
- Can be cancelled at any step
