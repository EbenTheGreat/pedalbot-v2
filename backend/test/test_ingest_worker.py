"""
Test PDF ingestion worker.

This tests the manual upload and processing pipeline:
1. Upload PDF
2. OCR text extraction
3. Chunking
4. Embedding generation
5. Pinecone storage
6. Email notification

Run: uv run python -m backend.test.test_ingest_worker
"""

from backend.workers.ingest_worker import process_manual_task
from backend.config.config import settings
import asyncio
from backend.db.mongodb import get_database, MongoDB
import uuid


async def create_test_manual():
    """Create a test manual entry in MongoDB."""
    # Initialize MongoDB connection
    await MongoDB.connect(uri=settings.MONGODB_URI, db_name=settings.MONGODB_DB_NAME)
    db = await get_database()
    
    # Generate unique manual_id
    manual_id = str(uuid.uuid4())
    
    # Create a test manual document
    manual = {
        "manual_id": manual_id,
        "pedal_name": "Boss DS-1 Distortion",
        "manufacturer": "Boss",
        "pdf_url": "./uploads_dir/GT-1_eng03_W.pdf",  # Using existing PDF from uploads_dir
        "uploaded_by": "test_user@example.com",
        "status": "pending",
        "created_at": "2026-01-06T15:30:00Z",
        "pinecone_namespace": f"manual_{manual_id}"  # Unique namespace for Pinecone
    }
    
    result = await db.manuals.insert_one(manual)
    
    print(f"✓ Created test manual: {manual_id}")
    return manual_id


async def test_ingestion():
    """Test the ingestion worker."""
    print("\n🧪 Testing PDF Ingestion Worker\n")
    print("=" * 50)
    
    # Step 1: Create test manual in MongoDB
    print("\n1️⃣ Creating test manual entry...")
    manual_id = await create_test_manual()
    
    # Step 2: Queue ingestion task
    print("\n2️⃣ Queuing ingestion task...")
    result = process_manual_task.delay(manual_id)
    print(f"✓ Task queued: {result.id}")
    
    print("\n" + "=" * 50)
    print("\n📊 Monitor progress:")
    print(f"   • Flower: http://localhost:5555/task/{result.id}")
    print("   • Logs: docker-compose logs -f celery-worker")
    
    print("\n⏳ Expected processing time: 1-5 minutes")
    print("   (depends on PDF size and OCR complexity)")
    
    print("\n✅ What to check:")
    print("   1. Task shows 'SUCCESS' in Flower")
    print("   2. Chunks created in Pinecone")
    print("   3. Manual status updated to 'completed'")
    print("   4. Email notification sent (if configured)")
    
    print("\n💡 Note: You need a test PDF at ./test_data/sample_manual.pdf")
    print("   Or update the file_path in this test to an existing PDF.\n")


if __name__ == "__main__":
    print("\n⚠️  IMPORTANT: This test requires:")
    print("   1. A test PDF file (pedal manual)")
    print("   2. Google Vision API credentials (for OCR)")
    print("   3. Pinecone API key (for vector storage)")
    print("   4. VoyageAI API key (for embeddings)")
    print("\n   Make sure these are configured in your .env file!\n")
    
    print("   Make sure these are configured in your .env file!\n")
    
    # Auto-run with existing PDF
    import os
    if os.path.exists("./uploads_dir/GT-1_eng03_W.pdf"):
        asyncio.run(test_ingestion())
    else:
        print("❌ Error: ./uploads_dir/GT-1_eng03_W.pdf not found.")
