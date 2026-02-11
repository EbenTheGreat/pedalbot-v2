import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import certifi
import os
import sys

# Ensure we can import backend
sys.path.append(os.getcwd())

from backend.config.config import settings

async def test():
    uri = settings.MONGODB_URI
    print("Testing connection with certifi...")
    print(f"URI: {uri[:50]}...")
    
    try:
        client = AsyncIOMotorClient(
            uri,
            tlsCAFile=certifi.where(),
            tls=True,
            serverSelectionTimeoutMS=10000
        )
        print("Ping command sending...")
        await client.admin.command('ping')
        print("SUCCESS! Connected with certifi.")
        
    except Exception as e:
        print(f"FAILED with certifi: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    asyncio.run(test())
