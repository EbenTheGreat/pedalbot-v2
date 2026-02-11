"""
PedalBot - AI Guitar Pedal Assistant

Main landing page.
"""

import streamlit as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from utils.api_client import get_client
from utils.styles import init_styles
from utils.loading_components import skeleton_list

# Page config
st.set_page_config(
    page_title="PedalBot",
    page_icon="🎸",
    layout="wide",
    initial_sidebar_state="expanded"
)


# Initialize styles and theme
init_styles()

# Page spacing
st.markdown("""
<style>
    .block-container { padding-top: 2rem; max-width: 1000px; }
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
    st.page_link("pages/4_⚙️_Settings.py", label="⚙️ Settings")
    
    st.markdown("---")
    
    # API Status
    is_healthy = client.health_check()
    status = "🟢 Online" if is_healthy else "🔴 Offline"
    st.caption(f"API: {status}")
    
    # Stats
    if is_healthy:
        pedals = client.get_available_pedals()
        st.caption(f"Manuals indexed: {len(pedals)}")


# ============ MAIN CONTENT ============
st.markdown("# PedalBot")
st.markdown("### AI-powered assistant for guitar pedal manuals.")

st.markdown("---")

# Quick stats
pedals = client.get_available_pedals()

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Indexed Manuals", len(pedals))
with col2:
    total_chunks = sum(p.chunk_count for p in pedals)
    st.metric("Total Chunks", total_chunks)
with col3:
    st.metric("Status", "Ready" if client.health_check() else "Offline")

st.markdown("---")

# What you can do
st.markdown("### What you can do")

col1, col2 = st.columns(2)

with col1:
    st.markdown("""
    <div class="card">
        <h4>💬 Ask Questions</h4>
        <p>Get instant answers from your pedal manuals. Ask about settings, features, troubleshooting.</p>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("""
    <div class="card">
        <h4>📤 Upload Manuals</h4>
        <p>Upload PDF manuals to index them. The system extracts and indexes the content.</p>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown("""
    <div class="card">
        <h4>💰 Get Pricing</h4>
        <p>Check current market prices from Reverb.com. See average prices and listings.</p>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("""
    <div class="card">
        <h4>📎 View Sources</h4>
        <p>Every answer shows the page number and section from the manual.</p>
    </div>
    """, unsafe_allow_html=True)

st.markdown("---")

# Available Manuals
st.markdown("### Available Manuals")

# Initialize loading state
if "pedals_loading" not in st.session_state:
    st.session_state.pedals_loading = False

if pedals:
    for pedal in pedals:
        col1, col2 = st.columns([4, 1])
        with col1:
            st.markdown(f"**{pedal.pedal_name}**")
            st.caption(f"{pedal.chunk_count} chunks indexed")
        with col2:
            if st.button("Chat →", key=f"chat_{pedal.pedal_name}"):
                st.session_state.selected_pedal = pedal.pedal_name
                st.switch_page("pages/1_💬_Chat.py")
        st.markdown("---")
else:
    st.info("No manuals indexed yet. Upload a PDF to get started.")
    if st.button("📤 Upload a Manual", type="primary"):
        st.switch_page("pages/2_📤_Upload.py")
