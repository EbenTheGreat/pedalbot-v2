"""
Script to clear MongoDB and Pinecone databases.

WARNING: This will delete ALL data. Use with caution.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Load environment variables from .env file (simple parser, no dependencies needed)
env_path = os.path.join(os.path.dirname(__file__), '../../.env')
if os.path.exists(env_path):
    with open(env_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ[key.strip()] = value.strip()
    print(f"[INFO] Loaded environment from: {env_path}")
else:
    print(f"[WARNING] .env file not found at: {env_path}")

from pymongo import MongoClient
from pinecone import Pinecone
import asyncio


def clear_mongodb():
    """Clear all collections in MongoDB."""
    print("\n" + "="*80)
    print("CLEARING MONGODB")
    print("="*80)
    
    # Connect to MongoDB
    mongo_uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017/pedalbot_db")
    client = MongoClient(mongo_uri)
    db = client.get_database()
    
    # List all collections
    collections = db.list_collection_names()
    print(f"\nFound {len(collections)} collections:")
    for coll in collections:
        print(f"  - {coll}")
    
    # Ask for confirmation
    response = input("\n⚠️  Delete ALL collections? (yes/no): ")
    if response.lower() != 'yes':
        print("❌ MongoDB clear cancelled")
        return
    
    # Delete all collections
    deleted_count = 0
    for collection_name in collections:
        result = db[collection_name].delete_many({})
        print(f"✓ Deleted {result.deleted_count} documents from '{collection_name}'")
        deleted_count += result.deleted_count
    
    print(f"\n✅ MongoDB cleared: {deleted_count} total documents deleted")
    client.close()


def clear_pinecone():
    """Clear all namespaces in Pinecone index."""
    print("\n" + "="*80)
    print("CLEARING PINECONE")
    print("="*80)
    
    # Get credentials
    api_key = os.getenv("PINECONE_API_KEY")
    index_name = os.getenv("PINECONE_INDEX_NAME", "pedalbot-manuals")
    
    if not api_key:
        print("❌ PINECONE_API_KEY not found in environment")
        return
    
    print(f"\nConnecting to Pinecone index: {index_name}")
    
    try:
        pc = Pinecone(api_key=api_key)
        index = pc.Index(index_name)
        
        # Get index stats to see namespaces
        stats = index.describe_index_stats()
        namespaces = stats.get('namespaces', {})
        
        if not namespaces:
            print("ℹ️  No namespaces found in index")
            return
        
        print(f"\nFound {len(namespaces)} namespaces:")
        for ns_name, ns_stats in namespaces.items():
            vector_count = ns_stats.get('vector_count', 0)
            print(f"  - {ns_name}: {vector_count} vectors")
        
        # Ask for confirmation
        response = input("\n⚠️  Delete ALL vectors from ALL namespaces? (yes/no): ")
        if response.lower() != 'yes':
            print("❌ Pinecone clear cancelled")
            return
        
        # Delete all vectors from each namespace
        total_deleted = 0
        for ns_name in namespaces.keys():
            print(f"\nDeleting all vectors from namespace: {ns_name}")
            index.delete(delete_all=True, namespace=ns_name)
            vector_count = namespaces[ns_name].get('vector_count', 0)
            total_deleted += vector_count
            print(f"✓ Deleted ~{vector_count} vectors from '{ns_name}'")
        
        print(f"\n✅ Pinecone cleared: ~{total_deleted} total vectors deleted")
        
    except Exception as e:
        print(f"❌ Error clearing Pinecone: {e}")


def main():
    """Main function."""
    print("\n" + "="*80)
    print("DATABASE CLEAR UTILITY")
    print("="*80)
    print("\n⚠️  WARNING: This will permanently delete ALL data from:")
    print("  1. MongoDB (all collections)")
    print("  2. Pinecone (all vectors in all namespaces)")
    print("\nThis action CANNOT be undone!")
    
    response = input("\nDo you want to proceed? (yes/no): ")
    if response.lower() != 'yes':
        print("\n❌ Operation cancelled")
        return
    
    # Clear databases
    clear_mongodb()
    clear_pinecone()
    
    print("\n" + "="*80)
    print("✅ DATABASE CLEAR COMPLETE")
    print("="*80)


if __name__ == "__main__":
    main()
