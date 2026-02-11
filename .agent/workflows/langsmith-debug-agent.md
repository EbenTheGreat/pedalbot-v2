---
description: Fetch LangSmith traces and perform deep agent debugging analysis
---

# LangSmith Debug Agent Workflow

This workflow fetches traces from LangSmith and performs a comprehensive agent analysis to identify failures, inefficiencies, and actionable improvements.

---

## Prerequisites
- LangSmith API key configured in `.env` (`LANGSMITH_API_KEY`)
- `langsmith-fetch` CLI installed (via `uv add langsmith-fetch`)

---

## Steps

### 1. Fetch the latest trace from LangSmith
// turbo
```bash
uv run langsmith-fetch traces --limit 1 --output ./latest_trace.json
```

### 2. Read the trace file
Open and parse `latest_trace.json` to extract the following fields:
- **Project Name**: The LangSmith project
- **User Input**: The original user query/intent
- **System Prompt**: The agent's system prompt (if available)
- **Agent Plan/Reasoning**: Any intermediate reasoning or chain-of-thought
- **Tool Calls**: All tools invoked with their parameters and outputs
- **Final Output**: The agent's final response to the user
- **Errors/Exceptions**: Any errors raised during execution
- **Metadata**: Latency, token counts, retries, model used

### 3. Perform the 8-Part Analysis

Using the extracted trace data, analyze the following:

#### 3.1 INTENT ALIGNMENT
- Did the agent correctly understand the user's intent?
- If not, what was misunderstood and why?

#### 3.2 PLANNING QUALITY
- Did the agent plan before acting?
- Identify any unnecessary or missing steps.

#### 3.3 TOOL USAGE
- Were the right tools used?
- Was any tool call premature, redundant, or mis-parameterized?

#### 3.4 FAILURE MODE (if applicable)
- Root cause in one sentence.
- Classify the failure: `prompt`, `planning`, `tooling`, `memory`, or `state`.

#### 3.5 OUTPUT QUALITY
- Was the output actually useful to the user?
- What information was missing or unnecessary?

#### 3.6 PERFORMANCE
- Identify the single biggest latency or cost contributor.
- One optimization suggestion.

#### 3.7 SYSTEMIC FIXES (IMPORTANT)
Provide exactly:
- **ONE system-prompt change** (as a rule, not explanation)
- **ONE planner rule or constraint** (as a rule, not explanation)
- **ONE tool-usage rule** (as a rule, not explanation)

#### 3.8 PREVENTION
- What invariant or guardrail would prevent this failure in the future?

### 4. Generate Final Deliverable

Return the following structured output:

```markdown
## 🔍 Diagnosis (max 5 bullet points)
- [bullet 1]
- [bullet 2]
- ...

## 📝 Revised System-Prompt Snippet (≤ 10 lines)
```
[revised prompt here]
```

## ✅ Reliability Statement
[Single sentence describing how this agent is now more reliable]
```

---

## Optional: Fetch Multiple Traces for Pattern Analysis

To analyze patterns across multiple runs:
// turbo
```bash
uv run langsmith-fetch traces --limit 10 --dir ./langsmith_traces
```

Then read all traces in `./langsmith_traces/` and look for:
- Recurring failure modes
- Common tool misuse patterns
- Consistent latency bottlenecks

---

## Example Usage

After running a query against PedalBot:
1. Trigger this workflow with `/langsmith-debug-agent`
2. Review the diagnosis and systemic fixes
3. Apply the revised system-prompt snippet to the agent
4. Re-run the query to verify improvement

---

## Trace Field Extraction Reference

When parsing the trace JSON, look for these common LangSmith fields:

| Field | JSON Path (typical) |
|-------|---------------------|
| User Input | `runs[0].inputs.input` or `runs[0].inputs.messages[0].content` |
| System Prompt | `runs[0].inputs.messages[0].content` (if role=system) |
| Tool Calls | `runs[*].outputs.tool_calls` or child runs with `run_type=tool` |
| Final Output | `runs[-1].outputs.output` or `runs[-1].outputs.content` |
| Errors | `runs[*].error` |
| Latency | `runs[*].end_time - runs[*].start_time` |
| Tokens | `runs[*].extra.tokens` or `runs[*].feedback` |
