"""
Pydantic models for MongoDB documents.

These models provide:
- Type safety for database operations
- Validation before insert/update
- Serialization to/from MongoDB BSON
"""

from pydantic import Field, field_validator, BaseModel, EmailStr
from typing import Optional, List, Dict, Any, Type, TypeVar
from datetime import datetime, UTC
from enum import Enum
import uuid


# ENUMS
class UserRole(str, Enum):
    FREE = "free"
    PRO = "pro"
    STORE = "store"
    ADMIN = "admin"


class ManualStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class JobStatus(str, Enum):
    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


# USER MODELS
class UserPreferences(BaseModel):
    """user preferences for personalization"""
    preffered_tone : str = "balanced"  # casual, technical, balanced
    show_prcing: bool = True
    email_notifications: bool = False

class UserDocument(BaseModel):
    """user collection schema"""
    user_id: str = Field(default_factory=lambda: f"user_{uuid.uuid4().hex[:12]}")
    email : EmailStr
    hashed_password: str
    role: UserRole = UserRole.FREE
    preferences: UserPreferences = Field(default_factory=UserPreferences)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    last_login: Optional[datetime] = None


    # Usage Tracking
    queries_count: int = 0
    queries_limit: Optional[int] = None # None = unlimited

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "user_a1b2c3d4e5f6",
                "email": "guitarist@example.com",
                "role": "free",
                "queries_count": 42,
                "queries_limit": 100
            }
        }


# CONVERSATION MODELS   
class Message(BaseModel):
    """Individual message in a conversation"""
    role: str #user or assistant
    content: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: Dict[str, Any] = Field(default_factory= dict) # agent_path, latency, etc.


class ConversationDocument(BaseModel):
    """Conversation collection schema"""
    conversation_id : str = Field(default_factory=lambda: f"conv_{uuid.uuid4().hex[:12]}")
    user_id: str
    started_at: datetime= Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime= Field(default_factory=lambda: datetime.now(UTC))
    messages : List[Message] = Field(default_factory=list)
    pedal_context: Optional[str] = None # Current pedal being discussed

    class Config:
        json_schema_extra= {
            "example": {
                "conversation_id": "conv_x7y8z9a0b1c2",
                "user_id": "user_a1b2c3d4e5f6",
                "pedal_context": "Boss DS-1",
                "messages": [
                    {"role": "user", "content": "Is the DS-1 analog?"},
                    {"role": "assistant", "content": "Yes, the Boss DS-1..."}
                ]
            }
        }

    
# MANUAL MODELS
class ManualDocument(BaseModel):
    """Manual collection schema"""
    manual_id: str = Field(default_factory=lambda: f"manual_{uuid.uuid4().hex[:12]}")
    pedal_name: str # e.g., "Boss DS-1"
    manufacturer: Optional[str] = None  # e.g., "Boss"
    pdf_url: Optional[str] # S3 URL or public URL
    pinecone_namespace: str # e.g., "boss_ds1_manual"
    status : ManualStatus = ManualStatus.PENDING

    # Ingestion metadata
    chunk_count: int = 0
    page_count: Optional[int] = None
    file_size_bytes: Optional[int] = None

    # Timestamps
    uploaded_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    indexed_at: Optional[datetime] = None

    # Quality flags
    ocr_required: bool = False
    quality_score: Optional[float] = None  # 0-1, based on text extraction

    @field_validator("pinecone_namespace")
    @classmethod
    def validate_namespace(cls, v: str) -> str:
        """Ensures namespace is lowercase and uses underscores"""
        return v.lower().replace(" ", "_").replace("-", "_")
    
    class Config:
        json_schema_extra = {
            "example": {
                "manual_id": "manual_m1n2o3p4q5r6",
                "pedal_name": "Boss DS-1",
                "manufacturer": "Boss",
                "pinecone_namespace": "boss_ds1_manual",
                "status": "completed",
                "chunk_count": 87,
                "page_count": 12
            }
        }


# ANSWER MODELS (FOR ANALYTICS)
class AnswerDocument(BaseModel):
    """Answers collection schema (logged after each query)"""
    answer_id: str = Field(default_factory=lambda: f"ans_{uuid.uuid4().hex[:12]}")
    conversation_id: str
    user_id: str

    # Query details
    query: str
    pedal_name: Optional[str] = None
    intent: Optional[str] = None  # manual_question, pricing, explanation

    # Response
    answer: str
    manual_id: Optional[str] = None  # Which manual was used
    retrieved_chunks: List[str] = Field(default_factory=list)

    # Quality metrics
    hallucination_flag: bool = False
    confidence_score: float = 0.0

    needs_human_review: bool = False

    # Performance metrics
    latency_ms: int = 0
    cost_usd: float = 0.0
    cache_hit: bool = False
    agent_path: List[str] = Field(default_factory=list)

    # Feedback 
    user_rating: Optional[int] = None  # 1-5 stars
    user_feedback: Optional[str] = None

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    class Config:
        json_schema_extra = {
            "example": {
                "answer_id": "ans_r7s8t9u0v1w2",
                "user_id": "user_a1b2c3d4e5f6",
                "query": "What's the input impedance?",
                "answer": "The Boss DS-1 has an input impedance of 1MΩ...",
                "confidence_score": 0.95,
                "latency_ms": 1243,
                "agent_path": ["router", "manual_agent", "synthesizer"]
            }
        }


# PRICING MODELS
class PriceListing(BaseModel):
    "Individual listing from a marketplace."
    listing_id: str
    price_usd: float
    condition: str     # "new", "mint", "excellent", "good", "fair"
    url: str
    seller_name: Optional[str]= None
    shipping_usd: Optional[float] = None
    listed_at: datetime


class PricingDocument(BaseModel):
    "Pricing model schema (24hrs TTL)."
    pedal_name: str
    manufacturer: Optional[str] = None

    # Aggregate stats
    avg_price: float
    min_price: float
    max_price: float
    median_price: Optional[float] = None
    
    # Raw listings (for detailed view)
    listings: List[PriceListing] = Field(default_factory=list)
    total_listings: int = 0

    # Source metadata
    source: str = "reverb"  # reverb, ebay, sweetwater
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    class Config:
        json_schema_extra = {
            "example": {
                "pedal_name": "Boss DS-1",
                "avg_price": 54.99,
                "min_price": 35.00,
                "max_price": 89.99,
                "total_listings": 127,
                "source": "reverb"
            }
        }


# INGESTION JOB MODELS
class IngestionJobDocument(BaseModel):
    """Ingestion jobs collection schema (for Celery tasks)."""
    job_id: str = Field(default_factory=lambda: f"job_{uuid.uuid4().hex[:12]}")
    manual_id: str
    status: JobStatus = JobStatus.QUEUED
    progress: float = 0.0  # 0-100
    
    # Error tracking
    error: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    
    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # Metrics
    chunks_processed: int = 0
    total_chunks: Optional[int] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "job_id": "job_j1k2l3m4n5o6",
                "manual_id": "manual_m1n2o3p4q5r6",
                "status": "in_progress",
                "progress": 67.3,
                "chunks_processed": 58,
                "total_chunks": 87
            }
        }


# HELPER FUNCTIONS
T = TypeVar("T")

def document_to_dict(doc: BaseModel) -> Dict[str, Any]:
    """Convert Pydantic model to MongoDB-compatible dict."""
    return doc.model_dump(by_alias=True, exclude_none=True)


def dict_to_document(data: Dict[str, Any], model: Type[T]) -> T:
    """Convert MongoDB dict to Pydantic model."""
    return model(**data)
