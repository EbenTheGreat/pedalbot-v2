"""
PedalBot Settings

Application settings and status.
"""

import streamlit as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.api_client import get_client, API_BASE_URL
from utils.styles import init_styles

# Page config
st.set_page_config(
    page_title="Settings - PedalBot",
    page_icon="⚙️",
    layout="wide",
    initial_sidebar_state="expanded"
)


# Initialize styles and theme
init_styles()

# Page spacing
st.markdown("""
<style>
    .block-container { padding-top: 2rem; max-width: 800px; }
</style>
""", unsafe_allow_html=True)

client = get_client()

# ============ SIDEBAR ============
with st.sidebar:
    st.markdown("## 🎸 PedalBot")
    st.markdown("---")
    
    # Navigation
    st.markdown("### Navigation")
    st.page_link("Home.py", label="🏠 Home")
    st.page_link("pages/1_💬_Chat.py", label="💬 Chat")
    st.page_link("pages/2_📤_Upload.py", label="📤 Upload Manual")
    st.page_link("pages/3_📚_Library.py", label="📚 Manual Library")
    
    st.markdown("---")
    
    # API Status
    is_healthy = client.health_check()
    status = "🟢 Online" if is_healthy else "🔴 Offline"
    st.caption(f"API: {status}")


# ============ MAIN CONTENT ============
st.markdown("## ⚙️ Settings")

st.markdown("---")

# API Configuration
st.markdown("### API Configuration")

st.text_input("Backend URL", value=API_BASE_URL, disabled=True)
st.caption("Set via PEDALBOT_API_URL environment variable")

if st.button("Test Connection"):
    if client.health_check():
        st.success("✓ Connected to API")
    else:
        st.error("✗ Could not connect to API")

st.markdown("---")

# System Status
st.markdown("### System Status")

col1, col2 = st.columns(2)

with col1:
    is_healthy = client.health_check()
    st.markdown(f"**API:** {'✓ Online' if is_healthy else '✗ Offline'}")
    
    pedals = client.get_available_pedals()
    st.markdown(f"**Indexed Manuals:** {len(pedals)}")

with col2:
    manuals = client.get_manuals()
    processing = len([m for m in manuals if m.get('status') == 'processing']) if manuals else 0
    st.markdown(f"**Processing:** {processing}")

st.markdown("---")

# Session Management
st.markdown("### Session")

if st.button("Clear Chat History"):
    st.session_state.messages = []
    st.session_state.conversation_id = None
    st.success("Chat history cleared")

if st.button("Reset All Session Data"):
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.success("Session reset")
    st.rerun()

st.markdown("---")

# About
st.markdown("### About")
st.markdown("""
**PedalBot** v2.0

AI-powered assistant for guitar pedal manuals.

- **Backend:** FastAPI + LangGraph
- **Frontend:** Streamlit
- **Vector DB:** Pinecone
- **LLM:** Groq (Llama 3.3 70B)
- **Embeddings:** VoyageAI
""")
