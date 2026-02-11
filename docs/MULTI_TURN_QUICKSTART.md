# 🎯 Quick Start: Multi-Turn Conversations

## Basic Example

### Using the API

```python
import requests

url = "http://localhost:8000/api/query/"

# Start a conversation
r1 = requests.post(url, json={
    "query": "What reverb types does the Helix have?",
    "pedal_name": "Helix"
})

# Get the conversation ID
conv_id = r1.json()["conversation_id"]
print(f"Answer 1: {r1.json()['answer']}\n")

# Ask a follow-up (no need to repeat pedal name!)
r2 = requests.post(url, json={
    "query": "Which ones are convolution-based?",
    "conversation_id": conv_id
})
print(f"Answer 2: {r2.json()['answer']}\n")

# Another follow-up
r3 = requests.post(url, json={
    "query": "How do I adjust the decay time?",
    "conversation_id": conv_id
})
print(f"Answer 3: {r3.json()['answer']}")
```

## Using Test Script

```bash
# Test multi-turn with Boss GT-10
python tests/test_multi_turn_conversation.py
```

## What Changed?

### ✅ Added to `AgentState`
```python
conversation_history: List[Dict[str, str]]  # Previous messages
```

### ✅ Updated API Endpoint
- Fetches last 10 messages from MongoDB
- Passes history to agents
- Saves new messages to conversation

### ✅ Updated Agents
- **Router**: Uses last 4 messages for context
- **Manual**: Uses last 6 messages for contextual answers

## Example Conversations

### Before (No Context)
```
Q: What is the input impedance?
A: The Boss GT-10 has an input impedance of 1MΩ.

Q: What about the output?  ❌ Doesn't understand "the output"
A: I need more context. Output of what?
```

### After (With Context)
```
Q: What is the input impedance?
A: The Boss GT-10 has an input impedance of 1MΩ.

Q: What about the output?  ✅ Understands from context!
A: The output impedance is 1kΩ.
```

## Key Benefits

🎯 **Natural follow-ups**: "What about...", "And the...", "How about..."  
🔗 **Pronoun resolution**: "it", "that", "these", "them"  
📚 **Context building**: Each turn builds on previous knowledge  
⚡ **Faster queries**: No need to repeat pedal name  

## See Full Documentation

📖 Read `docs/MULTI_TURN_CONVERSATIONS.md` for complete details
