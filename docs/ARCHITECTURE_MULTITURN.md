# Multi-Turn Conversation Architecture

## Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         CLIENT REQUEST                          │
└────────────────────────────────┬────────────────────────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │  POST /api/query/       │
                    │  {                      │
                    │    query: "...",        │
                    │    conversation_id: ""  │
                    │  }                      │
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │  Fetch Conversation     │
                    │  from MongoDB           │
                    │                         │
                    │  • Get messages[]       │
                    │  • Get pedal_context    │
                    │  • Limit to last 10     │
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │  Create AgentState      │
                    │                         │
                    │  state = {              │
                    │    query: "...",        │
                    │    pedal_name: "...",   │
                    │    conversation_history:│
                    │      [                  │
                    │        {role, content}, │
                    │        {role, content}, │
                    │        ...              │
                    │      ]                  │
                    │  }                      │
                    └────────────┬────────────┘
                                 │
        ┌────────────────────────┼────────────────────────┐
        │                        │                        │
        ▼                        ▼                        ▼
┌───────────────┐      ┌────────────────┐      ┌─────────────────┐
│ Router Agent  │      │ Manual Agent   │      │ Pricing Agent   │
│               │      │                │      │                 │
│ Uses last 4   │      │ Uses last 6    │      │ (No history     │
│ messages for  │      │ messages for   │      │  needed)        │
│ intent        │      │ contextual     │      │                 │
│ classification│      │ answers        │      │                 │
└───────┬───────┘      └────────┬───────┘      └─────────┬───────┘
        │                       │                        │
        └───────────────────────┼────────────────────────┘
                                │
                    ┌───────────▼────────────┐
                    │  Quality Check         │
                    │  Synthesizer           │
                    └───────────┬────────────┘
                                │
                    ┌───────────▼────────────┐
                    │  Save to MongoDB       │
                    │                        │
                    │  conversations.update( │
                    │    {conversation_id},  │
                    │    $push: {            │
                    │      messages: [       │
                    │        {user msg},     │
                    │        {assistant msg} │
                    │      ]                 │
                    │    }                   │
                    │  )                     │
                    └───────────┬────────────┘
                                │
                    ┌───────────▼────────────┐
                    │  Return Response       │
                    │  {                     │
                    │    answer: "...",      │
                    │    conversation_id: "" │
                    │  }                     │
                    └────────────────────────┘
```

## Message Flow Example

### Turn 1: New Conversation

```
┌───────────────────────────────────────────────────────────────┐
│ REQUEST                                                       │
├───────────────────────────────────────────────────────────────┤
│ {                                                             │
│   "query": "What is the input impedance?",                    │
│   "pedal_name": "Boss GT-10"                                  │
│ }                                                             │
└───────────────────────────────────────────────────────────────┘
                          ↓
┌───────────────────────────────────────────────────────────────┐
│ AGENT STATE                                                   │
├───────────────────────────────────────────────────────────────┤
│ query: "What is the input impedance?"                         │
│ pedal_name: "Boss GT-10"                                      │
│ conversation_history: []  ← EMPTY for first turn              │
└───────────────────────────────────────────────────────────────┘
                          ↓
┌───────────────────────────────────────────────────────────────┐
│ ROUTER PROMPT                                                 │
├───────────────────────────────────────────────────────────────┤
│ Current query: What is the input impedance?                   │
│ Pedal context: Boss GT-10                                     │
└───────────────────────────────────────────────────────────────┘
                          ↓
┌───────────────────────────────────────────────────────────────┐
│ MANUAL AGENT PROMPT                                           │
├───────────────────────────────────────────────────────────────┤
│ System: You are an expert...                                  │
│                                                               │
│ Manual Excerpts:                                              │
│ [Excerpt 1] The GT-10 has an input impedance of 1MΩ...       │
│                                                               │
│ User: What is the input impedance?                            │
└───────────────────────────────────────────────────────────────┘
                          ↓
┌───────────────────────────────────────────────────────────────┐
│ RESPONSE                                                      │
├───────────────────────────────────────────────────────────────┤
│ {                                                             │
│   "answer": "The Boss GT-10 has an input impedance of 1MΩ.", │
│   "conversation_id": "conv_abc123",                           │
│   "pedal_name": "Boss GT-10"                                  │
│ }                                                             │
└───────────────────────────────────────────────────────────────┘
                          ↓
┌───────────────────────────────────────────────────────────────┐
│ MONGODB CONVERSATIONS                                         │
├───────────────────────────────────────────────────────────────┤
│ {                                                             │
│   conversation_id: "conv_abc123",                             │
│   pedal_context: "Boss GT-10",                                │
│   messages: [                                                 │
│     {                                                         │
│       role: "user",                                           │
│       content: "What is the input impedance?"                 │
│     },                                                        │
│     {                                                         │
│       role: "assistant",                                      │
│       content: "The Boss GT-10 has an input impedance..."     │
│     }                                                         │
│   ]                                                           │
│ }                                                             │
└───────────────────────────────────────────────────────────────┘
```

### Turn 2: Follow-up with Context

```
┌───────────────────────────────────────────────────────────────┐
│ REQUEST                                                       │
├───────────────────────────────────────────────────────────────┤
│ {                                                             │
│   "query": "What about the output?",                          │
│   "conversation_id": "conv_abc123"  ← Provide conversation ID │
│ }                                                             │
└───────────────────────────────────────────────────────────────┘
                          ↓
