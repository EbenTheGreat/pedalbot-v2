"""
LangGraph workflow for PedalBot agent orchestration.

Flow:
1. Router → Classify intent
2. Specialist agents → Execute based on intent
3. Quality check → Validate answer
4. Synthesizer → Format final response

Hybrid Flow:
1. Router → Detect hybrid intent
2. Hybrid node → Run BOTH manual + pricing agents in parallel
3. Synthesizer → Combine partial results
4. Quality check → Validate combined answer
"""

import asyncio
from langgraph.graph import StateGraph, END
from langgraph.graph.state import CompiledStateGraph
from typing import Dict, Any, Optional
import logging

from backend.state import AgentState, AgentIntent
from backend.agents.router_agent import RouterAgent
from backend.agents.manual_agent import ManualAgent
from backend.agents.pricing_agent import PricingAgent
from backend.agents.quality_check import (QualityCheckAgent, should_reject_answer,
                                        get_safe_fallback_response
                                        )


logger = logging.getLogger(__name__)

class PedalBotGraph:
    """
    LangGraph-based multi-agent orchestrator.
    
    Nodes:
    - router: Classify intent
    - manual_agent: Answer from manuals
    - quality_check: Validate answer
    - synthesizer: Format final response
    
    Edges:
    - router → manual_agent (if MANUAL_QUESTION)
    - router → pricing_agent (if PRICING) [not implemented yet]
    - manual_agent → quality_check
    - quality_check → synthesizer (if valid)
    - quality_check → fallback (if invalid)
    """

    def __init__(self,
                router_agent: RouterAgent,
                manual_agent: ManualAgent,
                pricing_agent: PricingAgent,
                quality_check_agent: QualityCheckAgent):
        """
        Initialize graph with agents.
        
        Args:
            router_agent: Intent classification agent
            manual_agent: Manual RAG agent
            quality_check_agent: Answer validation agent
        """

        self.router = router_agent
        self.manual_agent = manual_agent
        self.pricing_agent = pricing_agent
        self.quality_check = quality_check_agent

        # Build Graph
        self.graph: CompiledStateGraph = self._build_graph()

    def _build_graph(self) -> CompiledStateGraph:
        """Build the LangGraph workflow."""

        # Create Graph with AgentState
        workflow = StateGraph(AgentState)

        # Add nodes
        workflow.add_node("router", self._router_node)
        workflow.add_node("manual_agent", self._manual_agent_node)
        workflow.add_node("pricing_agent", self._pricing_agent_node)
        workflow.add_node("hybrid_agent", self._hybrid_agent_node)  # NEW: Runs both agents
        workflow.add_node("quality_check", self._quality_check_node)
        workflow.add_node("synthesizer", self._synthesizer_node)
        workflow.add_node("fallback", self._fallback_node)

        workflow.set_entry_point("router")

        # Router routing logic
        # NOTE: explanation_agent not implemented yet, so route to manual_agent as fallback
        workflow.add_conditional_edges(
            "router",
            self._route_after_router,
            {
                "manual_agent": "manual_agent",
                "pricing_agent": "pricing_agent", 
                "explanation": "manual_agent",  # Fallback: use manual for explanation until explainer is built
                "hybrid": "hybrid_agent",  # NEW: Route to hybrid node that calls BOTH agents
                "casual": "synthesizer",  # CASUAL: Skip to synthesizer, answer already set in router
            }
        )

        # specialist agents → quality check
        workflow.add_edge("manual_agent", "quality_check")
        workflow.add_edge("pricing_agent", "quality_check")
        workflow.add_edge("hybrid_agent", "quality_check")  

        # Quality check routing
        workflow.add_conditional_edges(
            "quality_check",
            self._route_after_quality_check,
            {
                "synthesizer": "synthesizer",
                "fallback": "fallback",
            }
        )

        # End nodes
        workflow.add_edge("synthesizer", END)
        workflow.add_edge("fallback", END)
        
        return workflow.compile()
    
    
    # NODE IMPLEMENTATIONS
    async def _router_node(self, state: AgentState) -> AgentState:
        """Router node: Classify intent."""
        logger.info("Node: router")
        return await self.router.route(state)
    
    async def _manual_agent_node(self, state: AgentState) -> AgentState:
        """Manual agent node: Answer from manuals."""
        logger.info("Node: manual_agent")
        return await self.manual_agent.answer(state)
    
    async def _pricing_agent_node(self, state: AgentState) -> AgentState:
        """Pricing agent node: Fetch market data."""
        logger.info("Node: pricing_agent")
        return await self.pricing_agent.get_pricing(state)
    
    async def _hybrid_agent_node(self, state: AgentState) -> AgentState:
        """
        Hybrid agent node: Run BOTH manual and pricing agents.
        
        This is the key fix for hybrid queries like:
        "What reverb types does the Zoom G3 have and what's the price?"
        
        Strategy:
        - Run both agents concurrently (best-effort)
        - Store partial results in state.manual_answer and state.pricing_answer
        - Synthesize whatever we got into raw_answer
        - Mark hybrid_partial_success if at least one succeeded
        """
        logger.info("Node: hybrid_agent - Running both manual and pricing agents")
        
        # Run both agents concurrently
        manual_state = state.model_copy(deep=True)
        pricing_state = state.model_copy(deep=True)
        
        try:
            # Use asyncio.gather to run both agents in parallel
            # return_exceptions=True means failures don't crash the whole thing
            manual_result, pricing_result = await asyncio.gather(
                self.manual_agent.answer(manual_state),
                self.pricing_agent.get_pricing(pricing_state),
                return_exceptions=True
            )
            
            # Process manual agent result
            manual_success = False
            if isinstance(manual_result, AgentState) and manual_result.raw_answer:
                state.manual_answer = manual_result.raw_answer
                state.retrieved_chunks = manual_result.retrieved_chunks
                state.retrieval_scores = manual_result.retrieval_scores
                state.pinecone_namespace = manual_result.pinecone_namespace
                manual_success = bool(manual_result.retrieved_chunks)
                logger.info(f"Hybrid: Manual agent returned answer (chunks: {len(manual_result.retrieved_chunks)})")
            elif isinstance(manual_result, Exception):
                logger.warning(f"Hybrid: Manual agent failed: {manual_result}")
                state.manual_answer = None
            else:
                logger.warning("Hybrid: Manual agent returned no answer")
                state.manual_answer = None
            
            # Process pricing agent result
            pricing_success = False
            if isinstance(pricing_result, AgentState) and pricing_result.price_info:
                state.pricing_answer = pricing_result.raw_answer
                state.price_info = pricing_result.price_info
                pricing_success = not pricing_result.price_info.get("error")
                logger.info(f"Hybrid: Pricing agent returned data (listings: {pricing_result.price_info.get('total_listings', 0)})")
            elif isinstance(pricing_result, Exception):
                logger.warning(f"Hybrid: Pricing agent failed: {pricing_result}")
                state.pricing_answer = None
            else:
                logger.warning("Hybrid: Pricing agent returned no data")
                state.pricing_answer = None
            
            # Mark partial success if at least one agent succeeded
            state.hybrid_partial_success = manual_success or pricing_success
            
            # Synthesize the combined answer
            state.raw_answer = self._synthesize_hybrid_answer(state)
            
            # Set confidence based on what we got
            if manual_success and pricing_success:
                state.confidence_score = 0.9
            elif manual_success or pricing_success:
                state.confidence_score = 0.7  # Partial success
            else:
                state.confidence_score = 0.2  # Both failed
            
            # Reduce confidence if using mock pricing data
            if state.price_info and state.price_info.get("source") == "mock":
                state.confidence_score *= 0.85
                logger.info("Hybrid: Using mock pricing data, reduced confidence")
            
            state.agent_path.append("hybrid_agent")
            if manual_success:
                state.agent_path.append("manual_agent")
            if pricing_success:
                state.agent_path.append("reverb_agent")
            
            logger.info(f"Hybrid complete: manual={manual_success}, pricing={pricing_success}")
            
        except Exception as e:
            logger.error(f"Hybrid agent failed: {e}")
            state.error = f"Hybrid agent error: {str(e)}"
            state.confidence_score = 0.1
        
        return state
    
    def _synthesize_hybrid_answer(self, state: AgentState) -> str:
        """
        Combine manual and pricing answers into a single response.
        
        Strategy:
        - If both available: Combine them nicely
        - If only manual: Return manual answer + note about pricing
        - If only pricing: Acknowledge manual unavailability + return pricing
        - If neither: Return helpful message
        """
        parts = []
        
        # Check if manual answer indicates we don't have the manual
        manual_unavailable = False
        if state.manual_answer:
            unavailable_phrases = [
                "don't have a manual",
                "don't have the manual",
                "no manual",
                "manual not indexed",
                "manual isn't available"
            ]
            manual_unavailable = any(phrase in state.manual_answer.lower() for phrase in unavailable_phrases)
        
        # Add manual answer if available AND useful
        if state.manual_answer and state.retrieved_chunks and not manual_unavailable:
            parts.append(state.manual_answer)
        elif manual_unavailable and state.price_info and not state.price_info.get("error"):
            # Manual unavailable but we have pricing - acknowledge the limitation cleanly
            # Don't just concatenate "I don't have a manual" with pricing
            parts.append(
                f"I don't currently have the **{state.pedal_name}** manual indexed, "
                f"so I can't provide details about its features or specifications yet."
            )
        elif state.manual_answer and not manual_unavailable:
            # Have answer without chunks - could be explaining why no info found
            parts.append(state.manual_answer)
        
        # Add pricing answer if available
        has_pricing = state.price_info and not state.price_info.get("error")
        if has_pricing:
            if parts:
                parts.append("\n\n**Current Market Pricing:**\n")
            
            if state.pricing_answer:
                parts.append(state.pricing_answer)
            else:
                # Format pricing from price_info directly
                price_info = state.price_info
                pricing_text = (
                    f"Based on {price_info['total_listings']} active listings on Reverb, "
                    f"the **{state.pedal_name}** typically sells for **${price_info['avg_price']:.2f}**. "
                    f"Prices range from ${price_info['min_price']:.2f} to ${price_info['max_price']:.2f}, "
                    f"depending on condition."
                )
                parts.append(pricing_text)
            
            # Add source note for pricing
            source = state.price_info.get("source", "unknown")
            if source == "mock":
                parts.append("\n\n*Note: Using estimated pricing data. Live Reverb API data unavailable.*")
        
        # Handle case where we got nothing useful
        if not parts:
            return (
                f"I couldn't find complete information about the {state.pedal_name}. "
                f"The manual search didn't return relevant results, and pricing data was unavailable."
            )
        
        return "\n".join(parts)

    async def _quality_check_node(self, state: AgentState) -> AgentState:
        """Quality check node: Validate answer."""
        logger.info("Node: quality_check") 
        return await self.quality_check.validate(state)
    
    async def _synthesizer_node(self, state: AgentState) -> AgentState:
        """Synthesizer node: Format final response."""
        logger.info("Node: synthesizer")
        
        # For hybrid queries with partial success, the answer is already synthesized
        # For other queries, use raw_answer as final_answer
        state.final_answer = state.raw_answer
        state.agent_path.append("synthesizer")
        
        return state
    
    async def _fallback_node(self, state: AgentState) -> AgentState:
        """Fallback node: Handle rejected answers."""
        logger.info("Node: fallback")
        
        state.final_answer = get_safe_fallback_response(state)
        state.agent_path.append("fallback")
        
        return state
    
    
    # ROUTING LOGIC
    def _route_after_router(self, state: AgentState) -> str:
        """
        Determine next node after router.
        
        NOTE: Until explainer_agent is implemented, EXPLANATION queries
        are routed to manual_agent as a fallback.
        """
        if state.intent == AgentIntent.MANUAL_QUESTION:
            return "manual_agent"
        
        elif state.intent == AgentIntent.EXPLANATION:
            # TODO: Implement dedicated explainer_agent
            # For now, use manual_agent - it can still provide factual info
            logger.info("EXPLANATION intent routed to manual_agent (explainer not implemented)")
            return "explanation"
        
        elif state.intent == AgentIntent.HYBRID:
            # Start with manual for hybrid queries
            return "hybrid"
            
        elif state.intent == AgentIntent.PRICING:
            return "pricing_agent"
        
        elif state.intent == AgentIntent.CASUAL:
            # Casual conversation - answer already set in router, go straight to synthesizer
            return "casual"
        
        else:
            # Default fallback
            logger.warning(f"Unknown intent: {state.intent}, defaulting to manual_agent")
            return "manual_agent"  

    def _route_after_quality_check(self, state: AgentState) -> str:
        """Determine next node after quality check."""
        if should_reject_answer(state):
            return "fallback"
        else:
            return "synthesizer"
        

    # EXECUTION
    async def run(self, state: AgentState) -> AgentState:
        """
        Run the complete workflow.
        
        Args:
            state: Initial state with query and pedal_name
        
        Returns:
            Final state with answer
        """

        logger.info(f"Starting workflow for query: {state.query[:100]}")
        logger.debug(f"[WORKFLOW] Input pedal_name: '{state.pedal_name}'")

        try:
            # Execute graph
            raw_state = await self.graph.ainvoke(state)
            final_state = AgentState.model_validate(raw_state)

            # Debug log: Show retrieval status
            logger.debug(
                f"[WORKFLOW] Retrieval status:\n"
                f"  - Pedal: '{final_state.pedal_name}'\n"
                f"  - Namespace: '{final_state.pinecone_namespace}'\n"
                f"  - Chunks retrieved: {len(final_state.retrieved_chunks)}\n"
                f"  - Retrieval attempted: {bool(final_state.pinecone_namespace)}"
            )
            
            # Debug log: Show quality check status 
            logger.debug(
                f"[WORKFLOW] Quality status:\n"
                f"  - Hallucination flag: {final_state.hallucination_flag}\n"
                f"  - Confidence: {final_state.confidence_score:.2f}\n"
                f"  - Needs review: {final_state.needs_human_review}"
            )
            
            logger.info(
                f"Workflow complete: {' → '.join(final_state.agent_path)}"
            )
            
            return final_state
            
        except Exception as e:
            logger.error(f"Workflow failed: {e}")
            
            # Return state with error
            state.error = f"Workflow error: {str(e)}"
            state.final_answer = "I encountered an error processing your request."
            
            return state

        
