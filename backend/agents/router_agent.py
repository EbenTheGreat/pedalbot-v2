"""
Router Agent: Intent classification and routing logic.

Determines which agent(s) to invoke based on user query.
"""
from typing import Dict, Optional, Any
import logging 
from enum import Enum
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage


from backend.state import AgentIntent, AgentState

logger = logging.getLogger(__name__)

class RouterAgent:
    """
    Routes queries to appropriate specialist agents.
    
    Uses Groq for fast, cheap intent classification.
    
    Routes:
    - Manual questions → ManualAgent
    - Pricing queries → PricingAgent
    - Explanations → ExplainerAgent
    - Complex queries → Multiple agents (HYBRID)
    """

    SYSTEM_PROMPT = """
You are a routing agent for PedalBot, a guitar pedal assistant.

Your task is to classify the user's query and decide whether the pedal manual MUST be consulted.

INTENTS (choose EXACTLY ONE):

1. MANUAL_QUESTION  
Questions that can ONLY be answered from the pedal manual, specs, or internal effects list.
Examples:  
- "What's the input impedance?"  
- "Does it have true bypass?"
- "List the drive pedals available"
- "What effects does it include?"
- "What amp models are built in?"
- "How many presets can it store?"
- "What are the power requirements?"
- "List all the effects types"
- "What distortion/overdrive options does it have?"

2. PRICING  
Questions about market price, value, or availability.
Examples:  
- "How much is this?"  
- "What's a fair price?"  
- "Where can I buy one?"
- "I want to buy 3"
- "Looking to purchase this pedal"

3. EXPLANATION  
Questions about tone, sound character, or usage advice that don't require manual lookup.
Examples:  
- "What does this pedal sound like?"  
- "Where should it go in my chain?"
- "How do I dial in a blues tone?"

4. HYBRID  
Queries that combine multiple intents (e.g., manual + pricing, manual + explanation).
Examples:  
- "Is this pedal worth $100?" (pricing + value judgment)
- "Compare the specs and tone to a Boss DS-1" (manual + explanation)
- "How do I turn it on and I want to buy 3" (manual + pricing)
- "What effects does it have and what's the price?" (manual + pricing)
- "Can it do metal tones and where can I buy one?" (explanation + pricing)

CRITICAL CLASSIFICATION RULES:
- If the user asks to "list", "show", "what are", or "how many" effects/features → MANUAL_QUESTION
- If the user asks about built-in effects, amp models, or presets → MANUAL_QUESTION  
- If the user uses musician slang like "drive pedals", "dirt", "modulation" → MANUAL_QUESTION
- If the answer exists in the product manual or spec sheet → MANUAL_QUESTION
- Only use EXPLANATION for subjective tone/feel questions that aren't documented
- **If query contains BOTH a usage/feature question AND purchasing keywords (buy, purchase, price, cost) → HYBRID**
- Purchasing keywords: "buy", "purchase", "want to buy", "looking to buy", "where to buy", "I want", "get one"

OUTPUT RULES (MANDATORY):
- Respond with ONLY a valid JSON object.
- Do NOT include explanations outside JSON.
- "intent" MUST be one of: MANUAL_QUESTION | PRICING | EXPLANATION | HYBRID
- If pedal name is unclear, set "pedal_name" to null.
- "requires_retrieval" MUST be true if the answer depends on the manual or internal effects list.
- The "confidence" field MUST be between 0.0 and 1.0.
- Choose the most appropriate intent. Do not hedge.

OUTPUT FORMAT:
{
  "intent": "MANUAL_QUESTION",
  "pedal_name": "Zoom G3Xn",
  "requires_retrieval": true,
  "confidence": 0.95,
  "reasoning": "User is asking for a list of built-in drive effects, which are documented in the manual."
}
"""

    def __init__(self,
                api_key: str, 
                model: str="llama-3.1-8b-instant",
                temperature: float = 0.0,
                ):
        """
        Initialize router agent.
        
        Args:
            api_key: OpenAI API key
            model: Model to use (llama-3.1-8b-instant is fast and cheap)
            temperature: Low temp for consistent routing
        """

        self.llm = ChatGroq(
            api_key=api_key,
            model=model,
            temperature=temperature,
            max_tokens=200
        )
        self.model = model
        self.temperature = temperature

    async def route(self, state: AgentState) -> AgentState:
        """
        Classify query intent and update state.
        
        Args:
            state: Current agent state with query
        
        Returns:
            Updated state with intent and routing info
        """ 

        logger.info(f"Routing query: {state.query[:100]}")

        try:
            # PREPROCESSING: Normalize query before routing
            from backend.services.query_preprocessor import QueryPreprocessor
            
            preprocessor = QueryPreprocessor()
            preprocess_result = preprocessor.preprocess(state.query)
            
            # Update state with preprocessing results
            state.original_query = preprocess_result.original_query
            state.normalized_query = preprocess_result.normalized_query
            state.typos_corrected = preprocess_result.typos_corrected
            state.sub_questions = preprocess_result.sub_questions
            state.has_multi_questions = preprocess_result.has_multi_questions
            
            # Log preprocessing results
            if preprocess_result.typos_corrected:
                logger.info(
                    f"[ROUTER] Corrected {len(preprocess_result.typos_corrected)} typos: "
                    f"{[(t['original'], t['corrected']) for t in preprocess_result.typos_corrected[:3]]}"
                )
            if preprocess_result.has_multi_questions:
                logger.info(
                    f"[ROUTER] Detected multi-question query with {len(preprocess_result.sub_questions)} parts"
                )
            
            # CASUAL CONVERSATION DETECTION
            # Handle greetings and casual chat before routing to specialist agents
            query_lower = state.query.lower().strip()
            casual_patterns = [
                'hi', 'hello', 'hey', 'howdy', 'sup', 'yo',
                'how are you', 'how r u', 'how are you doing', 
                'whats up', "what's up", 'how do you do',
                'good morning', 'good afternoon', 'good evening',
                'nice to meet you', 'pleasure to meet you'
            ]
            
            is_casual = any(
                query_lower == pattern or 
                query_lower.startswith(pattern + ' ') or
                query_lower.endswith(' ' + pattern) or
                ' ' + pattern + ' ' in query_lower
                for pattern in casual_patterns
            )
            
            if is_casual:
                logger.info("[ROUTER] Detected casual conversation - responding warmly")
                state.intent = AgentIntent.CASUAL
                state.confidence_score = 1.0
                state.agent_path.append("router")
                state.raw_answer = (
                    "I'm here to help with your guitar pedal questions! "
                    "What would you like to know about the manual?"
                )
                state.final_answer = state.raw_answer
                return state
            
            # Use normalized query for routing
            query_for_routing = preprocess_result.normalized_query
            
            # Build Prompt
            user_prompt = self._build_user_prompt(state, query_for_routing)

            # Call LLM (using LangChain for LangSmith tracing)
            messages = [
                SystemMessage(content=self.SYSTEM_PROMPT),
                HumanMessage(content=user_prompt)
            ]
            response = await self.llm.ainvoke(messages)

            # Parse response
            raw_content = response.content

            if raw_content is None:
                raise ValueError("LLM returned empty response content")
            
            result = self._parse_response(raw_content)


            # Update State
            state.intent = AgentIntent(result["intent"].lower())
            state.pedal_name = result.get("pedal_name", state.pedal_name)
            state.confidence_score = result.get("confidence", 0.0)
            
            # Boost confidence if preprocessing helped significantly
            if len(preprocess_result.typos_corrected) >= 2:
                state.confidence_score = min(0.95, state.confidence_score + 0.05)
            
            state.agent_path.append("router")

            logger.info(
                f"Routed to {state.intent.value} "
                f"(confidence: {state.confidence_score:.2f})"
            )

            return state
        
        except Exception as e:
            logger.error(f"Routing failed: {e}")

            # Fallback: Default to manual question but check for obvious pricing keywords
            from backend.state import FallbackReason
            
            # Enhanced keyword heuristic for fallback
            query_lower = state.query.lower()
            
            # Expanded pricing keywords to catch purchasing intent
            pricing_keywords = [
                "price", "cost", "buy", "purchase", "sell", "worth", "value", 
                "cheapest", "expensive", "want to buy", "looking to buy", 
                "get one", "get 3", "i want"
            ]
            
            # Usage/manual keywords
            manual_keywords = [
                "how", "what", "setting", "manual", "use", "connect", 
                "turn on", "put it on", "set up", "install", "does it"
            ]
            
            has_pricing = any(k in query_lower for k in pricing_keywords)
            has_manual = any(k in query_lower for k in manual_keywords)
            
            if has_pricing and has_manual:
                # Query has BOTH pricing and manual/usage questions → HYBRID
                state.intent = AgentIntent.HYBRID
                logger.info("[ROUTER FALLBACK] Detected HYBRID: pricing + manual keywords present")
            elif has_pricing:
                # Only pricing keywords
                state.intent = AgentIntent.PRICING
            else:
                # Default to manual question
                state.intent = AgentIntent.MANUAL_QUESTION
                
            state.confidence_score = 0.5
            state.error = f"Routing error: {str(e)}"
            state.fallback_reason = FallbackReason.ROUTER_ERROR
            state.agent_path.append("router_fallback")
            
            return state
        
    
    def _build_user_prompt(self, state: AgentState, query: Optional[str] = None) -> str:
        """Build user prompt with context and conversation history."""
        prompt_parts = []
        
        # Use provided query or fall back to state.query
        current_query = query if query is not None else state.query
        
        # Add conversation history if available
        if state.conversation_history:
            prompt_parts.append("Recent conversation context:")
            for msg in state.conversation_history[-4:]:  # Last 2 exchanges (4 messages)
                role = msg.get("role", "user")
                content = msg.get("content", "")
                # Truncate long messages
                truncated = content[:150] + "..." if len(content) > 150 else content
                prompt_parts.append(f"{role.capitalize()}: {truncated}")
            prompt_parts.append("")  # Empty line separator
        
        # Add current query (normalized if available)
        prompt_parts.append(f"Current query: {current_query}")

        if state.pedal_name:
            prompt_parts.append(f"Pedal context: {state.pedal_name}")

        return "\n".join(prompt_parts)

    
    def _parse_response(self, content: str) -> Dict[str, Any]:
        """
        Parse LLM response into structured intent.
        
        Args:
            content: Raw LLM response
        
        Returns:
            Dict with intent, pedal_name, confidence, reasoning
        """

        import json 
        import re

        # Clean up response (remove markdown code blocks if present)
        content = content.strip()
        content = re.sub(r'^```json\s*', '', content)
        content = re.sub(r'\s*```$', '', content)

        try:
            result = json.loads(content)

            # Validate intent
            intent = result.get("intent", "MANUAL_QUESTION").upper()
            if intent not in ["MANUAL_QUESTION", "PRICING", "EXPLANATION", "HYBRID"]:
                logger.warning(f"Invalid intent: {intent}. Defaulting to MANUAL_QUESTION")
                intent = "MANUAL_QUESTION"
            
            result["intent"] = intent
            
            return result
        
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse routing response: {e}")
            logger.error(f"Raw content: {content}")

            # Fallback: Try to extract intent with regex
            intent_match = re.search(r'"intent"\s*:\s*"(\w+)"', content)
            if intent_match:
                return {
                    "intent": intent_match.group(1),
                    "pedal_name": None,
                    "confidence": 0.7,
                    "reasoning": "Parsed with fallback regex"
                }
            
            # Ultimate fallback
            return {
                "intent": "MANUAL_QUESTION",
                "pedal_name": None,
                "confidence": 0.5,
                "reasoning": "Failed to parse, defaulting to manual question"
            }
        

    async def extract_pedal_name(self, query: str) -> Optional[str]:
        """
        Extract pedal name from query if not provided.
        
        Args:
            query: User query
        
        Returns:
            Extracted pedal name or None
        """
        import re

        # Simple regex patterns for common pedals
        patterns = [
            r'\b(boss\s+(?:ds-?1|ts-?9|bd-?2|od-?3|ce-?5))\b',
            r'\b(ibanez\s+(?:ts-?9|ts-?808))\b',
            r'\b(mxr\s+(?:phase\s*90|distortion\s*\+))\b',
            r'\b(electro[\s-]?harmonix\s+(?:big\s+muff|soul\s+food))\b',
            r'\b(strymon\s+(?:timeline|bigsky|flint))\b',
        ]
        
        query_lower = query.lower()
        for pattern in patterns:
            match = re.search(pattern, query_lower, re.IGNORECASE)
            if match:
                return match.group(1).title()
        
        return None


