"""
Quick test to verify MongoDB connection.

This will test if the MongoDB Atlas cluster is accessible.
"""

import asyncio
from backend.db.mongodb import MongoDB
from backend.config.config import settings


async def test_mongodb_connection():
    """Test MongoDB connection."""
    print("\n🔍 Testing MongoDB Connection\n")
    print("=" * 50)
    
    print(f"\n📋 Connection Details:")
    print(f"   URI: {settings.MONGODB_URI[:50]}...")  # Show first 50 chars
    print(f"   Database: {settings.MONGODB_DB_NAME}")
    
    try:
        print("\n🔌 Attempting to connect...")
        await MongoDB.connect(
            uri=settings.MONGODB_URI,
            db_name=settings.MONGODB_DB_NAME
        )
        
        print("✅ Connection successful!")
        
        # Try to ping the database
        db = MongoDB.get_database()
        print(f"\n📊 Database: {db.name}")
        
        # List collections
        collections = await db.list_collection_names()
        print(f"\n📁 Collections ({len(collections)}):")
        for coll in collections:
            count = await db[coll].count_documents({})
            print(f"   • {coll}: {count} documents")
        
        print("\n✅ MongoDB is working correctly!")
        
    except Exception as e:
        print(f"\n❌ Connection failed!")
        print(f"\nError: {type(e).__name__}")
        print(f"Message: {str(e)}")
        
        print("\n🔧 Troubleshooting:")
        print("   1. Check if MongoDB Atlas cluster is running")
        print("   2. Verify connection string in .env")
        print("   3. Check network/firewall settings")
        print("   4. Ensure IP whitelist includes your IP")
        
        return False
    
    finally:
        await MongoDB.close()
    
    return True


if __name__ == "__main__":
    success = asyncio.run(test_mongodb_connection())
    exit(0 if success else 1)
