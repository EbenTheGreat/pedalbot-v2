from pydantic import BaseModel, Field
from typing import Literal, Optional, Dict, Any, List
from enum import Enum
from datetime import datetime


class AgentIntent(str, Enum):
    MANUAL_QUESTION = "manual_question"
    PRICING = "pricing"
    EXPLANATION = "explanation"
    HYBRID = "hybrid" # Needs multiple agents
    CASUAL = "casual"  # Greetings and casual chat


class FallbackReason(str, Enum):
    """Tracks WHY a query fell back - enables smarter fallback messages."""
    NONE = "none"  # No fallback needed
    AMBIGUOUS_QUERY = "ambiguous_query"  # Query is too vague/unclear
    LOW_RELEVANCE = "low_relevance"  # Retrieved chunks don't match intent
    CONCEPT_NOT_EXPLICIT = "concept_not_explicit"  # Concept exists but not explicitly documented
    DATA_MISSING = "data_missing"  # Information genuinely not in manual
    HALLUCINATION_DETECTED = "hallucination_detected"  # Answer contained unsupported claims
    RETRIEVAL_FAILED = "retrieval_failed"  # No chunks retrieved at all
    ROUTER_ERROR = "router_error"  # Router failed to classify


class AgentState(BaseModel):
    """Shared state across all agents in the workflow"""
    # # Transient state (current request only)
    user_id: str
    conversation_id: str  # Links to MongoDB  
    query: str
    pedal_name: str
    intent: Optional[AgentIntent] = None
    
    # Conversation context (for multi-turn conversations)
    conversation_history: List[Dict[str, str]] = Field(
        default_factory=list,
        description="Previous messages in format [{'role': 'user'|'assistant', 'content': '...'}]"
    )
    
    # Query preprocessing metadata
    original_query: Optional[str] = None  # Query before preprocessing
    normalized_query: Optional[str] = None  # Query after typo correction
    sub_questions: List[str] = Field(default_factory=list)  # Split questions if multi-question
    typos_corrected: List[Dict[str, Any]] = Field(default_factory=list)  # Typo corrections made (position is int)
    has_multi_questions: bool = False  # True if query contains multiple questions

    # Manual Retrieval (from Pinecone, not stored long-term) 
    pinecone_namespace: Optional[str] = None  
    retrieved_chunks: List[str] = Field(default_factory=list)
    retrieval_scores: List[float] = Field(default_factory=list)

    # Response tracking Agent outputs (ephemeral, logged to MongoDB) 
    raw_answer: Optional[str] = None
    final_answer: Optional[str] = None
    price_info: Optional[Dict[str, Any]] = None
    explanation_info: Optional[Dict[str, Any]] = None
    
    # Hybrid query sub-results (for combining manual + pricing)
    manual_answer: Optional[str] = None  # Answer from manual agent only
    pricing_answer: Optional[str] = None  # Answer from pricing agent only
    hybrid_partial_success: bool = False  # True if at least one sub-agent succeeded

    # Quality flags
    hallucination_flag: bool = False
    confidence_score: float = 0.0
    needs_human_review: bool = False
    fallback_reason: FallbackReason = FallbackReason.NONE  # Tracks WHY fallback occurred
    skip_quality_check: bool = False  # Skip quality check for meta-responses (system prompt questions)
    
    # Communication
    email_payload: Optional[Dict[str, str]] = None
    
    # Error handling
    error: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3

    # Metadata
    context: List[str] = Field(default_factory=list)
    agent_path: List[str] = Field(default_factory=list)  # Track routing
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        arbitrary_types_allowed = True

