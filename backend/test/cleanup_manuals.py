"""
Clean up duplicate manual entries with null manual_id.

This script removes any manual documents that have a null manual_id field,
which can cause duplicate key errors due to the unique index.

Run: uv run python -m backend.test.cleanup_manuals
"""

from backend.db.mongodb import MongoDB, get_database
from backend.config.config import settings
import asyncio


async def cleanup_null_manual_ids():
    """Remove manual documents with null manual_id or pinecone_namespace."""
    print("\n🧹 Cleaning up manual entries with null fields...\n")
    
    # Initialize MongoDB connection
    await MongoDB.connect(uri=settings.MONGODB_URI, db_name=settings.MONGODB_DB_NAME)
    db = await get_database()
    
    # Find documents with null manual_id
    null_manual_ids = await db.manuals.count_documents({"manual_id": None})
    print(f"Found {null_manual_ids} manual(s) with null manual_id")
    
    # Find documents with null pinecone_namespace
    null_namespaces = await db.manuals.count_documents({"pinecone_namespace": None})
    print(f"Found {null_namespaces} manual(s) with null pinecone_namespace")
    
    # Delete documents with null manual_id OR null pinecone_namespace
    total_to_delete = await db.manuals.count_documents({
        "$or": [
            {"manual_id": None},
            {"pinecone_namespace": None}
        ]
    })
    
    if total_to_delete > 0:
        result = await db.manuals.delete_many({
            "$or": [
                {"manual_id": None},
                {"pinecone_namespace": None}
            ]
        })
        print(f"✓ Deleted {result.deleted_count} manual(s) with null fields")
    else:
        print("✓ No cleanup needed")
    
    # Also show all remaining manuals
    print("\n📋 Remaining manuals:")
    async for manual in db.manuals.find():
        print(f"   • {manual.get('pedal_name', 'Unknown')} (ID: {manual.get('manual_id', 'N/A')})")
    
    # Close connection
    await MongoDB.close()
    print("\n✅ Cleanup complete!\n")


if __name__ == "__main__":
    asyncio.run(cleanup_null_manual_ids())
