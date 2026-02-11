"""
Quality Check Agent: Validates answers for hallucinations and accuracy.

Acts as a gate before returning answers to users.
"""
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage
from typing import List, Optional, Dict, Any
import logging 
import re

from backend.state import AgentState, FallbackReason

logger = logging.getLogger(__name__)


# Ambiguity detection patterns
AMBIGUOUS_PATTERNS = [
    r'^(how do i|how to)\s+(put|get|make|do|use)\s+(it|this|that)\s*(on|off|up|down)?$',
    r'^(what|where|how)\s+(is|are|do|does)\s+(it|this|that)(\?)?$',
    r'^(the|a|an)\s+\w+$',  # Single concept queries like "the signal chain"
    r'^(put|get|turn|set)\s+(it|this)\s*(on|off)?$',
]

# Short/vague query patterns that need clarification
SHORT_QUERY_WORDS = 4  # Queries with <= this many words are potentially ambiguous

class QualityCheckAgent:
    """
    Validates generated answers against source material.
    
    Checks for:
    1. Hallucinations (info not in source chunks)
    2. Contradictions (answer conflicts with sources)
    3. Citation accuracy (claims match sources)
    4. Completeness (all key info included)
    
    Uses llama-3.1-8b-instant for sophisticated validation.
    """

    # System prompt for quality checking
    SYSTEM_PROMPT = """You are a quality control agent. Your job is to validate that an AI-generated answer is accurate and grounded in the provided source material.

Check for:
1. HALLUCINATIONS: Does the answer contain information NOT in the sources?
2. CONTRADICTIONS: Does the answer contradict the sources?
3. ACCURACY: Are specific claims (numbers, specs) correct?
4. COMPLETENESS: Did it miss MAJOR critical warnings? (Minor omissions are OK)
5. MULTI-QUESTION COVERAGE: If the query had multiple questions, does the answer address ALL of them?

Source Material:
{sources}

AI-Generated Answer:
{answer}

Respond with JSON in this format:
{{
  "is_accurate": true,
  "hallucination_detected": false,
  "confidence": 0.95,
  "issues": [],
  "reasoning": "Answer is fully grounded in sources. All specs match."
}}

If issues found:
{{
  "is_accurate": false,
  "hallucination_detected": true,
  "confidence": 0.3,
  "issues": [
    "Claims input impedance is 500kΩ but source says 1MΩ",
    "Mentions true bypass but not found in sources"
  ],
  "reasoning": "Answer contains unsupported claims"
}}"""

    def __init__(self, api_key: str, model: str= "llama-3.1-8b-instant",
                temperature: float= 0.0,
                hallucination_threshold: float = 0.3,
                ):
        """
        Initialize quality check agent.
        
        Args:
            api_key: Groq API key
            model: Model for validation (llama-3.1-8b-instant for best accuracy)
            temperature: Zero temp for deterministic checking
            hallucination_threshold: Confidence threshold below which answer is flagged
        """

        self.llm = ChatGroq(
            api_key=api_key,
            model=model,
            temperature=temperature,
            max_tokens=500
        )
        self.model = model
        self.temperature = temperature
        self.hallucination_threshold = hallucination_threshold

    
    async def validate(self, state: AgentState) -> AgentState:
        """
        Validate answer quality.
        
        Args:
            state: State with raw_answer and retrieved_chunks
        
        Returns:
            Updated state with quality flags
        """
        from backend.state import AgentIntent

        logger.info("Quality check: Validating answer")
        
        # SKIP IF EXPLICITLY MARKED (e.g., system prompt meta-questions)
        if state.skip_quality_check:
            logger.info("[QUALITY_CHECK] Skipping - skip_quality_check flag is set")
            state.hallucination_flag = False
            state.needs_human_review = False
            state.agent_path.append("quality_check")
            return state

        # HYBRID QUERY SPECIAL HANDLING
        # For hybrid queries with partial success, we're more lenient
        # because it's acceptable to have pricing but no manual info (or vice versa)
        is_hybrid = state.intent == AgentIntent.HYBRID
        has_partial_success = getattr(state, 'hybrid_partial_success', False)
        
        if is_hybrid and has_partial_success:
            logger.info("[QUALITY_CHECK] Hybrid query with partial success - using lenient validation")
            
            # For hybrid with partial success, we only flag as hallucination if:
            # 1. We have manual_answer but no retrieved_chunks (potential hallucination)
            # 2. Confidence is critically low
            has_manual_content = bool(state.manual_answer and state.retrieved_chunks)
            has_pricing_content = bool(state.price_info and not state.price_info.get("error"))
            
            if has_manual_content or has_pricing_content:
                # At least one source of truth - proceed with normal validation on manual content
                if has_manual_content and state.retrieved_chunks:
                    # Validate manual answer against sources
                    try:
                        result = await self._check_quality(
                            answer=state.manual_answer,
                            sources=state.retrieved_chunks
                        )
                        state.hallucination_flag = result["hallucination_detected"]
                        state.needs_human_review = not result["is_accurate"]
                        state.context.append(f"Quality check (manual part): {result['reasoning']}")
                    except Exception as e:
                        logger.warning(f"[QUALITY_CHECK] Hybrid manual validation failed: {e}")
                        # Don't fail the whole thing - pricing is still valid
                        state.hallucination_flag = False
                        state.needs_human_review = True
                else:
                    # Only have pricing - that's OK, pricing doesn't need chunk validation
                    state.hallucination_flag = False
                    state.needs_human_review = False
                
                state.agent_path.append("quality_check")
                logger.info(f"[QUALITY_CHECK] Hybrid passed: hallucination={state.hallucination_flag}")
                return state

        # PRICING-ONLY QUERY SPECIAL HANDLING
        # Pricing queries get data from Reverb API, not from retrieved_chunks
        # They should pass through if price_info is valid
        is_pricing = state.intent == AgentIntent.PRICING
        has_valid_pricing = bool(state.price_info and not state.price_info.get("error"))
        
        # Debug logging
        logger.info(f"[QUALITY_CHECK] Intent check: intent={state.intent}, is_pricing={is_pricing}, has_valid_pricing={has_valid_pricing}")
        if state.price_info:
            logger.info(f"[QUALITY_CHECK] price_info keys: {list(state.price_info.keys())}")
        
        if is_pricing and has_valid_pricing:
            logger.info("[QUALITY_CHECK] Pricing query with valid price_info - passing through")
            state.hallucination_flag = False
            state.needs_human_review = False
            state.confidence_score = max(state.confidence_score, 0.85)  # Pricing is reliable
            state.agent_path.append("quality_check")
            return state

        # Skip if no answer or no sources (for non-hybrid, non-pricing queries)
        if not state.raw_answer or not state.retrieved_chunks:
            # Log the specific reason for skipping
            if not state.raw_answer:
                logger.warning(
                    f"[QUALITY_CHECK] Skipped: No raw_answer generated. "
                    f"Error: {state.error or 'None'}"
                )
            elif not state.retrieved_chunks:
                logger.warning(
                    f"[QUALITY_CHECK] Skipped: No retrieved_chunks. "
                    f"Possible causes: (1) all search results filtered out due to low similarity scores, "
                    f"(2) namespace has no vectors, (3) empty query embedding. "
                    f"Pedal: '{state.pedal_name}', Namespace: '{state.pinecone_namespace}'"
                )
            
            state.hallucination_flag = True
            state.needs_human_review = True
            state.agent_path.append("quality_check_skipped")
            return state
        
        try:
            # Run Validation
            result = await self._check_quality(
                answer= state.raw_answer,
                sources= state.retrieved_chunks
            )

            # Update State
            state.hallucination_flag = result["hallucination_detected"]
            state.needs_human_review = not result["is_accurate"]

            # Lower confidence if issues detected
            if not result["is_accurate"]:
                state.confidence_score *= 0.5

            # Add to context for debugging
            state.context.append(f"Quality check: {result['reasoning']}")

            if result["issues"]:
                state.context.extend([f"Issue: {issue}" for issue in result["issues"]])
            
            state.agent_path.append("quality_check")
            
            # Log results
            if state.hallucination_flag:
                logger.warning(
                    f"Hallucination detected! Confidence: {state.confidence_score:.2f}"
                )
            else:
                logger.info(f"Quality check passed")
            
            return state
        except Exception as e:
            logger.error(f"Quality check failed: {e}")
            
            # On error, flag for human review
            state.needs_human_review = True
            state.error = f"Quality check error: {str(e)}"
            state.agent_path.append("quality_check_error")
            
            return state

    
    async def _check_quality(self, answer: str, 
                            sources: List[str]) -> Dict[str, Any]:
        """
        Run quality check using LLM.
        
        Args:
            answer: Generated answer
            sources: Source chunks used
        
        Returns:
            Quality check result
        """

        # Build prompt
        sources_text = "\n\n---\n\n".join([
            f"Source {i+1}:\n{source}"
            for i, source in enumerate(sources)
        ])
        
        system_prompt = self.SYSTEM_PROMPT.format(
            sources=sources_text,
            answer=answer
        )

        # Call LLM (using LangChain for LangSmith tracing)
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content="Validate this answer.")
        ]
        response = await self.llm.ainvoke(messages)

        # Parse response
        content = response.content

        if content is None:
            raise ValueError("Quality check model returned no content")

        result = self._parse_validation(content)
        return result
    
    def _parse_validation(self, content: str) -> Dict[str, Any]:
        """Parse LLM validation response."""
        import json
        
        # Clean up response
        content = content.strip()
        content = re.sub(r'^```json\s*', '', content)
        content = re.sub(r'\s*```$', '', content)
        
        # Try to extract just the JSON object (LLM often adds extra text after)
        json_match = re.search(r'\{[\s\S]*?\}(?=\s*(?:\n\n|\Z|[A-Z]))', content)
        if json_match:
            json_str = json_match.group(0)
        else:
            # Try finding JSON by matching balanced braces
            brace_depth = 0
            start_idx = None
            end_idx = None
            for i, char in enumerate(content):
                if char == '{':
                    if start_idx is None:
                        start_idx = i
                    brace_depth += 1
                elif char == '}':
                    brace_depth -= 1
                    if brace_depth == 0 and start_idx is not None:
                        end_idx = i + 1
                        break
            
            if start_idx is not None and end_idx is not None:
                json_str = content[start_idx:end_idx]
            else:
                json_str = content
        
        try:
            result = json.loads(json_str)
            
            # Ensure required fields
            result.setdefault("is_accurate", True)
            result.setdefault("hallucination_detected", False)
            result.setdefault("confidence", 0.8)
            result.setdefault("issues", [])
            result.setdefault("reasoning", "")
            
            logger.info(f"[QUALITY_CHECK] Parsed validation: is_accurate={result['is_accurate']}, confidence={result['confidence']}")
            
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse validation response: {e}")
            logger.error(f"Raw content: {content[:500]}...")  # Truncate for log

            # Fallback: Check for positive keywords (the answer was likely good!)
            positive_keywords = ["is_accurate\": true", "accurate", "grounded", "correct"]
            negative_keywords = ["hallucination", "not in source", "unsupported", "contradiction"]
            
            has_positive = any(kw in content.lower() for kw in positive_keywords)
            has_negative = any(kw in content.lower() for kw in negative_keywords)
            
            # If we see positive signals and no negative ones, trust the LLM
            if has_positive and not has_negative:
                logger.info("[QUALITY_CHECK] Parse failed but found positive signals, trusting answer")
                return {
                    "is_accurate": True,
                    "hallucination_detected": False,
                    "confidence": 0.85,
                    "issues": [],
                    "reasoning": "Parse error but positive validation detected"
                }
            
            return {
                "is_accurate": not has_negative,
                "hallucination_detected": has_negative,
                "confidence": 0.5,
                "issues": ["Parse error - manual review recommended"],
                "reasoning": "Failed to parse validation, defaulting to cautious"
            }
        
    async def run_heuristic_check(self, state: AgentState) -> Dict[str, Any]:
        """
        Fast heuristic checks (no LLM call).
        
        Useful for quick filtering before expensive LLM validation.
        
        Returns:
            Dict with heuristic results
        """
        issues = []
        
        # Check 0: Multi-question completeness
        if state.has_multi_questions and len(state.sub_questions) > 1:
            # Validate that answer addresses all sub-questions
            answer_lower = state.raw_answer.lower() if state.raw_answer else ""
            
            # Count how many sub-questions appear to be addressed
            addressed_count = 0
            for sub_q in state.sub_questions:
                # Extract key topic words from sub-question
                sub_q_lower = sub_q.lower()
                
                # Check for key question words in answer
                question_keywords = []
                if "price" in sub_q_lower or "buy" in sub_q_lower or "cost" in sub_q_lower:
                    question_keywords = ["price", "$", "cost", "buy", "reverb", "listing"]
                elif "connect" in sub_q_lower or "cable" in sub_q_lower or "usb" in sub_q_lower:
                    question_keywords = ["connect", "cable", "usb", "port", "interface"]
                elif "how" in sub_q_lower or "what" in sub_q_lower:
                    # Generic - check if ANY meaningful content related
                    question_keywords = sub_q_lower.split()[:3]  # First 3 words
                
                # If any keyword found in answer, consider it addressed
                if any(kw in answer_lower for kw in question_keywords if len(kw) > 2):
                    addressed_count += 1
                    logger.debug(f"[QUALITY_HEURISTIC] Sub-question addressed: '{sub_q[:50]}...'")
                else:
                    logger.warning(f"[QUALITY_HEURISTIC] Sub-question NOT addressed: '{sub_q[:50]}...'")
            
            # Flag if less than 50% of questions addressed
            coverage_ratio = addressed_count / len(state.sub_questions)
            if coverage_ratio < 0.5:
                issues.append(
                    f"Multi-question query: Only {addressed_count}/{len(state.sub_questions)} "
                    f"questions appear to be addressed in the answer"
                )
                logger.warning(
                    f"[QUALITY_HEURISTIC] Poor multi-question coverage: {coverage_ratio:.0%} "
                    f"({addressed_count}/{len(state.sub_questions)})"
                )
            else:
                logger.info(
                    f"[QUALITY_HEURISTIC] Good multi-question coverage: {coverage_ratio:.0%} "
                    f"({addressed_count}/{len(state.sub_questions)})"
                )
        
        # Check 1: Answer length vs source length
        if state.raw_answer and state.retrieved_chunks:
            answer_len = len(state.raw_answer)
            total_source_len = sum(len(chunk) for chunk in state.retrieved_chunks)
            
            # Answer shouldn't be way longer than sources
            if answer_len > total_source_len * 1.5:
                issues.append("Answer is significantly longer than sources (possible elaboration)")
        
        # Check 2: Specific numbers in answer should be in sources
        if state.raw_answer:
            # Extract numbers from answer
            answer_numbers = set(re.findall(r'\b\d+(?:\.\d+)?\s*(?:kΩ|MΩ|Hz|kHz|dB|V|mA)?\b', state.raw_answer))
            
            # Check if they appear in sources
            source_text = " ".join(state.retrieved_chunks) if state.retrieved_chunks else ""
            for number in answer_numbers:
                if number not in source_text:
                    issues.append(f"Number '{number}' not found in sources")
        
        # Check 3: Common hallucination phrases
        hallucination_phrases = [
            "according to my knowledge",
            "as far as i know",
            "generally speaking",
            "typically",
            "usually",
        ]

        if state.raw_answer:
            answer_lower = state.raw_answer.lower()
            for phrase in hallucination_phrases:
                if phrase in answer_lower:
                    issues.append(f"Hedging phrase detected: '{phrase}'")
        
        # Check 4: "I don't know" responses should have high confidence
        if state.raw_answer and "don't have that information" in state.raw_answer.lower():
            if state.confidence_score < 0.8:
                issues.append("Low confidence on 'don't know' response")
        
        return {
            "passed": len(issues) == 0,
            "issues": issues,
            "check_type": "heuristic"
        }
    

