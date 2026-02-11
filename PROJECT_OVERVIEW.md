# 🎸 PedalBot: Project Overview & Strategy

## 🏗️ Technical Architecture

PedalBot is a sophisticated **Agentic AI Application** designed to be the ultimate assistant for guitar gear enthusiasts. It combines RAG (Retrieval-Augmented Generation) with real-time data fetching.

### 🧩 The "Brain" (LangGraph)
The core logic lives in `backend/agents/graph.py`. It uses a graph-based workflow:
1.  **Router Agent**: Classifies user intent (Pricing vs. Tech Support).
2.  **Manual Agent**: Uses vector search (Pinecone + VoyageAI) to answer technical questions from PDF manuals.
3.  **Pricing Agent**: Fetches real-time market data from Reverb.com.
4.  **Quality Check**: Validates answers before sending them to the user.

### ⚙️ The "Body" (Infrastructure)
-   **API**: FastAPI (Python) for the backend interface.
-   **Workers**: Celery + Redis for heavy lifting (PDF OCR, bulk pricing updates).
-   **Database**:
    -   **MongoDB**: Stores pedal metadata, cached pricing, and user alerts.
    -   **Pinecone**: Stores vector embeddings of manual text.
    -   **Redis**: Message broker and caching layer.
-   **Email**: Resend API for notifications (Price alerts, processing complete).

---

## ⚡ How to Be Fast & Efficient

### 1. Master the "Inner Loop"
Don't spin up the full Docker stack for every code change.
-   **Logic Changes**: Test agents in isolation. Use `backend/test/` scripts.
-   **Graph Changes**: Use the `uv run` command to test the graph logic without the API overhead.

### 2. Trust the Workers
Your background workers are set up perfectly. Offload EVERYTHING slow here.
-   *Parsing a 50MB PDF?* -> Worker.
-   *Fetching 100 prices?* -> Worker.
-   **Efficiency Tip**: Use the `Celery Beat` scheduler (already configured) to keep data fresh automatically, so the user never waits for "loading..." screens.

### 3. Mock External APIs
Development slows down when you wait for Reverb or OpenAI API calls.
-   Create "Mock Agents" that return hardcoded data for UI development.

---

## 🎸 Product Strategy: Making it Essential for Guitarists

If this were my product, here is how I would pivot from "cool tech demo" to **"I can't live without this"**:

### 1. The "Tone Architect" (Killer Feature) 🌟
Instead of just asking *metrics* ("What is the impedance?"), users care about *sound*.
-   **Feature**: "I want to sound like David Gilmour on 'Comfortably Numb'. Here are my pedals. Tell me the exact knob settings."
-   **Tech**: RAG can extract "suggested settings" from manuals. The AI can infer settings based on "creamy lead tone" descriptions.

### 2. The "Rig Doctor" 🚑
-   **Feature**: "My signal chain is noisy. Here is a photo of my board."
-   **Analysis**: PedalBot analyzes the order (e.g., "You put your Fuzz *after* a buffered bypass pedal—move it first!") and power requirements ("You are underpowering that Strymon").

### 3. "Sniper" Price Alerts 🎯
-   **context**: Reverb emails are slow.
-   **Feature**: "Find me a Boss DM-2 (Vintage) under $150."
-   **Tech**: Your pricing worker runs hourly. Beat the scalpers. Send an SMS or instant email (already built!) the second a listing drops.

### 4. Visual Manuals 📖
-   **Problem**: PDFs are boring.
-   **Feature**: When answering "How do I loop?", show the **cropped image** of the specific diagram from the manual, not just text.
-   **Tech**: You are already doing OCR. Store the bounding boxes of diagrams and serve the image slice.
