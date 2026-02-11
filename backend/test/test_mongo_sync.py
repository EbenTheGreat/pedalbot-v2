"""
Test MongoDB Atlas connection with synchronous pymongo to isolate SSL issues.
"""

from pymongo import MongoClient
from backend.config.config import settings
import ssl

try:
    print("Testing MongoDB Atlas connection with synchronous pymongo...")
    print(f"OpenSSL version: {ssl.OPENSSL_VERSION}")
    print(f"MongoDB URI: {settings.MONGODB_URI[:50]}...")
    
    # Try with tlsAllowInvalidCertificates
    client = MongoClient(
        settings.MONGODB_URI,
        tls=True,
        tlsAllowInvalidCertificates=True,
        serverSelectionTimeoutMS=10000
    )
    
    # Test connection
    client.admin.command('ping')
    print("✅ Connection successful with tlsAllowInvalidCertificates!")
    
    # List databases
    dbs = client.list_database_names()
    print(f"Available databases: {dbs}")
    
    client.close()
    
except Exception as e:
    print(f"❌ Connection failed: {e}")
    print(f"\nError type: {type(e).__name__}")