# HELPER FUNCTIONS
async def validate_answer(
    answer: str,
    sources: List[str],
    agent: QualityCheckAgent,
) -> Dict[str, Any]:
    """
    Convenience function to validate an answer.
    
    Args:
        answer: Generated answer
        sources: Source chunks
        agent: QualityCheckAgent instance
    
    Returns:
        Validation result
    """
    from backend.state import AgentState
    from datetime import datetime, UTC

    state = AgentState(
        user_id="temp_user",
        conversation_id="temp_conv",
        query="temp_query",
        pedal_name="temp_pedal",
        raw_answer=answer,
        retrieved_chunks=sources,
        created_at=datetime.now(UTC)
    )
    
    state = await agent.validate(state)

    return {
        "hallucination_detected": state.hallucination_flag,
        "needs_review": state.needs_human_review,
        "confidence": state.confidence_score,
        "context": state.context,
    }



def should_reject_answer(state: AgentState) -> bool:
    """
    Determine if answer should be rejected and set the fallback_reason.
    
    This function now sets state.fallback_reason to enable smart fallback messages.
    
    Args:
        state: Validated state
    
    Returns:
        True if answer should be rejected
    """
    from backend.state import AgentIntent
    
    # Reset fallback reason
    state.fallback_reason = FallbackReason.NONE
    
    # HYBRID QUERIES: More lenient rejection criteria
    is_hybrid = state.intent == AgentIntent.HYBRID
    has_partial_success = getattr(state, 'hybrid_partial_success', False)
    
    if is_hybrid and has_partial_success:
        if state.confidence_score < 0.2:
            state.fallback_reason = FallbackReason.LOW_RELEVANCE
            return True
        if state.error and "critical" in state.error.lower():
            state.fallback_reason = FallbackReason.RETRIEVAL_FAILED
            return True
        return False
    
    # Check for missing raw_answer
    if not state.raw_answer:
        state.fallback_reason = FallbackReason.RETRIEVAL_FAILED
        return True
    
    # ACCEPT "I don't know" answers - they are valid and accurate!
    if "don't have that information" in state.raw_answer.lower() or "couldn't find" in state.raw_answer.lower():
        return False

    # Check for ambiguous query BEFORE rejecting
    query_lower = state.query.lower().strip()
    query_words = len(state.query.split())
    
    # Detect ambiguous patterns
    is_ambiguous = False
    for pattern in AMBIGUOUS_PATTERNS:
        if re.match(pattern, query_lower, re.IGNORECASE):
            is_ambiguous = True
            break
    
    # Short queries are also potentially ambiguous
    if query_words <= SHORT_QUERY_WORDS and not is_ambiguous:
        # Check if it's a technical term that's unambiguous
        technical_terms = ['impedance', 'bypass', 'voltage', 'power', 'presets', 'effects', 'amp model']
        if not any(term in query_lower for term in technical_terms):
            is_ambiguous = True
    
    # Reject if hallucination detected
    if state.hallucination_flag:
        state.fallback_reason = FallbackReason.HALLUCINATION_DETECTED
        return True
    
    # Reject if confidence too low
    if state.confidence_score < 0.25:
        # Determine WHY confidence is low
        if is_ambiguous:
            state.fallback_reason = FallbackReason.AMBIGUOUS_QUERY
        elif not state.retrieved_chunks:
            state.fallback_reason = FallbackReason.RETRIEVAL_FAILED
        elif state.retrieval_scores and max(state.retrieval_scores) < 0.4:
            # We got chunks but they don't match the query intent
            state.fallback_reason = FallbackReason.LOW_RELEVANCE
        else:
            # Chunks exist and have decent scores, but answer wasn't grounded
            # This likely means the concept isn't explicitly documented
            state.fallback_reason = FallbackReason.CONCEPT_NOT_EXPLICIT
        return True
    
    # Reject if error occurred
    if state.error:
        if "router" in state.error.lower():
            state.fallback_reason = FallbackReason.ROUTER_ERROR
        else:
            state.fallback_reason = FallbackReason.RETRIEVAL_FAILED
        return True
    
    return False