# CONVENIENCE FUNCTIONS
async def create_pedalbot_graph(
    voyageai_api_key: str,
    groq_api_key: str,
    pinecone_api_key: str,
    pinecone_index_name: str,
    reverb_api_key: str = None
) -> PedalBotGraph:
    """
    Create a complete PedalBot graph with all agents.
    
    Args:
        groq_api_key: Groq API key
        pinecone_api_key: Pinecone API key
        pinecone_index_name: Pinecone index name
    
    Returns:
        Configured PedalBotGraph
    """
    from backend.services.pinecone_client import PineconeClient
    from backend.services.embeddings import EmbeddingService

    # Initialize services
    pinecone_client = PineconeClient(
        api_key=pinecone_api_key,
        index_name=pinecone_index_name
    )
    
    embeddings_service = EmbeddingService(
        api_key=voyageai_api_key,
        model="voyage-3.5-lite"
    )

    # Initialize agents
    router = RouterAgent(
        api_key=groq_api_key,
        model="llama-3.1-8b-instant"
    )
    
    manual_agent = ManualAgent(
        groq_api_key=groq_api_key,
        pinecone_client=pinecone_client,
        embeddings_service=embeddings_service,
        model="llama-3.3-70b-versatile"
    )

    pricing_agent = PricingAgent(
        reverb_api_key=reverb_api_key
    )

    quality_check = QualityCheckAgent(
        api_key=groq_api_key,
        model="llama-3.1-8b-instant"
    )

    # Create graph
    graph = PedalBotGraph(
        router_agent=router,
        manual_agent=manual_agent,
        pricing_agent=pricing_agent,
        quality_check_agent=quality_check
    )
    
    return graph


