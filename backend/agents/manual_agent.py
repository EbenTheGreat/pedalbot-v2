"""
Manual Agent: Retrieves and answers questions from pedal manuals.

Uses RAG (Retrieval-Augmented Generation):
1. Embed query
2. Search Pinecone for relevant chunks
3. Generate answer with llama-3.3-70b-versatile

Architecture:
- System identity and context are SEPARATE messages
- Context is injected as a hidden layer, not merged with identity
- System prompt questions get a safe, professional response
"""

from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from typing import List, Dict, Any, Optional
import logging

from backend.state import AgentState
from backend.services.pinecone_client import PineconeClient, SearchResult
from backend.services.embeddings import EmbeddingService
from backend.prompts.manual_prompts import (
    PEDALBOT_IDENTITY,
    CONTEXT_TEMPLATE,
    SYSTEM_PROMPT_RESPONSE,
    is_system_prompt_question,
)

logger = logging.getLogger(__name__)

class ManualAgent:
    """
    Answers questions using pedal manual content via RAG.
    
    Pipeline:
    1. Embed query → vector
    2. Search Pinecone → retrieve relevant chunks
    3. Build context → top K chunks
    4. Generate answer → llama-3.3-70b-versatile with context
    5. Validate → check for hallucinations
    """

    # Prompts are now imported from backend.prompts.manual_prompts
    # This keeps agent code clean and prompts centralized
    def __init__(
        self,
        groq_api_key: str,
        pinecone_client: PineconeClient,
        embeddings_service: EmbeddingService,
        model: str = "llama-3.3-70b-versatile",
        temperature: float = 0.1,
        top_k: int = 5,
        min_score: float = 0.5,  # Lowered from 0.7 - OCR text may not match as precisely
    ):
        
        """
        Initialize manual agent.
        
        Args:
            groq_api_key: Groq API key
            pinecone_client: Pinecone client for vector search
            embeddings_service: Service for generating embeddings
            model: Model for answer generation (llama-3.3-70b-versatile)
            temperature: Low temp for factual answers
            top_k: Number of chunks to retrieve
            min_score: Minimum similarity score to include chunk
        """

        self.llm = ChatGroq(
            api_key=groq_api_key,
            model=model,
            temperature=temperature,
            max_tokens=500
        )
        self.pinecone = pinecone_client
        self.embeddings = embeddings_service
        self.model = model
        self.temperature = temperature
        self.top_k = top_k
        self.min_score = min_score

    
    async def answer(self, state: AgentState) -> AgentState:
        """
        Generate answer from manual content.
        
        Args:
            state: Agent state with query and pedal context
        
        Returns:
            Updated state with answer and retrieved chunks
        """

        logger.info(f"Manual agent processing: {state.query[:100]}")

        try:
            # Step 0: Check for system prompt meta-questions
            if is_system_prompt_question(state.query):
                logger.info("[MANUAL_AGENT] System prompt question detected - returning safe response")
                state.raw_answer = SYSTEM_PROMPT_RESPONSE.format(pedal_name=state.pedal_name)
                state.confidence_score = 1.0
                state.skip_quality_check = True  # Don't flag this as hallucination
                state.agent_path.append("manual_agent")
                return state

            # Step 1: Get Pinecone namespace for this pedal
            namespace = await self._get_namespace(state.pedal_name)
            if not namespace:
                state.error = f"No manual found for {state.pedal_name}"
                state.raw_answer = f"I don't have a manual for '{state.pedal_name}' yet."
                return state
            
            state.pinecone_namespace = namespace

            if not state.query or not state.query.strip():
                state.error = "Empty query"
                state.raw_answer = "Please ask a question about the pedal manual."
                return state


            # Step 2: Embed query (use normalized query if available from preprocessing)
            query_for_embedding = state.normalized_query if state.normalized_query else state.query
            
            logger.info(f"[MANUAL_AGENT] Embedding query: '{query_for_embedding[:100]}'")
            if state.normalized_query and state.normalized_query != state.query:
                logger.info(f"[MANUAL_AGENT] Using normalized query (original: '{state.query[:100]}')")
            
            embedding_result = await self.embeddings.embed_single(query_for_embedding)
            query_embedding = embedding_result.embeddings[0]

            # Step 3: Adaptive threshold based on query length
            # Short/vague queries need lower threshold since embeddings are less precise
            query_words = len(state.query.split())
            if query_words <= 4:
                effective_min_score = 0.3  # Very lenient for short queries
            elif query_words <= 8:
                effective_min_score = 0.4  # Moderate for medium queries
            else:
                effective_min_score = self.min_score  # Use default for longer queries
            
            logger.info(f"[MANUAL_AGENT] Query has {query_words} words, using min_score={effective_min_score}")

            # Step 4: Search Pinecone
            logger.info(f"[MANUAL_AGENT] Searching namespace '{namespace}'")
            results = self.pinecone.search(
                query_embedding=query_embedding,
                namespace=namespace,
                top_k=self.top_k,
                include_metadata=True
            )

            # Log raw results before filtering
            if results:
                scores = [r.score for r in results]
                logger.info(f"[MANUAL_AGENT] Raw search returned {len(results)} results. Scores: {scores}")
            else:
                logger.warning(f"[MANUAL_AGENT] Pinecone search returned NO results for namespace '{namespace}'")

            # Filter by adaptive score
            filtered_results = [r for r in results if r.score >= effective_min_score]
            
            logger.info(f"[MANUAL_AGENT] After filtering (min_score={effective_min_score}): {len(filtered_results)} results")
            
            # FALLBACK: If no results, try a broader search with pedal context
            if not filtered_results and results:
                logger.info("[MANUAL_AGENT] Trying fallback query rewrite...")
                
                # Create a broader fallback query
                fallback_query = f"{state.pedal_name} features specifications setup connections power"
                fallback_embedding_result = await self.embeddings.embed_single(fallback_query)
                fallback_embedding = fallback_embedding_result.embeddings[0]
                
                fallback_results = self.pinecone.search(
                    query_embedding=fallback_embedding,
                    namespace=namespace,
                    top_k=self.top_k,
                    include_metadata=True
                )
                
                if fallback_results:
                    fallback_scores = [r.score for r in fallback_results]
                    logger.info(f"[MANUAL_AGENT] Fallback search returned {len(fallback_results)} results. Scores: {fallback_scores}")
                    
                    # Use even lower threshold for fallback
                    filtered_results = [r for r in fallback_results if r.score >= 0.25]
                    logger.info(f"[MANUAL_AGENT] Fallback filtering (min_score=0.25): {len(filtered_results)} results")
            
            if not filtered_results:
                # Log what we would have had if threshold was lower
                if results:
                    logger.warning(
                        f"[MANUAL_AGENT] All {len(results)} results filtered out! "
                        f"Top score was {results[0].score:.3f}, threshold is {effective_min_score}"
                    )
                state.error = "No relevant content found in manual"
                state.raw_answer = (
                    f"I couldn't find relevant information about that in the "
                    f"{state.pedal_name} manual. Could you rephrase your question?"
                )
                state.confidence_score = 0.0
                return state
            
            # Step 4: Build context
            context = self._build_context(filtered_results)
            
            # Store chunks WITH metadata for the frontend
            formatted_chunks = []
            for i, r in enumerate(filtered_results, 1):
                page = r.metadata.get("page_number", "unknown")
                section = r.metadata.get("section", "general")
                formatted_chunks.append(
                    f"[Excerpt {i} - Page {page}, Section: {section}]\n{r.text}"
                )
            
            state.retrieved_chunks = formatted_chunks
            state.retrieval_scores = [r.score for r in filtered_results]
            
            # Step 5: Generate answer
            answer = await self._generate_answer(
                state.query, 
                context,
                state.pedal_name,
                state.conversation_history
            )
            
            state.raw_answer = answer
            state.confidence_score = self._calculate_confidence(filtered_results)
            state.agent_path.append("manual_agent")
            
            logger.info(
                f"Generated answer (confidence: {state.confidence_score:.2f}, "
                f"chunks: {len(filtered_results)})"
            )
            
            return state
            
        except Exception as e:
            logger.error(f"Manual agent failed: {e}")
            state.error = f"Manual agent error: {str(e)}"
            state.raw_answer = "I encountered an error while searching the manual."
            return state

    
    async def _get_namespace(self, pedal_name: str) -> Optional[str]:
        """
        Get Pinecone namespace for a pedal using the PedalRegistry.
        
        Uses fuzzy matching to resolve user input like "Helix" to the 
        actual namespace like "manual_helix_3.80_owner's_manual___english".
        
        Args:
            pedal_name: User-provided pedal name (can be fuzzy)
            
        Returns:
            Pinecone namespace or None if not found
        """
        if not pedal_name:
            logger.warning("Empty pedal_name provided")
            return None
        
        try:
            # Use the PedalRegistry for fuzzy matching
            from backend.services.pedal_registry import resolve_pedal
            
            logger.debug(f"[NAMESPACE] Resolving pedal: '{pedal_name}'")
            
            pedal_info = await resolve_pedal(pedal_name)
            
            if not pedal_info:
                logger.warning(f"[NAMESPACE] No pedal found matching: '{pedal_name}'")
                # Log available pedals for debugging
                from backend.services.pedal_registry import get_pedal_registry
                registry = await get_pedal_registry()
                available = await registry.list_all()
                available_names = [p.display_name for p in available]
                logger.debug(f"[NAMESPACE] Available pedals: {available_names}")
                return None
            
            logger.info(
                f"[NAMESPACE] Resolved '{pedal_name}' → "
                f"namespace='{pedal_info.namespace}', "
                f"type={pedal_info.pedal_type.value}"
            )
            
            return pedal_info.namespace
            
        except Exception as e:
            logger.error(f"[NAMESPACE] Error resolving '{pedal_name}': {e}")
            return None

    def _build_context(self, results:List[SearchResult]) -> str:
        """
        Build context string from search results.
        
        Args:
            results: Search results from Pinecone
        
        Returns:
            Formatted context string
        """

        context_parts = []

        for i, result in enumerate(results, 1):
            page = result.metadata.get("page_number", "unknown")
            section = result.metadata.get("section", "general")

            context_parts.append(
                f"[Excerpt {i} - Page {page}, Section: {section}]\n"
                f"{result.text}\n"
            )

        return "\n".join(context_parts)

    
    async def _generate_answer(self, query: str, context: str, pedal_name: str, conversation_history: List[Dict[str, str]] = None) -> str:
        """
        Generate answer using llama-3.3-70b-versatile with retrieved context.
        
        Args:
            query: User query
            context: Retrieved manual excerpts
            pedal_name: Name of the pedal being queried
            conversation_history: Previous messages for context
        
        Returns:
            Generated answer
        """

        # THREE-LAYER MESSAGE ARCHITECTURE:
        # Layer 1: Identity prompt (behavioral rules only)
        identity_prompt = PEDALBOT_IDENTITY.format(pedal_name=pedal_name)
        
        # Layer 2: Context injection (hidden, not exposed as "system prompt")
        context_prompt = CONTEXT_TEMPLATE.format(pedal_name=pedal_name, context=context)

        # Build message list with separated layers
        messages = [
            SystemMessage(content=identity_prompt),  # Layer 1: Identity
            SystemMessage(content=context_prompt),   # Layer 2: Context (hidden)
        ]
        
        # Add conversation history if available (for follow-up questions)
        if conversation_history:
            for msg in conversation_history[-6:]:  # Last 3 exchanges
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if role == "user":
                    messages.append(HumanMessage(content=content))
                else:
                    # Use AIMessage for natural conversation flow:
                    # System → System → Human → AI → Human → AI → Human
                    messages.append(AIMessage(content=content))
        
        # Layer 3: User query
        messages.append(HumanMessage(content=query))
        
        response = await self.llm.ainvoke(messages)

        content = response.content
        return content.strip() if content else ""


    
    def _calculate_confidence(self, results: List[SearchResult]) -> float:
        """
        Calculate confidence score based on retrieval quality.
        
        High confidence if:
        - Top result has high similarity (>0.85)
        - Multiple results with good similarity (>0.75)
        - Results are from same section (consistency)
        """
        if not results:
            return 0.0
        
        # Base score from top result
        top_score = results[0].score

        # Boost if multiple good results
        good_results = [r for r in results if r.score > 0.75]
        consistency_boost = min(0.1, len(good_results) * 0.02)

        # Boost if results from same section (indicates focus)
        sections = [r.metadata.get('section') for r in results]
        if len(set(sections)) == 1:
            consistency_boost += 0.05

        confidence = min(1.0, top_score + consistency_boost)
        
        return confidence