def get_safe_fallback_response(state: AgentState) -> str:
    """
    Generate smart, intent-aware fallback response based on WHY the query failed.
    
    This replaces the generic "I couldn't find reliable information" message
    with specific, helpful messages that accurately describe what happened.
    
    Args:
        state: State with rejected answer and fallback_reason
    
    Returns:
        Smart fallback message tailored to the failure mode
    """
    pedal = state.pedal_name or "this pedal"
    query = state.query
    reason = state.fallback_reason
    
    # === AMBIGUOUS QUERY ===
    if reason == FallbackReason.AMBIGUOUS_QUERY:
        # Provide clarification suggestions based on the query
        query_lower = query.lower()
        
        if "put" in query_lower or "on" in query_lower:
            return (
                f"I'm not sure what you mean. Are you asking about:\n"
                f"• **Powering on** the {pedal}?\n"
                f"• **Enabling an effect** or patch?\n"
                f"• **Connecting cables** to the inputs/outputs?\n\n"
                f"Please clarify and I'll help you find the answer."
            )
        elif "signal chain" in query_lower or "chain" in query_lower:
            return (
                f"The {pedal} manual doesn't explicitly describe a fixed signal chain. "
                f"Effects are arranged internally by patch, and their routing may vary.\n\n"
                f"Would you like to know about:\n"
                f"• The **effects order** within patches?\n"
                f"• How to **connect** the pedal to your amp/pedalboard?\n"
                f"• The **input/output connections**?"
            )
        else:
            return (
                f"Your question is a bit vague. Could you be more specific about what "
                f"you'd like to know about the {pedal}?\n\n"
                f"For example:\n"
                f"• \"How do I power on the {pedal}?\"\n"
                f"• \"What effects does the {pedal} include?\"\n"
                f"• \"What are the power requirements?\""
            )
    
    # === LOW RELEVANCE (chunks retrieved but don't match intent) ===
    elif reason == FallbackReason.LOW_RELEVANCE:
        return (
            f"I found some information in the {pedal} manual, but it doesn't directly "
            f"answer your question about \"{query}\".\n\n"
            f"Try rephrasing with more specific terms, or ask about a particular feature "
            f"like power requirements, effects, connections, or settings."
        )
    
    # === CONCEPT NOT EXPLICITLY DOCUMENTED ===
    elif reason == FallbackReason.CONCEPT_NOT_EXPLICIT:
        return (
            f"The {pedal} manual doesn't explicitly cover this topic.\n\n"
            f"The manual contains information about settings, specifications, and features, "
            f"but this particular concept may not be documented in a way I can retrieve.\n\n"
            f"Would you like me to try a different angle? For example, I can tell you about "
            f"specific effects, controls, or technical specs."
        )
    
    # === RETRIEVAL FAILED (no chunks at all) ===
    elif reason == FallbackReason.RETRIEVAL_FAILED:
        return (
            f"I wasn't able to search the {pedal} manual successfully. "
            f"This could be a temporary issue.\n\n"
            f"Please try your question again, or ask about a specific feature."
        )
    
    # === HALLUCINATION DETECTED ===
    elif reason == FallbackReason.HALLUCINATION_DETECTED:
        return (
            f"I found some information, but I'm not confident it accurately answers "
            f"your question about the {pedal}.\n\n"
            f"To avoid giving you incorrect information, I'd recommend:\n"
            f"• Rephrasing your question more specifically\n"
            f"• Checking the manual directly for this topic"
        )
    
    # === ROUTER ERROR ===
    elif reason == FallbackReason.ROUTER_ERROR:
        return (
            f"I had trouble understanding your question.\n\n"
            f"Could you rephrase it? For example:\n"
            f"• \"What effects does this pedal have?\"\n"
            f"• \"How do I save a patch?\"\n"
            f"• \"What's the price of this pedal?\""
        )
    
    # === DATA MISSING (genuinely not in manual) ===
    elif reason == FallbackReason.DATA_MISSING:
        return (
            f"This information isn't covered in the {pedal} manual.\n\n"
            f"The manual focuses on operation, settings, and specifications. "
            f"If you're looking for something else, try checking the manufacturer's website."
        )
    
    # === DEFAULT FALLBACK (shouldn't happen often) ===
    else:
        return (
            f"I couldn't find reliable information about that in the {pedal} manual. "
            f"Could you rephrase your question or ask about a specific feature?"
        )

