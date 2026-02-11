---
name: langsmith_fetch
description: Fetch and reflect on LangSmith traces for debugging and optimization.
---

# LangSmith Fetch Skill

This skill allows Antigravity to retrieve and analyze execution data from LangSmith. This is useful for identifying why an agent failed, checking tool outputs, or optimizing prompts.

## How to use

Use the `langsmith-fetch` CLI tool to pull traces.

### 1. Fetching recent traces
To get the most recent trace from the current project:
```bash
uv run langsmith-fetch traces --limit 1
```

### 2. Saving traces to a directory
To save traces for closer inspection:
```bash
uv run langsmith-fetch traces --limit 5 --dir ./langsmith_traces
```

### 3. Workflow for reflection
1. Run the agent workflow (e.g., query PedalBot).
2. Fetch the trace using `langsmith-fetch`.
3. Read the trace data to identify where the logic deviated from expectations.
4. Apply fixes to the code, prompt, or tool configuration.

### 4. Configuration
The tool uses environment variables for LangSmith access:
- `LANGSMITH_API_KEY`
- `LANGSMITH_PROJECT` (Optional, defaults to the active project)
- `LANGCHAIN_ENDPOINT`
