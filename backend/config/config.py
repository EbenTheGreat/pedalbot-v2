"""
Application configuration using Pydantic BaseSettings.

Loads from environment variables with validation.

Usage:
    from app.config import settings
    
    print(settings.MONGODB_URI)
    print(settings.OPENAI_API_KEY)
"""

from pydantic_settings import BaseSettings
from pydantic import Field, field_validator
from typing import Optional, Dict, Any
from functools import lru_cache
from dotenv import load_dotenv
import os

# CRITICAL: Load .env file explicitly before Settings initialization
# This ensures environment variables are available when Pydantic reads them
load_dotenv()


class Settings(BaseSettings):
    """Application settings from environment variables."""

    @field_validator("*", mode="before")
    @classmethod
    def strip_whitespace(cls, v: Any, info: Any) -> Any:
        """Strip whitespace and convert empty strings to None."""
        if isinstance(v, str):
            stripped = v.strip()
            return stripped if stripped else None
        return v

    model_config = {
    "env_file": ".env",
    "env_file_encoding": "utf-8",
    "case_sensitive": True,
    "validate_default": False,
    "populate_by_name": True,
    "extra": "allow",  
}


    # APPLICATION
    APP_NAME: str = "PedalBot"
    APP_VERSION: str = "0.2.0"
    ENV: str = "development"
    DEBUG: bool = True

    # API
    API_V1_PREFIX: str = "/api/v2"
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:8501"]

    # DATABASE - MongoDB
    MONGODB_URI: str = Field(default="")
    MONGODB_DB_NAME: str = "pedalbot_db"
    MONGODB_MAX_POOL_SIZE: int = 30
    MONGODB_MIN_POOL_SIZE: int = 5

    # VECTOR DATABASE - Pinecone
    PINECONE_API_KEY: str = Field(default="", alias="PINECONE_API_KEY")
    PINECONE_INDEX_NAME: str = "pedalbot"
    PINECONE_DIMENSION: int = 1024  # text-embedding-3-small
    PINECONE_METRIC: str = "cosine"
    PINECONE_CLOUD: str = "aws"
    PINECONE_REGION: str = "us-east-1"

    # LLM - Groq and VoyageAI
    GROQ_API_KEY: str = Field(default="", alias="GROQ_API_KEY")
    GROQ_ROUTER_MODEL: str= Field(default="", alias="GROQ_ROUTER_MODEL")  # Fast intent classification
    GROQ_ANSWER_MODEL: str= Field(default="", alias="GROQ_ANSWER_MODEL") # High-quality answers
    VOYAGEAI_API_KEY: str = Field(default="", alias="VOYAGEAI_API_KEY")
    VOYAGEAI_EMBEDDING_MODEL: str = "voyage-3.5-lite"
    GROQ_MAX_TOKENS: int = 1000
    GROQ_TEMPERATURE: float = 0.1  # Low temp for factual responses


    # GOOGLE CLOUD (OCR)
    GOOGLE_APPLICATION_CREDENTIALS: Optional[str] = None
    GOOGLE_OCR_ENABLED: bool = False
    GOOGLE_API_KEY: Optional[str] = None

    # GOOGLE CLOUD - Vision API (OCR)
    GOOGLE_CLOUD_PROJECT_ID: Optional[str] = None
    GOOGLE_VISION_CREDENTIALS_PATH: Optional[str] = None  # Path to service account JSON
    GOOGLE_VISION_CREDENTIALS_JSON: Optional[str] = None  # JSON string of credentials
    GOOGLE_VISION_CREDENTIALS: Optional[str] = None  # Base64-encoded service account JSON
    
    # OCR settings
    OCR_QUALITY_THRESHOLD: float = 0.3  # Auto-trigger OCR if quality < this
    OCR_DPI: int = 300  # DPI for rendering PDF pages to images
    
    @property
    def google_vision_credentials_dict(self) -> Optional[Dict[str, Any]]:
        """
        Decode base64-encoded service account credentials to dict.
        Used for Google Vision API OCR.
        """
        if self.GOOGLE_VISION_CREDENTIALS:
            import base64
            import json
            try:
                decoded = base64.b64decode(self.GOOGLE_VISION_CREDENTIALS)
                return json.loads(decoded)
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(f"Failed to decode GOOGLE_VISION_CREDENTIALS: {e}")
                return None
        return None

    # REDIS (Cache + Rate Limiting)
    REDIS_URL_ENV: Optional[str] = Field(None, alias="REDIS_URL")
    REDIS_URI: Optional[str] = None
    REDIS_TTL_SECONDS: int = 3600  # 1 hour cache
    REDIS_MAX_CONNECTIONS: int = 30

    # CELERY (Background Workers)
    CELERY_BROKER_URL: Optional[str] = None 
    CELERY_RESULT_BACKEND: Optional[str] = None

    # AWS S3 (PDF Storage)
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    AWS_S3_BUCKET: Optional[str] = None
    AWS_S3_REGION: str = "us-east-1"

    # REVERB API (Pricing Data)
    REVERB_API_KEY: Optional[str] = None
    REVERB_BASE_URL: str = "https://api.reverb.com/api"
    
    # AUTHENTICATION
    JWT_SECRET_KEY: str=Field(default="", alias="JWT_SECRET_KEY")  # Generate with: openssl rand -hex 32
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    
    # RATE LIMITING
    RATE_LIMIT_REQUESTS: int = 100  # Requests per window
    RATE_LIMIT_WINDOW_SECONDS: int = 3600  # 1 hour
    
    # LOGGING
    LOG_LEVEL: str = "INFO"  # DEBUG, INFO, WARNING, ERROR
    LOG_FORMAT: str = "json"  # json or text

    # INGESTION
    PDF_CHUNK_SIZE: int = 300  # More granular chunks (approx 1200 chars)
    PDF_CHUNK_OVERLAP: int = 100  # Increased overlap for better context (approx 400 chars)
    MAX_UPLOAD_SIZE_MB: int = 100  # Max PDF size
    UPLOADS_DIRECTORY: str = "./uploads_dir"  # Relative path for uploads
    
    @property
    def uploads_path(self) -> str:
        """
        Get the correct uploads directory path based on environment.
        
        In Docker: /app/uploads_dir (mounted volume)
        On Windows host: ./uploads_dir (relative to project root)
        """
        # Check if running in Docker by looking for /app directory
        if os.path.exists("/app"):
            return "/app/uploads_dir"
        return self.UPLOADS_DIRECTORY
    
    # QUALITY THRESHOLDS
    HALLUCINATION_THRESHOLD: float = 0.3  # Confidence threshold
    MIN_RETRIEVAL_SCORE: float = 0.7  # Min semantic similarity

    # SENDGRID
    RESEND_API_KEY: Optional[str] = None
    RESEND_FROM_EMAIL: str = "onboarding@resend.dev"
    

    @property
    def mongodb_url(self) -> str:
        """
        Get the MongoDB URI from environment or settings.
        """
        # Prioritize os.environ over pydantic field to ensure Railway vars win
        uri = os.environ.get("MONGODB_URI") or self.MONGODB_URI
        return uri.strip() if uri else ""
    
    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.ENV.lower() == "production"
    
    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.ENV.lower() == "development"
    
    @property
    def redis_url(self) -> str:
        """
        Get the Redis connection URL with environment priority.
        
        Priority:
        1. os.environ["REDIS_URL"] (Railway default)
        2. os.environ["REDIS_URI"]
        3. self.REDIS_URL_ENV
        4. self.REDIS_URI
        5. Default localhost
        """
        import os
        # Prioritize os.environ directly to ensure Railway/Env vars win over .env cache
        env_url = os.environ.get("REDIS_URL") or os.environ.get("REDIS_URI")
        if env_url:
            return env_url.strip()
            
        settings_url = self.REDIS_URL_ENV or self.REDIS_URI
        return settings_url or "redis://localhost:6379/0"

    def get_celery_broker_url(self) -> Optional[str]:
        """Get Celery broker URL with strict environment priority."""
        import os
        # Absolute priority: Railway's REDIS_URL
        if os.environ.get("REDIS_URL"):
            return os.environ["REDIS_URL"].strip()
            
        # Second priority: Explicit CELERY_BROKER_URL (if not localhost in production)
        if self.CELERY_BROKER_URL:
            # If we are in production but broker is localhost, ignore it and try redis_url
            if self.is_production and "localhost" in self.CELERY_BROKER_URL:
                return self.redis_url
            return self.CELERY_BROKER_URL
            
        return self.redis_url
    
    def get_celery_backend(self) -> Optional[str]:
        """Get Celery result backend with strict environment priority."""
        import os
        # Absolute priority: Railway's REDIS_URL
        if os.environ.get("REDIS_URL"):
            return os.environ["REDIS_URL"].strip()
            
        # Second priority: Explicit CELERY_RESULT_BACKEND
        if self.CELERY_RESULT_BACKEND:
            if self.is_production and "localhost" in self.CELERY_RESULT_BACKEND:
                return self.redis_url
            return self.CELERY_RESULT_BACKEND
            
        return self.redis_url
    
    @property
    def google_credentials_dict(self) -> Optional[Dict[str, Any]]:
        """Parse Google credentials JSON string to dict."""
        if self.GOOGLE_VISION_CREDENTIALS_JSON:
            import json
            return json.loads(self.GOOGLE_VISION_CREDENTIALS_JSON)
        return None
    
@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance.
    
    Usage:
        from app.config import get_settings
        settings = get_settings()
    """
    return Settings()



# Debug: Check if env var is actually set before pydantic reads it
_mongo_env = os.environ.get("MONGODB_URI")
if _mongo_env is None:
    _status = "MISSING (None)"
elif len(_mongo_env.strip()) == 0:
    _status = "EMPTY STRING"
else:
    _status = f"PRESENT ('{_mongo_env[:5]}...')"

print(f"[ENV DEBUG] MONGODB_URI status: {_status} (len={len(_mongo_env) if _mongo_env else 0})")
print(f"[ENV DEBUG] MONGO-related keys in os.environ: {[k for k in os.environ.keys() if 'MONGO' in k]}")

# Singleton instance for convenience
settings = get_settings()
