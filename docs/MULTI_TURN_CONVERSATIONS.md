# Multi-Turn Conversation Support

## Overview

PedalBot now supports **multi-turn conversations**, allowing users to ask follow-up questions that reference previous context without repeating information.

## Key Features

### 1. Conversation History Tracking
- All conversations are stored in MongoDB with full message history
- Each conversation has a unique `conversation_id`
- Messages include role (user/assistant), content, timestamp, and metadata

### 2. Context-Aware Agents
The following agents now use conversation history for better understanding:

- **Router Agent**: Understands follow-up questions like "What about the output?" after asking about input
- **Manual Agent**: Uses previous Q&A to provide contextual answers
- **Quality Check Agent**: Already robust for single-turn validation

### 3. Automatic Context Management
- Last 10 messages are loaded for context (prevents token overflow)
- Router uses last 4 messages (2 exchanges) for intent classification
- Manual agent uses last 6 messages (3 exchanges) for answer generation

## API Usage

### First Message (New Conversation)

```bash
curl -X POST http://localhost:8000/api/query/ \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is the input impedance?",
    "pedal_name": "Boss GT-10"
  }'
```

**Response:**
```json
{
  "answer": "The Boss GT-10 has an input impedance of 1MΩ...",
  "conversation_id": "conv_abc123def456",
  "user_id": "anon_xyz789",
  "pedal_name": "Boss GT-10",
  "confidence": 0.92,
  ...
}
```

### Follow-up Message (Existing Conversation)

```bash
curl -X POST http://localhost:8000/api/query/ \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What about the output impedance?",
    "conversation_id": "conv_abc123def456"
  }'
```

**Key differences:**
- ✅ No need to repeat `pedal_name` - inherited from conversation context
- ✅ Agent understands "What about..." references previous question
- ✅ Full conversation history available to agents

### Example: Multi-Turn Conversation Flow

```python
import requests

BASE_URL = "http://localhost:8000/api/query/"

# Turn 1: Initial question
response1 = requests.post(BASE_URL, json={
    "query": "What is the input impedance?",
    "pedal_name": "Boss GT-10"
})
conv_id = response1.json()["conversation_id"]

# Turn 2: Follow-up with pronoun reference
response2 = requests.post(BASE_URL, json={
    "query": "What about its output impedance?",
    "conversation_id": conv_id
})

# Turn 3: Another follow-up
response3 = requests.post(BASE_URL, json={
    "query": "And the power requirements?",
    "conversation_id": conv_id
})

# Turn 4: Reference previous answer
response4 = requests.post(BASE_URL, json={
    "query": "Is that 9V or 12V?",
    "conversation_id": conv_id
})
```

## How It Works

### 1. State Management

```python
class AgentState(BaseModel):
    # ... other fields ...
    
    # NEW: Conversation context
    conversation_history: List[Dict[str, str]] = Field(
        default_factory=list,
        description="Previous messages [{'role': 'user'|'assistant', 'content': '...'}]"
    )
```

### 2. API Layer

When a request includes `conversation_id`:

1. **Fetch conversation** from MongoDB
2. **Extract last 10 messages** for context
3. **Inherit pedal_name** if not provided
4. **Create AgentState** with conversation history
5. **Run agent graph** with full context
6. **Save new messages** to conversation

### 3. Agent Layer

**Router Agent:**
```python
def _build_user_prompt(self, state: AgentState) -> str:
    prompt_parts = []
    
    # Add conversation history
    if state.conversation_history:
        prompt_parts.append("Recent conversation context:")
        for msg in state.conversation_history[-4:]:
            prompt_parts.append(f"{msg['role'].capitalize()}: {msg['content']}")
    
    # Add current query
    prompt_parts.append(f"Current query: {state.query}")
    
    return "\n".join(prompt_parts)
```

**Manual Agent:**
```python
async def _generate_answer(self, query: str, context: str, 
                          conversation_history: List[Dict[str, str]] = None) -> str:
    messages = [SystemMessage(content=system_prompt)]
    
    # Add conversation history for context
    if conversation_history:
        for msg in conversation_history[-6:]:
            if msg["role"] == "user":
                messages.append(HumanMessage(content=msg["content"]))
            else:
                messages.append(SystemMessage(content=f"Previous answer: {msg['content']}"))
    
    # Add current query
    messages.append(HumanMessage(content=query))
    
    response = await self.llm.ainvoke(messages)
    return response.content.strip()
```

## Use Cases

### 1. Technical Specifications
```
User: What's the input impedance?
Bot: The Boss GT-10 has an input impedance of 1MΩ.

User: What about the output?
Bot: The output impedance is 1kΩ.

User: Are those values typical for multi-effects?
Bot: [Uses context to understand "those values" refers to 1MΩ input / 1kΩ output]
```

### 2. Feature Exploration
```
User: List all the reverb types
Bot: The Helix includes: Spring, Plate, Hall, Room, Chamber...

User: Which ones are convolution-based?
Bot: [Understands "ones" refers to reverb types from previous answer]

User: How do I adjust the decay time?
Bot: [Knows we're still discussing reverb effects]
```

### 3. Troubleshooting
```
User: How do I connect this to my amp?
Bot: Connect the GT-10's OUTPUT jacks to your amp's INPUT...

User: What if I want to use 4-cable method?
Bot: [Understands "I" and context about connections]

User: Does it require stereo cables?
Bot: [Knows "it" refers to the GT-10 in 4CM setup]
```

## Benefits

✅ **Natural conversations** - No need to repeat pedal name or context  
✅ **Pronoun resolution** - Understands "it", "that", "these", etc.  
✅ **Follow-up questions** - "What about...", "And the...", "How about..."  
✅ **Context building** - Each answer builds on previous knowledge  
✅ **Better UX** - Feels like talking to a knowledgeable expert  

## Implementation Details

### Storage
- **Collection**: `conversations` in MongoDB
- **Schema**: `ConversationDocument` with `messages` array
- **TTL**: No automatic expiration (can be added if needed)
- **Index**: `conversation_id` for fast lookups

### Performance
- **History limit**: Last 10 messages loaded (configurable)
- **Token usage**: ~2-3x increase per query (due to history)
- **Latency**: +50-100ms for history fetch from MongoDB
- **Cost**: Minimal increase (~$0.001 per query with history)

### Configuration

```python
# In backend/routers/query.py
CONVERSATION_HISTORY_LIMIT = 10  # Messages to load
ROUTER_HISTORY_WINDOW = 4        # Messages router sees
MANUAL_HISTORY_WINDOW = 6        # Messages manual agent sees
```

## Testing

Run the multi-turn conversation test:

```bash
python tests/test_multi_turn_conversation.py
```

This will simulate a 3-turn conversation and verify:
- Conversation history is passed correctly
- Follow-up questions work
- Context is maintained across turns

## Limitations

1. **No cross-pedal context** - Each conversation is tied to one pedal
2. **No memory compression** - Simple truncation after 10 messages
3. **No explicit entity tracking** - Relies on LLM to understand references
4. **Anonymous sessions** - No persistent user sessions (can be added)

## Future Enhancements

- [ ] Add conversation summarization for longer sessions
- [ ] Implement explicit entity tracking (pedal features, settings mentioned)
- [ ] Add user authentication for persistent conversation history
- [ ] Support switching pedal context mid-conversation
- [ ] Add conversation export/sharing functionality
