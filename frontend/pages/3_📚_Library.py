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
    api_status = "🟢 Online" if is_healthy else "🔴 Offline"
    st.caption(f"API: {api_status}")
    
    # Celery Status
    try:
        celery_stats = client.get_celery_stats()
        if celery_stats and celery_stats.get("online"):
            workers = celery_stats.get("workers", [])
            active = sum(w.get("active_tasks", 0) for w in workers)
            st.caption(f"Worker: 🟢 Online ({len(workers)})")
            if active > 0:
                st.caption(f"Tasks: ⏳ {active} active")
        else:
            st.caption("Worker: 🔴 Offline")
    except Exception:
        st.caption("Worker: ⚪ Unknown")


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
        
        col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
        
        # Extra status info for processing manuals
        job_message = None
        if status == "processing":
            try:
                job_status = client.get_ingestion_status(manual.get('manual_id'))
                if job_status:
                    job_message = job_status.get('message')
            except Exception:
                pass
        
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
                    {f'<div style="color: #ef4444; margin-top: 4px; font-size: 11px;">{manual.get("error")}</div>' if status == "failed" and manual.get("error") else ''}
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            if job_message:
                st.info(f"ℹ️ {job_message}", icon=None)
        
        with col2:
            if status == "completed":
                if st.button("💬 Chat", key=f"chat_{manual.get('manual_id')}"):
                    st.session_state.selected_pedal = manual.get('pedal_name')
                    st.switch_page("pages/1_💬_Chat.py")
        
        with col3:
            if status == "failed" or status == "pending":
                if st.button("🔄 Retry", key=f"retry_{manual.get('manual_id')}"):
                    try:
                        with st.spinner("Starting retry..."):
                            result = client.retry_ingestion(manual.get('manual_id'))
                            st.success("Retry started!")
                            st.rerun()
                    except Exception as e:
                        st.error(f"Retry failed: {e}")

        with col4:
            manual_id = manual.get('manual_id')
            pedal_name = manual.get('pedal_name', 'Unknown')
            
            # Use session state to track which manual is being deleted
            confirm_key = f"confirm_delete_{manual_id}"
            
            if st.session_state.get(confirm_key, False):
                # Show confirm/cancel buttons
                st.markdown(f"<div style='font-size: 12px; color: #ef4444; font-weight: 600;'>Delete {pedal_name}?</div>", unsafe_allow_html=True)
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("✅", key=f"yes_{manual_id}", help="Confirm delete"):
                        try:
                            with st.spinner("Deleting..."):
                                client.delete_manual(manual_id)
                                st.session_state[confirm_key] = False
                                st.success(f"Deleted {pedal_name}!")
                                st.rerun()
                        except Exception as e:
                            st.error(f"Delete failed: {e}")
                with c2:
                    if st.button("❌", key=f"no_{manual_id}", help="Cancel"):
                        st.session_state[confirm_key] = False
                        st.rerun()
            else:
                if st.button("🗑️", key=f"delete_{manual_id}", help=f"Delete {pedal_name}"):
                    st.session_state[confirm_key] = True
                    st.rerun()

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