# HELPER FUNCTIONS
async def query_manual(query: str, pedal_name: str, agent: ManualAgent,
                    ) -> Dict[str, Any]:
    
    """
    Convenience function to query manual.
    
    Args:
        query: User query
        pedal_name: Pedal name
        agent: ManualAgent instance
    
    Returns:
        Dict with answer, chunks, confidence
    """

    from backend.state import AgentState
    from datetime import datetime, UTC

    state = AgentState(
        user_id="temp_user",
        conversation_id="temp_conv",
        query=query,
        pedal_name=pedal_name,
        created_at=datetime.now(UTC)
    )

    state = await agent.answer(state)
    
    return {
        "answer": state.raw_answer,
        "chunks": state.retrieved_chunks,
        "confidence": state.confidence_score,
        "error": state.error,
    }
    


def format_answer_with_sources(state: AgentState) -> str:
    """
    Format answer with source citations.
    
    Args:
        state: State with answer and chunks
    
    Returns:
        Formatted answer with sources
    """
    if not state.raw_answer:
        return "No answer generated."
    
    formatted = state.raw_answer
    
    # Add sources if available
    if state.retrieved_chunks and len(state.retrieved_chunks) > 0:
        formatted += "\n\n**Sources:**\n"
        for i, score in enumerate(state.retrieval_scores[:3], 1):
            formatted += f"- Excerpt {i} (relevance: {score:.0%})\n"
    
    # Add confidence indicator
    if state.confidence_score > 0:
        confidence_label = (
            "High" if state.confidence_score > 0.8
            else "Medium" if state.confidence_score > 0.6
            else "Low"
        )
        formatted += f"\n*Confidence: {confidence_label}*"
    
    return formatted
    
