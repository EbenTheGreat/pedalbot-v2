"""
PedalBot Upload Interface

Upload PDF manuals for indexing.
"""

import streamlit as st
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.api_client import get_client
from utils.styles import init_styles
from utils.loading_components import upload_progress

# Page config
st.set_page_config(
    page_title="Upload - PedalBot",
    page_icon="📤",
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
    st.page_link("pages/3_📚_Library.py", label="📚 Manual Library")
    st.page_link("pages/4_⚙️_Settings.py", label="⚙️ Settings")
    
    st.markdown("---")
    
    # API Status
    is_healthy = client.health_check()
    status = "🟢 Online" if is_healthy else "🔴 Offline"
    st.caption(f"API: {status}")


# ============ MAIN CONTENT ============
st.markdown("## 📤 Upload Manual")
st.markdown("Upload a PDF manual to index it for chat queries.")

st.markdown("---")

# Upload section
st.markdown("### Upload PDF")

uploaded_file = st.file_uploader(
    "Choose a PDF file",
    type=["pdf"],
    help="Supported format: PDF only | Max size: 20MB"
)

if uploaded_file:
    st.markdown(f"**Selected:** {uploaded_file.name}")
    st.caption(f"Size: {uploaded_file.size / 1024:.1f} KB")
    
    # Extract pedal name from filename
    pedal_name = uploaded_file.name.replace(".pdf", "").replace("_manual", "").replace("_", " ").strip()
    st.caption(f"Detected pedal: **{pedal_name}**")
    
    if st.button("📤 Upload & Process", type="primary"):
        # Show upload progress
        progress_container = st.empty()
        
        try:
            # Simulate upload progress (in real implementation, this would track actual upload)
            with progress_container.container():
                upload_progress(uploaded_file.name, 0.3, "Uploading")
            time.sleep(0.3)
            
            result = client.upload_manual(uploaded_file)
            
            with progress_container.container():
                upload_progress(uploaded_file.name, 0.8, "Processing")
            time.sleep(0.3)
            
            if result:
                with progress_container.container():
                    upload_progress(uploaded_file.name, 1.0, "Complete")
                time.sleep(0.5)
                st.success(f"✓ Uploaded! Manual ID: {result.get('manual_id')}")
                st.info("Processing started. Check the Library to see status.")
                time.sleep(1)
                st.rerun()
            else:
                with progress_container.container():
                    upload_progress(uploaded_file.name, 0.5, "Error")
                st.error("Upload failed. Check the API logs.")
                
        except Exception as e:
            with progress_container.container():
                upload_progress(uploaded_file.name, 0.5, "Error")
            st.error(f"Upload failed: {str(e)}")

st.markdown("---")

# Guidelines
st.markdown("### Guidelines")

st.markdown("""
**Supported formats:**
- PDF files only
- Max size: 20MB

""")

st.markdown("---")

# Recent uploads
st.markdown("### Recent Processing")

try:
    manuals = client.get_manuals()
    
    if manuals:
        for manual in manuals[:5]:
            status = manual.get('status', 'unknown')
            status_class = f"status-{status}"
            
            st.markdown(f"""
            <div class="status-card {status_class}">
                <strong>{manual.get('pedal_name', 'Unknown')}</strong>
                <div style="color: #888; font-size: 13px; margin-top: 4px;">
                    Status: {status.upper()} · {manual.get('chunk_count', 0)} chunks
                </div>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("No manuals uploaded yet.")
        
except Exception as e:
    st.caption(f"Could not load recent uploads: {e}")
