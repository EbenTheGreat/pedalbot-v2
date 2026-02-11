import asyncio
import logging
import os
from datetime import datetime, UTC
from backend.config.config import settings
from backend.agents.graph import create_pedalbot_graph, query_pedalbot
from backend.db.mongodb import MongoDB

# LangSmith setup is handled by environment variables in .env
# LANGSMITH_TRACING=true
# LANGSMITH_API_KEY=...

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def run_test():
    """Run full agent integration tests."""
    print("\n Testing Full PedalBot Agent Pipeline\n")
    print("=" * 60)

    # 1. Initialize MongoDB (needed for pricing cache and potentially manual lookups)
    await MongoDB.connect(
        uri=settings.MONGODB_URI,
        db_name=settings.MONGODB_DB_NAME
    )

    try:
        # 2. Setup Graph
        graph = await create_pedalbot_graph(
            voyageai_api_key=settings.VOYAGEAI_API_KEY,
            groq_api_key=settings.GROQ_API_KEY,
            pinecone_api_key=settings.PINECONE_API_KEY,
            pinecone_index_name=settings.PINECONE_INDEX_NAME,
            reverb_api_key=settings.REVERB_API_KEY
        )

        test_cases = [
            {
                "name": "Manual Question (Spec Check)",
                "query": "What is the input impedance of the Boss DS-1 Distortion?",
                "pedal": "Boss DS-1 Distortion"  # Match the exact name from ingestion
            },
            {
                "name": "Pricing Question",
                "query": "How much does a used Boss DS-1 cost on average?",
                "pedal": "Boss DS-1"
            },
            {
                "name": "General Question (Not Supported)",
                "query": "Tell me a joke about guitarists.",
                "pedal": None
            }
        ]

        for case in test_cases:
            print(f"\n▶️ Case: {case['name']}")
            print(f"  Query: {case['query']}")
            
            result = await query_pedalbot(
                query=case['query'],
                graph=graph,
                pedal_name=case['pedal']
            )

            print(f"  Intent: {result['intent']}")
            print(f"  Path: {' -> '.join(result['agent_path'])}")
            
            # Safely handle None answers
            answer = result.get('answer') or "No answer generated"
            print(f"  Answer: {answer[:200]}...")
            
            if result.get('hallucination_flag'):
                print(f"   Hallucination Flagged!")
            if result.get('error'):
                print(f"   Error: {result['error']}")
            print("-" * 30)

    finally:
        await MongoDB.close()
        print("\n Test complete. Check results in LangSmith dashboard:")
        print(f"   Project: {settings.LANGSMITH_PROJECT}")
        print(f"   URL: https://smith.langchain.com/")

if __name__ == "__main__":
    asyncio.run(run_test())
