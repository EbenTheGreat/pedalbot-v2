"""
Application configuration using Pydantic BaseSettings.

Loads from environment variables with validation.

Usage:
    from app.config import settings
    
    print(settings.MONGODB_URI)
    print(settings.OPENAI_API_KEY)
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional, Dict, Any
from functools import lru_cache
from dotenv import load_dotenv
import os

# CRITICAL: Load .env file explicitly before Settings initialization
# This ensures environment variables are available when Pydantic reads them
load_dotenv()


class Settings(BaseSettings):
    """Application settings from environment variables."""

    model_config = {
    "env_file": ".env",
    "env_file_encoding": "utf-8",
    "case_sensitive": True,
    "validate_default": False,
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
    MONGODB_URI: str = Field(default="", alias="MONGODB_URI")
    MONGODB_URI_PRODUCTION: Optional[str] = Field(default=None, alias="MONGODB_URI_PRODUCTION")
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
        Construct full MongoDB URI with fallback logic.
        
        Prioritizes MONGODB_URI_PRODUCTION if set, otherwise MONGODB_URI.
        Ensures empty strings are treated as None.
        """
        # Try both names from environment first
        uri_prod = _os.environ.get("MONGODB_URI_PRODUCTION")
        uri_main = _os.environ.get("MONGODB_URI")
        
        # Also check model fields (which might come from .env files)
        model_prod = self.MONGODB_URI_PRODUCTION
        model_main = self.MONGODB_URI
        
        # Decision sequence:
        # 1. Non-empty PRODUCTION from env
        if uri_prod and len(uri_prod.strip()) > 0:
            return uri_prod
        # 2. Non-empty MAIN from env
        if uri_main and len(uri_main.strip()) > 0:
            return uri_main
        # 3. Non-empty PRODUCTION from model (.env)
        if model_prod and len(model_prod.strip()) > 0:
            return model_prod
        # 4. Non-empty MAIN from model (.env)
        if model_main and len(model_main.strip()) > 0:
            return model_main
            
        return ""
    
    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.ENV.lower() == "production"
    
    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.ENV.lower() == "development"
    
    def get_celery_broker_url(self) -> Optional[str]:
        """Get Celery broker URL, defaulting to Redis if set."""
        return self.CELERY_BROKER_URL or self.REDIS_URI or "redis://localhost:6379/0"
    
    def get_celery_backend(self) -> Optional[str]:
        """Get Celery result backend, defaulting to Redis if set."""
        return self.CELERY_RESULT_BACKEND or self.REDIS_URI or "redis://localhost:6379/1"
    
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
import os as _os
_mongo_env = _os.environ.get("MONGODB_URI", "NOT_SET")
print(f"[ENV DEBUG] MONGODB_URI from os.environ: '{_mongo_env[:30]}...' (len={len(_mongo_env)})")
print(f"[ENV DEBUG] All env vars with MONGO: {[k for k in _os.environ.keys() if 'MONGO' in k]}")

# Singleton instance for convenience
settings = get_settings() 

