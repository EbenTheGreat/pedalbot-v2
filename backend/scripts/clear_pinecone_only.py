#!/usr/bin/env python3
"""
Simple Pinecone clearing script.
Loads API key from .env and clears all namespaces.
"""

import os
import sys

# Load .env file
env_path = os.path.join(os.path.dirname(__file__), '../../.env')
if os.path.exists(env_path):
    with open(env_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ[key.strip()] = value.strip()

# Get Pinecone credentials
api_key = os.getenv("PINECONE_API_KEY")
index_name = os.getenv("PINECONE_INDEX_NAME", "pedalbot")

if not api_key:
    print("❌ PINECONE_API_KEY not found in .env file")
    sys.exit(1)

print("="*80)
print("PINECONE DATABASE CLEAR")
print("="*80)
print(f"\nAPI Key: {api_key[:10]}...{api_key[-5:]}")
print(f"Index: {index_name}")

# Import Pinecone
try:
    from pinecone import Pinecone
except ImportError:
    print("\n❌ Pinecone library not installed")
    print("Run: pip install pinecone-client")
    sys.exit(1)

# Connect
try:
    pc = Pinecone(api_key=api_key)
    index = pc.Index(index_name)
    
    # Get stats
    stats = index.describe_index_stats()
    namespaces = stats.get('namespaces', {})
    
    if not namespaces:
        print("\nℹ️  No namespaces found in index")
        sys.exit(0)
    
    print(f"\n📊 Found {len(namespaces)} namespaces:")
    for ns_name, ns_stats in namespaces.items():
        vector_count = ns_stats.get('vector_count', 0)
        print(f"  - {ns_name}: {vector_count:,} vectors")
    
    # Confirm
    print("\n⚠️  WARNING: This will DELETE ALL vectors from ALL namespaces!")
    response = input("Type 'yes' to proceed: ")
    
    if response.lower() != 'yes':
        print("❌ Cancelled")
        sys.exit(0)
    
    # Delete
    total_deleted = 0
    for ns_name, ns_stats in namespaces.items():
        vector_count = ns_stats.get('vector_count', 0)
        print(f"\n🗑️  Deleting {vector_count:,} vectors from '{ns_name}'...")
        index.delete(delete_all=True, namespace=ns_name)
        print(f"✅ Deleted from '{ns_name}'")
        total_deleted += vector_count
    
    print(f"\n{'='*80}")
    print(f"✅ SUCCESS: Deleted ~{total_deleted:,} total vectors")
    print(f"{'='*80}")
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    sys.exit(1)
