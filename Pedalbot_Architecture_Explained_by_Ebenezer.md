# Pedalbot Architecture Explained by Ebenezer

## What Problem Does PedalBot Solve?
Guitar pedal manuals are often dense, long, and hard to search through physically or as generic PDFs. Musicians waste time scrolling through hundreds of pages to find how to save a preset or change a MIDI channel. Additionally, checking the current market value of a pedal requires switching context to browsing functionality.

**PedalBot acts as an intelligent assistant that:**
1.  **Reads Manuals for You:** Instantly answers specific questions like "How do I change the loop length?" based on the actual manual.
2.  **Checks Market Prices:** Fetches real-time pricing data for gear.
3.  **Understands Context:** Distinguishes between technical questions and buying questions.

---

## The Full Flow: From Upload to Answer

### Part 1: The Learning Phase (Upload & Ingestion)
Before PedalBot can answer questions, it must "read" and "learn" the manual.

1.  **Upload**: You upload a PDF manual (e.g., "Boss_DD500.pdf").
2.  **Filing**: The system saves the file and records its existence in **MongoDB**.
3.  **Queueing**: The system acts immediately but doesn't make you wait. It sends a "job ticket" to **Redis** saying, "Hey, process this manual."
4.  **Processing (Background Worker)**:
    *   A worker picks up the ticket from **Redis**.
    *   It opens the PDF and extracts all the text.
    *   It breaks the text into small, meaningful "chunks" (paragraphs).
    *   It converts these chunks into mathematical representations (vectors).
    *   It saves these vectors into **Pinecone**.
5.  **Ready**: The manual is now "indexed" and ready to be queried.

### Part 2: The Thinking Phase (Answering a Question)
When you ask a question like, *"How do I reset this pedal?"*:

1.  **The Brain (LangGraph)** wakes up. It acts as a conductor.
2.  **Routing**: The *Router Agent* analyzes your intent. "Is this asking for a price? Or how to use a feature?"
3.  **Retrieval**: If it's a manual question, the *Manual Agent* searches **Pinecone**. It looks for the specific chunks of text that match your question mathematically.
4.  **Generation**: The agent reads those specific chunks and formulates an answer in plain English.
5.  **Quality Control**: The *Quality Check Agent* reviews the draft. "Does this answer actually answer the user's question? Is it making things up?"
6.  **Delivery**: If the answer is good, it is delivered to you.

---

## The Technology Stack (The "Who Does What")

### **Pinecone: The Memory Bank**
*   **What it does:** Stores the "knowledge" extracted from the manuals.
*   **Why we need it:** Computers can't "read" a book like we do. Pinecone stores the manual as searchable vectors (numbers). This allows PedalBot to find the *exact* paragraph relevant to your question effectively instantly, even in a 500-page document.

### **MongoDB: The Filing Cabinet**
*   **What it does:** Stores the administrative records.
*   **Why we need it:** It keeps track of what manuals have been uploaded, their file names, their processing status (Pending, Completed, Failed), and their timestamps. It ensures we don't upload the same thing twice and lets us list what's available.

### **Redis: The Messenger**
*   **What it does:** Acts as a high-speed message queue between the web server and the heavy-lifting workers.
*   **Why we need it:** Reading and processing a PDF takes time (seconds or minutes). If the web server did this directly, the website would freeze. Redis lets the website say "Here, do this later" and immediately tell the user "Upload received!" providing a snappy experience.

### **LangGraph: The Conductor (The Brain)**
*   **What it does:** Controls the decision-making flow of the AI agents.
*   **Why we need it:** A simple script acts linearly (A -> B -> C). LangGraph allows for complex reasoning. It lets the AI:
    *   **Decide** which tool to use (Price checker vs Manual reader).
    *   **Loop back** if an answer isn't good enough.
    *   **Critique** its own work before showing it to you.
    *   It turns a dumb chatbot into a smart **agent**.
