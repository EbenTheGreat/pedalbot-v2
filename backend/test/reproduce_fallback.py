import asyncio
import sys
import os
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone

# Add parent directory to path to import backend
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from backend.agents.router_agent import RouterAgent
from backend.state import AgentState, AgentIntent

async def test_fallback():
    print("Initializing test...")
    # Create router with dummy key
    router = RouterAgent(api_key="dummy")
    
    # Mock LLM to raise exception
    router.llm.ainvoke = AsyncMock(side_effect=Exception("Connection error simulation"))
    
    # Test 1: Price query
    state_price = AgentState(
        user_id="test",
        conversation_id="test",
        query="What is the price of Boss DS-1?",
        pedal_name="Boss DS-1",
        created_at=datetime.now(timezone.utc)
    )
    
    print("Testing Price Query Fallback...")
    result_price = await router.route(state_price)
    print(f"Intent: {result_price.intent}")
    print(f"Fallback Reason: {result_price.fallback_reason}")
    
    if result_price.intent == AgentIntent.PRICING:
        print("✅ Price fallback success")
    else:
        print(f"❌ Price fallback failed: Gets {result_price.intent}")

    # Test 2: Hybrid Query (User's specific case)
    state_hybrid = AgentState(
        user_id="test",
        conversation_id="test",
        query="price of boss gt1 and how do i put it on",
        pedal_name="Boss GT-1",
        created_at=datetime.now(timezone.utc)
    )
    
    print("\nTesting Hybrid Query Fallback (User Case)...")
    result_hybrid = await router.route(state_hybrid)
    print(f"Intent: {result_hybrid.intent}")
    
    # "price" and "how" -> HYBRID
    if result_hybrid.intent == AgentIntent.HYBRID:
        print("✅ Hybrid fallback success")
    else:
        print(f"❌ Hybrid fallback failed: Gets {result_hybrid.intent}")
        
    # Test 3: Standard manual query
    state_manual = AgentState(
        user_id="test",
        conversation_id="test",
        query="how do i reset it?",
        pedal_name="Boss GT-1",
        created_at=datetime.now(timezone.utc)
    )
    
    print("\nTesting Manual Query Fallback...")
    result_manual = await router.route(state_manual)
    print(f"Intent: {result_manual.intent}")
    
    if result_manual.intent == AgentIntent.MANUAL_QUESTION:
        print("✅ Manual fallback success")
    else:
        print(f"❌ Manual fallback failed: Gets {result_manual.intent}")


if __name__ == "__main__":
    asyncio.run(test_fallback())
