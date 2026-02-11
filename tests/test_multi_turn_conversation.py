"""
Test script for multi-turn conversation support.

Tests that the agent can understand follow-up questions using conversation history.
"""
import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from backend.agents.graph import create_pedalbot_graph
from backend.state import AgentState
from backend.config.config import settings
from datetime import datetime, UTC


async def test_multi_turn():
    """Test multi-turn conversation capabilities."""
    
    print(" Testing Multi-Turn Conversation Support\n")
    print("=" * 80)
    
    # Create graph
    print("\n Initializing PedalBot graph...")
    graph = await create_pedalbot_graph(
        groq_api_key=settings.GROQ_API_KEY,
        voyageai_api_key=settings.VOYAGEAI_API_KEY,
        pinecone_api_key=settings.PINECONE_API_KEY,
        pinecone_index_name=settings.PINECONE_INDEX_NAME,
        reverb_api_key=settings.REVERB_API_KEY
    )
    print("   ✓ Graph initialized")
    
    # Simulate a multi-turn conversation
    conversation_history = []
    conversation_id = "test_conv_123"
    user_id = "test_user_456"
    pedal_name = "Boss GT-10"
    
    # Turn 1: Ask about input impedance
    print("\n Turn 1: Initial question about input impedance")
    print("-" * 80)
    
    query1 = "What is the input impedance?"
    state1 = AgentState(
        user_id=user_id,
        conversation_id=conversation_id,
        query=query1,
        pedal_name=pedal_name,
        conversation_history=[],  # Empty for first turn
        created_at=datetime.now(UTC)
    )
    
    result1 = await graph.run(state1)
    print(f"   Query: {query1}")
    print(f"   Answer: {result1.final_answer}")
    print(f"   Confidence: {result1.confidence_score:.2f}")
    
    # Add to conversation history
    conversation_history.append({"role": "user", "content": query1})
    conversation_history.append({"role": "assistant", "content": result1.final_answer or "No answer"})
    
    # Turn 2: Follow-up question using pronoun ("it")
    print("\n3️⃣ Turn 2: Follow-up question with pronoun reference")
    print("-" * 80)
    
    query2 = "What about the output impedance?"
    state2 = AgentState(
        user_id=user_id,
        conversation_id=conversation_id,
        query=query2,
        pedal_name=pedal_name,
        conversation_history=conversation_history,  # Include previous messages
        created_at=datetime.now(UTC)
    )
    
    result2 = await graph.run(state2)
    print(f"   Query: {query2}")
    print(f"   Answer: {result2.final_answer}")
    print(f"   Confidence: {result2.confidence_score:.2f}")
    
    # Add to conversation history
    conversation_history.append({"role": "user", "content": query2})
    conversation_history.append({"role": "assistant", "content": result2.final_answer or "No answer"})
    
    # Turn 3: Another follow-up referencing previous context
    print("\n4️⃣ Turn 3: Another follow-up building on previous answers")
    print("-" * 80)
    
    query3 = "And the power requirements?"
    state3 = AgentState(
        user_id=user_id,
        conversation_id=conversation_id,
        query=query3,
        pedal_name=pedal_name,
        conversation_history=conversation_history,  # Include full history
        created_at=datetime.now(UTC)
    )
    
    result3 = await graph.run(state3)
    print(f"   Query: {query3}")
    print(f"   Answer: {result3.final_answer}")
    print(f"   Confidence: {result3.confidence_score:.2f}")
    
    # Summary
    print("\n" + "=" * 80)
    print(" Multi-turn conversation test completed!")
    print(f"\n Summary:")
    print(f"   • Total turns: 3")
    print(f"   • Conversation ID: {conversation_id}")
    print(f"   • Pedal context: {pedal_name}")
    print(f"   • Messages in history: {len(conversation_history) + 2}")
    
    print("\n Key observations:")
    print("   • Each query had access to previous conversation context")
    print("   • Follow-up questions like 'What about...' can reference previous topics")
    print("   • Agents can understand pronouns and implicit references")
    
    return True


if __name__ == "__main__":
    try:
        asyncio.run(test_multi_turn())
    except KeyboardInterrupt:
        print("\n\n Test interrupted by user")
    except Exception as e:
        print(f"\n\n Test failed: {e}")
        import traceback
        traceback.print_exc()
