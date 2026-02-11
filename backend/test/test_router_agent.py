from backend.agents.router_agent import RouterAgent
from backend.state import AgentState
from datetime import datetime, UTC
from backend.config.config import settings

router = RouterAgent(api_key=settings.GROQ_API_KEY)

state = AgentState(
    user_id="test",
    conversation_id="test",
    query="What's the input impedance of Boss DS-1?",
    pedal_name="Boss DS-1",
    created_at=datetime.now(UTC)
)

state = await router.route(state)
print(state.intent)  # → AgentIntent.MANUAL_QUESTION