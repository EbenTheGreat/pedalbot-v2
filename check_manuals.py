
import asyncio
import os
from backend.config.config import settings
from backend.db.mongodb import MongoDB

async def list_manuals():
    await MongoDB.connect(
        uri=settings.MONGODB_URI,
        db_name=settings.MONGODB_DB_NAME
    )
    
    try:
        db = MongoDB.get_database()
        cursor = db.manuals.find({})
        docs = await cursor.to_list(length=100)
        
        print(f"Found {len(docs)} manuals:")
        for doc in docs:
            print(f"- {doc.get('pedal_name')} (Status: {doc.get('status')})")
            print(f"  Namespace: {doc.get('pinecone_namespace')}")
            
    finally:
        await MongoDB.close()

if __name__ == "__main__":
    asyncio.run(list_manuals())
