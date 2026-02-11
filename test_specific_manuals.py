
import asyncio
import logging
from backend.config.config import settings
from backend.agents.graph import create_pedalbot_graph, query_pedalbot
from backend.db.mongodb import MongoDB

# Configure logging
logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)

async def run_test():
    print("\n🎸 Testing Specific Manual Questions (Helix & Zoom)\n")
    print("=" * 60)

    # 1. Connect to DB to check availablity
    print("Connecting to MongoDB...")
    await MongoDB.connect(
        uri=settings.MONGODB_URI,
        db_name=settings.MONGODB_DB_NAME
    )

    try:
        db = MongoDB.get_database()
        manuals = await db.manuals.find({}, {"pedal_name": 1, "status": 1}).to_list(length=100)
        
        print(f"\nFound {len(manuals)} manuals in DB:")
        available_pedals = []
        for m in manuals:
            p_name = m.get('pedal_name')
            status = m.get('status')
            print(f"- {p_name} [{status}]")
            if status == "completed":
                available_pedals.append(p_name)
        
        print("-" * 30)

        # 2. Define Test Cases
        # We try to match the likely pedal names derived from filenames or user input
        # Adjust these names based on what we find in the DB if needed
        
        potential_helix_names = [p for p in available_pedals if "Helix" in p]
        potential_zoom_names = [p for p in available_pedals if "Zoom" in p]
        
        helix_name = potential_helix_names[0] if potential_helix_names else "Line 6 Helix"
        zoom_name = potential_zoom_names[0] if potential_zoom_names else "Zoom G3Xn"

        test_cases = [
            {
                "name": "Zoom - Aux In",
                "query": "What can I connect to the AUX IN jack?",
                "pedal": zoom_name
            },
            {
                "name": "Zoom - Looper",
                "query": "How long is the recording time for the looper?",
                "pedal": zoom_name
            },
            {
                "name": "Helix - Snapshots",
                "query": "How do snapshots work?",
                "pedal": helix_name
            },
             {
                "name": "Helix - Update",
                "query": "How do I update the firmware to 3.80?",
                "pedal": helix_name
            }
        ]

        # 3. Initialize Graph
        graph = await create_pedalbot_graph(
            voyageai_api_key=settings.VOYAGEAI_API_KEY,
            groq_api_key=settings.GROQ_API_KEY,
            pinecone_api_key=settings.PINECONE_API_KEY,
            pinecone_index_name=settings.PINECONE_INDEX_NAME,
            reverb_api_key=settings.REVERB_API_KEY
        )

        # 4. Run Queries
        for case in test_cases:
            print(f"\n▶️ Case: {case['name']}")
            print(f"  Pedal: {case['pedal']}")
            print(f"  Query: {case['query']}")
            
            if case['pedal'] not in available_pedals:
                 print(f"  ⚠️ WARNING: '{case['pedal']}' not found in 'completed' manuals. RAG might fail.")

            result = await query_pedalbot(
                query=case['query'],
                graph=graph,
                pedal_name=case['pedal']
            )

            print(f"  Intent: {result['intent']}")
            
            # Print answer
            answer = result.get('answer') or "No answer generated"
            print(f"  Answer: {answer[:300]}...") # Truncate for readability
            
            if result.get('hallucination_flag'):
                print(f"  🚩 Hallucination Flagged!")
            
            # Print sources if available
            chunks = result.get('retrieved_chunks')
            if chunks:
                print(f"  📚 Sources retrieved: {len(chunks)}")
            else:
                 print(f"  ❌ No sources retrieved")

            print("-" * 30)

    except Exception as e:
        print(f"\n❌ fatal error: {e}")
    finally:
        await MongoDB.close()

if __name__ == "__main__":
    asyncio.run(run_test())
