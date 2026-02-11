"""
FastAPI router for query endpoints.

Main endpoint: POST /api/query/
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from fastapi.responses import StreamingResponse
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import logging
import json
import uuid
from datetime import datetime, UTC
from bson import ObjectId

from backend.db.mongodb import get_database
from backend.db.models import(
    ConversationDocument, AnswerDocument, Message,
    document_to_dict, dict_to_document
)

from backend.agents.graph import PedalBotGraph, create_pedalbot_graph
from backend.state import AgentState
from backend.config.config import settings


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/query", tags=["query"])


# HELPER FUNCTIONS
def convert_objectid_to_str(doc: Any) -> Any:
    """
    Recursively convert all ObjectId instances to strings in a document.
    This handles nested dicts, lists, and ObjectId fields.
    """
    if isinstance(doc, dict):
        return {key: convert_objectid_to_str(value) for key, value in doc.items()}
    elif isinstance(doc, list):
        return [convert_objectid_to_str(item) for item in doc]
    elif isinstance(doc, ObjectId):
        return str(doc)
    else:
        return doc


def generate_user_id() -> str:
    """Generate anonymous user ID."""
    return f"anon_{uuid.uuid4().hex[:12]}"


def generate_conversation_id() -> str:
    """Generate conversation ID."""
    return f"conv_{uuid.uuid4().hex[:12]}"


# REQUEST/RESPONSE MODELS
class QueryRequest(BaseModel):
    """
    Request to query PedalBot.
    
    - query: Your question (required)
    - pedal_name: Pedal name (required for first message, optional for follow-ups)
    - conversation_id: Optional - provide to continue existing conversation
    
    Note: user_id and conversation_id are auto-generated if not provided.
    """
    query: str = Field(..., description="User question", min_length=1, max_length=1000)
    pedal_name: Optional[str] = Field(
        None, 
        description="Pedal name (required for first message, uses conversation context for follow-ups)"
    )
    conversation_id: Optional[str] = Field(
        None, 
        description="Conversation ID - auto-generated if not provided, or provide existing ID for follow-ups"
    )
    stream: bool = Field(False, description="Stream response")


class QueryResponse(BaseModel):
    """Response from PedalBot."""
    answer: str
    conversation_id: str
    user_id: str  # Return the auto-generated user_id so client can track
    pedal_name: str  # Return the resolved pedal name
    intent: Optional[str]
    confidence: float
    agent_path: list[str]
    hallucination_flag: bool
    fallback_reason: Optional[str] = None  # Why the query fell back (if it did)
    latency_ms: int
    cost_usd: float
    sources: Optional[list[str]] = None


class PedalInfo(BaseModel):
    """Information about an indexed pedal."""
    pedal_name: str
    manufacturer: Optional[str]
    pinecone_namespace: str
    chunk_count: int
    indexed_at: Optional[datetime]


class PedalsListResponse(BaseModel):
    """Response listing available pedals."""
    pedals: List[PedalInfo]
    total: int


# GRAPH SINGLETON (INITIALIZED ON STARTUP)

_graph: Optional[PedalBotGraph] = None

async def get_graph() -> PedalBotGraph:
    """Get or create PedalBot graph singleton."""
    global _graph
    
    if _graph is None:
        _graph = await create_pedalbot_graph(
            groq_api_key=settings.GROQ_API_KEY,
            voyageai_api_key=settings.VOYAGEAI_API_KEY,
            pinecone_api_key=settings.PINECONE_API_KEY,
            pinecone_index_name=settings.PINECONE_INDEX_NAME,
            reverb_api_key=settings.REVERB_API_KEY  
        )
        logger.info(f"PedalBot graph initialized (Reverb API: {'enabled' if settings.REVERB_API_KEY else 'disabled'})")
    
    return _graph


# ENDPOINTS
@router.get("/pedals", response_model=PedalsListResponse)
async def list_available_pedals(
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """
    List all available pedals with indexed manuals.
    
    Use this to discover which pedals you can ask questions about.
    """
    try:
        # Find all completed manuals
        cursor = db.manuals.find({"status": "completed"})
        manuals = await cursor.to_list(length=100)
        
        pedals = [
            PedalInfo(
                pedal_name=m.get("pedal_name", "Unknown"),
                manufacturer=m.get("manufacturer"),
                pinecone_namespace=m.get("pinecone_namespace", ""),
                chunk_count=m.get("chunk_count", 0),
                indexed_at=m.get("indexed_at")
            )
            for m in manuals
        ]
        
        return PedalsListResponse(pedals=pedals, total=len(pedals))
        
    except Exception as e:
        logger.error(f"Failed to list pedals: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/", response_model=QueryResponse)
async def query_pedalbot(
    request: QueryRequest,
    db: AsyncIOMotorDatabase = Depends(get_database),
    graph: PedalBotGraph = Depends(get_graph),
):
    """
    Query PedalBot with a question.
    
    This is the main endpoint for asking questions about pedals.
    
    **Smart Defaults:**
    - `user_id`: Auto-generated (anonymous session)
    - `conversation_id`: Auto-generated for new conversations, or provide existing ID for follow-ups
    - `pedal_name`: Required for first message, or inherited from conversation context
    
    **Example (first message):**
    ```json
    {
        "query": "What is the input impedance?",
        "pedal_name": "Boss GT-10"
    }
    ```
    
    **Example (follow-up in same conversation):**
    ```json
    {
        "query": "What about the output impedance?",
        "conversation_id": "conv_abc123def456"
    }
    ```
    """
    start_time = datetime.now(UTC)

    try:
        # Auto-generate user_id (anonymous session)
        user_id = generate_user_id()
        
        # Handle conversation context
        # Normalize conversation_id: treat empty, whitespace, or placeholder values as None
        conversation_id = request.conversation_id
        if conversation_id and (not conversation_id.strip() or conversation_id.strip().lower() == "string"):
            conversation_id = None
            
        pedal_name = request.pedal_name
        existing_conversation = None
        
        if conversation_id:
            # Try to get existing conversation for pedal context
            existing_conversation = await db.conversations.find_one(
                {"conversation_id": conversation_id}
            )
            
            if existing_conversation:
                # Inherit user_id from existing conversation
                user_id = existing_conversation.get("user_id", user_id)
                
                # If no pedal_name provided, use conversation's pedal context
                if not pedal_name:
                    pedal_name = existing_conversation.get("pedal_context")
                    if pedal_name:
                        logger.info(f"Using pedal from conversation context: {pedal_name}")
        
        # Validate: pedal_name is required (either provided or from context)
        if not pedal_name:
            # Try to suggest available pedals
            cursor = db.manuals.find({"status": "completed"}, {"pedal_name": 1})
            available = await cursor.to_list(length=10)
            pedal_names = [m.get("pedal_name") for m in available if m.get("pedal_name")]
            
            hint = ""
            if pedal_names:
                hint = f" Available pedals: {', '.join(pedal_names[:5])}"
            
            raise HTTPException(
                status_code=400,
                detail=f"pedal_name is required for the first message in a conversation.{hint} Use GET /api/query/pedals to see all available pedals."
            )
        
        logger.info(f"Query from user {user_id}: {request.query[:100]}")
        
        # Create new conversation if needed
        if not conversation_id:
            conversation = ConversationDocument(
                user_id=user_id,
                pedal_context=pedal_name
            )
            await db.conversations.insert_one(document_to_dict(conversation))
            conversation_id = conversation.conversation_id
            logger.info(f"Created new conversation: {conversation_id}")
        elif not existing_conversation:
            # conversation_id provided but not found - create it
            conversation = ConversationDocument(
                conversation_id=conversation_id,
                user_id=user_id,
                pedal_context=pedal_name
            )
            await db.conversations.insert_one(document_to_dict(conversation))
            logger.info(f"Created conversation with provided ID: {conversation_id}")

        # Fetch conversation history for context
        conversation_history = []
        if existing_conversation and existing_conversation.get("messages"):
            # Get last 5 messages for context (avoid token overflow)
            recent_messages = existing_conversation["messages"][-5:]
            conversation_history = [
                {
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", "")
                }
                for msg in recent_messages
            ]
            logger.info(f"Loaded {len(conversation_history)} previous messages for context")
        
        # Create initial state
        state = AgentState(
            user_id=user_id,
            conversation_id=conversation_id,
            query=request.query,
            pedal_name=pedal_name,
            conversation_history=conversation_history,
            created_at=start_time
        )
        
        # Run workflow
        final_state = await graph.run(state)

        # Calculate latency
        latency_ms = int((datetime.now(UTC) - start_time).total_seconds() * 1000)
        
        # Estimate cost (simplified)
        cost_usd = 0.008  # Rough estimate
        
        # Save to conversations
        await db.conversations.update_one(
            {"conversation_id": conversation_id},
            {
                "$push": {
                    "messages": {
                        "$each": [
                            document_to_dict(Message(
                                role="user",
                                content=request.query,
                                metadata={"pedal_name": pedal_name}
                            )),
                            document_to_dict(Message(
                                role="assistant",
                                content=final_state.final_answer or "No answer generated",
                                metadata={
                                    "intent": final_state.intent.value if final_state.intent else None,
                                    "confidence": final_state.confidence_score,
                                    "agent_path": final_state.agent_path,
                                    "hallucination_flag": final_state.hallucination_flag,
                                }
                            ))
                        ]
                    }
                },
                "$set": {
                    "updated_at": datetime.now(UTC),
                    "pedal_context": pedal_name  # Update pedal context
                }
            }
        )

        # Save answer for analytics
        answer_doc = AnswerDocument(
            conversation_id=conversation_id,
            user_id=user_id,
            query=request.query,
            pedal_name=pedal_name,
            intent=final_state.intent.value if final_state.intent else None,
            answer=final_state.final_answer or "",
            retrieved_chunks=final_state.retrieved_chunks,
            hallucination_flag=final_state.hallucination_flag,
            confidence_score=final_state.confidence_score,
            latency_ms=latency_ms,
            cost_usd=cost_usd,
            agent_path=final_state.agent_path,
        )

        await db.answers.insert_one(document_to_dict(answer_doc))
        
        logger.info(
            f"Query completed: {latency_ms}ms, "
            f"confidence={final_state.confidence_score:.2f}, "
            f"path={' → '.join(final_state.agent_path)}"
        )

        return QueryResponse(
            answer=final_state.final_answer or "No answer generated",
            conversation_id=conversation_id,
            user_id=user_id,
            pedal_name=pedal_name,
            intent=final_state.intent.value if final_state.intent else None,
            confidence=final_state.confidence_score,
            agent_path=final_state.agent_path,
            hallucination_flag=final_state.hallucination_flag,
            fallback_reason=final_state.fallback_reason.value if final_state.fallback_reason else None,
            latency_ms=latency_ms,
            cost_usd=cost_usd,
            sources=final_state.retrieved_chunks[:3] if final_state.retrieved_chunks else None
        )
    
    except HTTPException:
        raise  # Re-raise HTTP exceptions as-is
    except Exception as e:
        logger.error(f"Query failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    

@router.post("/stream")
async def query_pedalbot_stream(
    request: QueryRequest,
    db: AsyncIOMotorDatabase = Depends(get_database),
    graph: PedalBotGraph = Depends(get_graph),
):
    """
    Query PedalBot with streaming response.
    
    Returns Server-Sent Events (SSE) stream.
    """

    async def event_generator():
        try:
            # Auto-generate user_id
            user_id = generate_user_id()
            
            # Get or create conversation
            # Normalize conversation_id: treat empty, whitespace, or placeholder values as None
            conversation_id = request.conversation_id
            if conversation_id and (not conversation_id.strip() or conversation_id.strip().lower() == "string"):
                conversation_id = None
                
            pedal_name = request.pedal_name
            
            if conversation_id:
                # Try to get existing conversation
                existing = await db.conversations.find_one({"conversation_id": conversation_id})
                if existing:
                    user_id = existing.get("user_id", user_id)
                    if not pedal_name:
                        pedal_name = existing.get("pedal_context")
            
            if not pedal_name:
                yield f"data: {json.dumps({'type': 'error', 'error': 'pedal_name is required for first message'})}\n\n"
                return
            
            if not conversation_id:
                conversation = ConversationDocument(
                    user_id=user_id,
                    pedal_context=pedal_name
                )
                await db.conversations.insert_one(document_to_dict(conversation))
                conversation_id = conversation.conversation_id
            
            # Send conversation ID and user_id first
            yield f"data: {json.dumps({'type': 'session', 'conversation_id': conversation_id, 'user_id': user_id, 'pedal_name': pedal_name})}\n\n"
            
            # Fetch conversation history for context
            conversation_history = []
            existing = await db.conversations.find_one({"conversation_id": conversation_id})
            if existing and existing.get("messages"):
                recent_messages = existing["messages"][-5:]
                conversation_history = [
                    {
                        "role": msg.get("role", "user"),
                        "content": msg.get("content", "")
                    }
                    for msg in recent_messages
                ]
            
            # Create state
            state = AgentState(
                user_id=user_id,
                conversation_id=conversation_id,
                query=request.query,
                pedal_name=pedal_name,
                conversation_history=conversation_history,
                created_at=datetime.now(UTC)
            )

            # Stream through graph
            async for event in graph.graph.astream(state):
                if isinstance(event, dict):
                    for node_name, node_state in event.items():
                        # Send node update
                        yield f"data: {json.dumps({'type': 'node', 'node': node_name})}\n\n"
                        
                        # Send partial answer if available
                        if hasattr(node_state, 'raw_answer') and node_state.raw_answer:
                            yield f"data: {json.dumps({'type': 'answer', 'text': node_state.raw_answer})}\n\n"
            
            # Send completion
            yield f"data: {json.dumps({'type': 'done'})}\n\n"

        except Exception as e:
            logger.error(f"Streaming failed: {e}")
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream"
    )


@router.get("/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Get conversation history."""
    conversation = await db.conversations.find_one({"conversation_id": conversation_id})
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    # Convert all MongoDB ObjectIds to strings for JSON serialization (including nested ones)
    conversation = convert_objectid_to_str(conversation)
    
    return conversation


@router.get("/health")
async def health_check(
    graph: PedalBotGraph = Depends(get_graph),
):
    """Health check for query service."""
    return {
        "status": "healthy",
        "graph_initialized": graph is not None,
        "timestamp": datetime.now(UTC).isoformat()
    }
