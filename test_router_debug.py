#!/usr/bin/env python3
"""
Test what intent the router assigns to the NUX MG-30 query.
"""

import asyncio
import logging
from backend.agents.router_agent import RouterAgent
from backend.state import AgentState
from datetime import datetime, UTC

# Set up logging
logging.basicConfig(level=logging.INFO)

async def main():
    """Test router intent classification."""
    from backend.config.config import settings
    
    router = RouterAgent(
        api_key=settings.GROQ_API_KEY,
        model="llama-3.1-8b-instant"
    )
    
    test_query = "how do i put it on and i wnt to buy 3"
    
    state = AgentState(
        user_id="test",
        conversation_id="test",
        query=test_query,
        pedal_name="NUX MG-30",
        created_at=datetime.now(UTC)
    )
    
    print(f"Testing Query: {test_query}")
    print("-" * 60)
    
    result = await router.route(state)
    
    print(f"Intent: {result.intent.value}")
    print(f"Confidence: {result.confidence_score:.2f}")
    print(f"Normalized Query: {result.normalized_query}")
    print(f"Typos Corrected: {result.typos_corrected}")
    print(f"Has Multi-Questions: {result.has_multi_questions}")
    print(f"Sub-Questions: {result.sub_questions}")
    print("-" * 60)
    
    # Check expected vs actual
    if result.intent.value == "hybrid":
        print("✅ Router correctly identified HYBRID intent")
    else:
        print(f"❌ Router assigned '{result.intent.value}' instead of 'hybrid'")
        print("  Issue: Query has both usage question ('how to put it on') and purchasing intent ('want to buy')")

if __name__ == "__main__":
    asyncio.run(main())
