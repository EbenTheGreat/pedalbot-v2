"""
MongoDB client with async connection pooling and health checks.

Usage:
    from app.db.mongodb import get_database, init_db, close_db
    
    # On app startup 
    await init_db()
    
    # In route handlers
    db = await get_database()
    await db.users.find_one({"user_id": "123"})
    
    # On app shutdown
    await close_db()
"""

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
from typing import Optional
import logging
from contextlib import asynccontextmanager
import ssl
import certifi

logger = logging.getLogger(__name__)


class MongoDB:
    """Singleton MongoDB client manager."""
    
    client: Optional[AsyncIOMotorClient] = None
    db: Optional[AsyncIOMotorDatabase] = None
    
    @classmethod
    async def connect(
        cls,
        uri: str,
        db_name: str,
        max_pool_size: int = 10,
        min_pool_size: int = 1,
        server_selection_timeout_ms: int = 5000,
    ) -> None:
        """
        Initialize MongoDB connection with pooling.
        
        Args:
            uri: MongoDB connection string (mongodb://... or mongodb+srv://...)
            db_name: Database name (e.g., "pedalbot_prod")
            max_pool_size: Max connections in pool
            min_pool_size: Min idle connections
            server_selection_timeout_ms: Timeout for server selection
        """
        try:
            if not uri or len(uri.strip()) == 0:
                raise ValueError("MongoDB URI is empty! Check your MONGODB_URI environment variable.")
            
            # DEBUG: Print the actual URI being used
            print(f"[DEBUG] MONGODB URI BEING USED: {uri[:10]}... (len={len(uri)})")
            
            # Detect if this is a local MongoDB (no SSL needed)
            is_local = "localhost" in uri or "127.0.0.1" in uri or "mongodb://" in uri and "mongodb.net" not in uri
            
            if is_local:
                # Local MongoDB - no SSL
                cls.client = AsyncIOMotorClient(
                    uri,
                    maxPoolSize=max_pool_size,
                    minPoolSize=min_pool_size,
                    serverSelectionTimeoutMS=server_selection_timeout_ms,
                    retryWrites=True,
                    retryReads=True,
                )
            else:
                # Remote MongoDB (Atlas) - needs SSL
                cls.client = AsyncIOMotorClient(
                    uri,
                    maxPoolSize=max_pool_size,
                    minPoolSize=min_pool_size,
                    serverSelectionTimeoutMS=server_selection_timeout_ms,
                    retryWrites=True,
                    retryReads=True,
                    tls=True,
                    tlsAllowInvalidCertificates=True,
                )

            
            # Test connection
            await cls.client.admin.command("ping")
            cls.db = cls.client[db_name]
            
            # Create indexes on startup
            await cls._create_indexes()
            
            logger.info(f"MongoDB connected: {db_name}")
            
        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            logger.error(f"MongoDB connection failed: {e}")
            raise
    
    @classmethod
    async def _create_indexes(cls) -> None:
        """Create indexes for optimal query performance."""
        
        if cls.db is None:
            logger.warning("Cannot create indexes: database not initialized")
            return
        
        try:
            # Users collection
            await cls.db.users.create_index("user_id", unique=True)
            await cls.db.users.create_index("email", unique=True)
            
            # Conversations collection
            await cls.db.conversations.create_index("conversation_id", unique=True)
            await cls.db.conversations.create_index([("user_id", 1), ("started_at", -1)])
            
            # Manuals collection
            await cls.db.manuals.create_index("manual_id", unique=True)
            await cls.db.manuals.create_index("pedal_name")
            await cls.db.manuals.create_index("pinecone_namespace", unique=True)
            
            # Answers collection (for analytics)
            await cls.db.answers.create_index("answer_id", unique=True)
            await cls.db.answers.create_index([("user_id", 1), ("created_at", -1)])
            await cls.db.answers.create_index("conversation_id")
            await cls.db.answers.create_index("hallucination_flag")
            
            # Pricing collection (TTL index for 24h expiry)
            await cls.db.pricing.create_index("pedal_name", unique=True)
            await cls.db.pricing.create_index("updated_at", expireAfterSeconds=86400)  # 24 hours
            
            # Ingestion jobs
            await cls.db.ingestion_jobs.create_index("job_id", unique=True)
            await cls.db.ingestion_jobs.create_index([("status", 1), ("created_at", -1)])
            
            logger.info("MongoDB indexes created")
            
        except Exception as e:
            logger.warning(f"Index creation failed (may already exist): {e}")
    
    @classmethod
    async def close(cls) -> None:
        """Close MongoDB connection."""
        if cls.client:
            cls.client.close()
            cls.client = None
            cls.db = None
            logger.info("MongoDB connection closed")
    
    @classmethod
    async def health_check(cls) -> bool:
        """Check if MongoDB is healthy."""
        try:
            if not cls.client:
                return False
            await cls.client.admin.command("ping")
            return True
        except Exception as e:
            logger.error(f"MongoDB health check failed: {e}")
            return False
    
    @classmethod
    def get_database(cls) -> AsyncIOMotorDatabase:
        """Get the database instance."""
        if cls.db is None:
            raise RuntimeError("MongoDB not initialized. Call MongoDB.connect() first.")
        return cls.db


# Convenience functions for FastAPI dependency injection
async def init_db(uri: str, db_name: str) -> None:
    """Initialize database connection (call on app startup)."""
    await MongoDB.connect(uri, db_name)


async def close_db() -> None:
    """Close database connection (call on app shutdown)."""
    await MongoDB.close()


async def get_database() -> AsyncIOMotorDatabase:
    """
    Get database instance for dependency injection.
    
    Usage in FastAPI:
        @app.get("/health")
        async def health(db: AsyncIOMotorDatabase = Depends(get_database)):
            ...
    """
    return MongoDB.get_database()


@asynccontextmanager
async def get_db_context():
    """
    Context manager for database operations (useful in workers).
    
    Usage:
        async with get_db_context() as db:
            await db.users.insert_one({...})
    """
    try:
        yield MongoDB.get_database()
    except Exception as e:
        logger.error(f"Database operation failed: {e}")
        raise
    