# HELPER FUNCTIONS
async def route_query(query: str,
                    pedal_name: Optional[str],
                    router: RouterAgent,
                    ) -> AgentState:
    """
    Convenience function to route a query.
    
    Args:
        query: User query
        pedal_name: Known pedal name (or None)
        router: RouterAgent instance
    
    Returns:
        AgentState with routing information
    """

    from datetime import datetime, UTC

    # Create initial state
    state = AgentState(
        user_id="temp_user",
        conversation_id="temp_conv",
        query=query,
        pedal_name=pedal_name or "",
        created_at=datetime.now(UTC)
    )
    
    # Route
    state = await router.route(state)
    
    return state


def get_next_agents(state: AgentState) -> list[str]:
    """
    Determine which agents to call based on intent.
    
    Args:
        state: Routed state
    
    Returns:
        List of agent names to invoke
    """
    if state.intent is None:
        logger.warning("State intent is None, defaulting to manual_agent")
        return ["manual_agent"]
    
    intent_to_agents = {
        AgentIntent.MANUAL_QUESTION: ["manual_agent"],
        AgentIntent.PRICING: ["pricing_agent"],
        AgentIntent.EXPLANATION: ["explainer_agent"],
        AgentIntent.HYBRID: ["manual_agent", "pricing_agent"],
    }
    
    return intent_to_agents.get(state.intent, ["manual_agent"])