async def query_pedalbot(query: str, graph: PedalBotGraph,
                        pedal_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Convenience function to query PedalBot.
    
    Args:
        query: User query
        pedal_name: Pedal name
        graph: PedalBotGraph instance
    
    Returns:
        Dict with answer and metadata
    """

    from datetime import datetime, UTC

    # Create initial state
    state = AgentState(
        user_id="temp_user",
        conversation_id="temp_conv",
        query=query,
        pedal_name=pedal_name,
        created_at=datetime.now(UTC)
    )
    
    # Run graph
    final_state = await graph.run(state)
    
    return {
        "answer": final_state.final_answer,
        "intent": final_state.intent.value if final_state.intent else None,
        "confidence": final_state.confidence_score,
        "agent_path": final_state.agent_path,
        "hallucination_flag": final_state.hallucination_flag,
        "error": final_state.error,
    }


# STREAMING SUPPORT
async def stream_pedalbot_response(
    query: str,
    pedal_name: str,
    graph: PedalBotGraph,
):
    """
    Stream PedalBot response token by token.
    
    Yields:
        Dicts with updates as workflow progresses
    """

    from datetime import datetime, UTC
    
    state = AgentState(
        user_id="temp_user",
        conversation_id="temp_conv",
        query=query,
        pedal_name=pedal_name,
        created_at=datetime.now(UTC)
    )

    # Stream through graph
    async for event in graph.graph.astream(state):
        # Yield intermediate results
        if isinstance(event, dict):
            for node_name, node_state in event.items():
                yield {
                    "node": node_name,
                    "state": node_state,
                    "answer_partial": node_state.raw_answer if hasattr(node_state, 'raw_answer')
                    else None
                }
