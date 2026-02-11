"""
PedalBot Manual Library

View and manage all indexed manuals.
"""

import streamlit as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.api_client import get_client
from utils.styles import init_styles

# Page config
st.set_page_config(
    page_title="Library - PedalBot",
    page_icon="📚",
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
    
    if st.button("🔄 Refresh", use_container_width=True):
        st.rerun()
    
    st.markdown("---")
    
    # Navigation
    st.markdown("### Navigation")
    st.page_link("Home.py", label="🏠 Home")
    st.page_link("pages/1_💬_Chat.py", label="💬 Chat")
    st.page_link("pages/2_📤_Upload.py", label="📤 Upload Manual")
    st.page_link("pages/4_⚙️_Settings.py", label="⚙️ Settings")
    
    st.markdown("---")
    
    # API Status
    is_healthy = client.health_check()
    status = "🟢 Online" if is_healthy else "🔴 Offline"
    st.caption(f"API: {status}")


# ============ MAIN CONTENT ============
st.markdown("## 📚 Manual Library")
st.markdown("All indexed manuals and their status.")

st.markdown("---")

# Stats
try:
    manuals = client.get_manuals()
    
    col1, col2, col3, col4 = st.columns(4)
    
    total = len(manuals) if manuals else 0
    completed = len([m for m in manuals if m.get('status') == 'completed']) if manuals else 0
    processing = len([m for m in manuals if m.get('status') == 'processing']) if manuals else 0
    failed = len([m for m in manuals if m.get('status') == 'failed']) if manuals else 0
    
    with col1:
        st.metric("Total", total)
    with col2:
        st.metric("Completed", completed)
    with col3:
        st.metric("Processing", processing)
    with col4:
        st.metric("Failed", failed)
        
except Exception as e:
    manuals = []
    st.warning(f"Could not fetch manuals: {e}")

st.markdown("---")

# Manual list
if manuals:
    for manual in manuals:
        status = manual.get('status', 'unknown')
        badge_class = f"badge-{status}"
        
        col1, col2, col3 = st.columns([3, 1, 1])
        
        with col1:
            # Badge colors
            badge_colors = {
                'pending': '#f59e0b',
                'processing': '#3b82f6',
                'completed': '#22c55e',
                'failed': '#ef4444',
                'unknown': '#6b7280'
            }
            badge_color = badge_colors.get(status, badge_colors['unknown'])
            
            st.markdown(f"""
            <div class="card">
                <div style="font-size: 16px; font-weight: 600; margin-bottom: 8px;">
                    {manual.get('pedal_name', 'Unknown')}
                </div>
                <div style="font-size: 13px; color: #94a3b8;">
                    <span style="background: {badge_color}20; color: {badge_color}; padding: 2px 8px; border-radius: 6px; font-size: 11px; font-weight: 600;">{status.upper()}</span>
                    · {manual.get('chunk_count', 0)} chunks
                    · ID: {manual.get('manual_id', 'N/A')[:12]}...
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            if status == "completed":
                if st.button("💬 Chat", key=f"chat_{manual.get('manual_id')}"):
                    st.session_state.selected_pedal = manual.get('pedal_name')
                    st.switch_page("pages/1_💬_Chat.py")
        
        with col3:
            if status == "failed":
                if st.button("🔄 Retry", key=f"retry_{manual.get('manual_id')}"):
                    st.info("Retry not implemented yet")

else:
    st.markdown("""
    <div style="text-align: center; padding: 40px; color: #888;">
        <div style="font-size: 48px; margin-bottom: 16px;">📚</div>
        <div>No manuals indexed yet.</div>
        <div style="margin-top: 8px;">Upload a PDF to get started.</div>
    </div>
    """, unsafe_allow_html=True)
    
    if st.button("📤 Upload Manual", type="primary"):
        st.switch_page("pages/2_📤_Upload.py")