┌───────────────────────────────────────────────────────────────┐
│ FETCH FROM MONGODB                                            │
├───────────────────────────────────────────────────────────────┤
│ conversations.find_one({conversation_id: "conv_abc123"})      │
│                                                               │
│ Returns:                                                      │
│   pedal_context: "Boss GT-10"  ← Inherited!                  │
│   messages: [...]  ← Last 10 messages                         │
└───────────────────────────────────────────────────────────────┘
                          ↓
┌───────────────────────────────────────────────────────────────┐
│ AGENT STATE                                                   │
├───────────────────────────────────────────────────────────────┤
│ query: "What about the output?"                               │
│ pedal_name: "Boss GT-10"  ← From conversation!                │
│ conversation_history: [                                       │
│   {                                                           │
│     role: "user",                                             │
│     content: "What is the input impedance?"                   │
│   },                                                          │
│   {                                                           │
│     role: "assistant",                                        │
│     content: "The Boss GT-10 has an input impedance of 1MΩ."  │
│   }                                                           │
│ ]                                                             │
└───────────────────────────────────────────────────────────────┘
                          ↓
┌───────────────────────────────────────────────────────────────┐
│ ROUTER PROMPT (with context!)                                │
├───────────────────────────────────────────────────────────────┤
│ Recent conversation context:                                  │
│ User: What is the input impedance?                            │
│ Assistant: The Boss GT-10 has an input impedance of 1MΩ.      │
│                                                               │
│ Current query: What about the output?                         │
│ Pedal context: Boss GT-10                                     │
└───────────────────────────────────────────────────────────────┘
                          ↓
        Router understands "output" refers to "output impedance"
        (from previous question about "input impedance")
                          ↓
┌───────────────────────────────────────────────────────────────┐
│ MANUAL AGENT PROMPT (with context!)                          │
├───────────────────────────────────────────────────────────────┤
│ System: You are an expert...                                  │
│                                                               │
│ Manual Excerpts:                                              │
│ [Excerpt 1] Output impedance: 1kΩ...                          │
│                                                               │
│ Previous answer: The Boss GT-10 has an input impedance of 1MΩ │
│ User: What is the input impedance?                            │
│ Previous answer: The Boss GT-10 has an input impedance of 1MΩ │
│                                                               │
│ User: What about the output?                                  │
└───────────────────────────────────────────────────────────────┘
                          ↓
       Agent understands context and provides coherent answer
                          ↓
┌───────────────────────────────────────────────────────────────┐
│ RESPONSE                                                      │
├───────────────────────────────────────────────────────────────┤
│ {                                                             │
│   "answer": "The output impedance is 1kΩ.",                   │
│   "conversation_id": "conv_abc123",                           │
│   "pedal_name": "Boss GT-10"                                  │
│ }                                                             │
└───────────────────────────────────────────────────────────────┘
```

## Key Differences: Before vs After

### ❌ BEFORE (No Multi-Turn Support)

```
User: What is the input impedance?
→ State: {query: "...", pedal: "GT-10", history: []}
→ Answer: "The Boss GT-10 has an input impedance of 1MΩ."

User: What about the output?
→ State: {query: "...", pedal: "GT-10", history: []}  ← NO CONTEXT!
→ Router: "output" of what? Ambiguous!
→ Answer: "Could you clarify what you're asking about?"
```

### ✅ AFTER (With Multi-Turn Support)

```
User: What is the input impedance?
→ State: {query: "...", pedal: "GT-10", history: []}
→ Answer: "The Boss GT-10 has an input impedance of 1MΩ."

User: What about the output?
→ State: {
    query: "...", 
    pedal: "GT-10", 
    history: [
      {user: "What is the input impedance?"},
      {assistant: "The Boss GT-10 has an input impedance of 1MΩ."}
    ]
  }  ← HAS CONTEXT!
→ Router: Understands "output" means "output impedance" from context
→ Manual: Retrieves and answers about output impedance
→ Answer: "The output impedance is 1kΩ."
```

## Architecture Benefits

1. **Stateless API with Stateful Conversations**
   - API endpoints are stateless
   - MongoDB provides persistent conversation state
   - Best of both worlds!

2. **Flexible History Windows**
   - Router: 4 messages (fast classification)
   - Manual: 6 messages (richer context)
   - Configurable per agent

3. **Token-Efficient**
   - Only last N messages loaded
   - Prevents unbounded growth
   - Balances context vs cost

4. **LangSmith Compatible**
   - All LLM calls use LangChain
   - Full conversation traces visible
   - Easy debugging

## Next Steps

1. **Test with real users** - Gather feedback on conversation flow
2. **Monitor token usage** - Ensure costs remain reasonable
3. **Add summarization** - For very long conversations (>10 turns)
4. **Implement export** - Allow users to save/share conversations
