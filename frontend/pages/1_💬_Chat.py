"""
PedalBot Chat Interface

Clean chat interface with proper source citations and sidebar.
"""

import streamlit as st
import sys
import re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.api_client import get_client
from utils.styles import init_styles
from utils.loading_components import skeleton_message, loading_spinner

# Page config
st.set_page_config(
    page_title="Chat - PedalBot",
    page_icon="💬",
    layout="wide",
    initial_sidebar_state="expanded"
)


# Initialize styles and theme
init_styles()

# Page spacing
st.markdown("""
<style>
    .block-container { padding-top: 1rem; max-width: 900px; }
</style>
""", unsafe_allow_html=True)

# Session state
if "messages" not in st.session_state:
    st.session_state.messages = []
if "conversation_id" not in st.session_state:
    st.session_state.conversation_id = None
if "selected_pedal" not in st.session_state:
    st.session_state.selected_pedal = None

client = get_client()

# ============ SIDEBAR ============
with st.sidebar:
    st.markdown("## 🎸 PedalBot")
    st.markdown("---")
    
    # New Chat
    if st.button("➕ New Chat", use_container_width=True):
        st.session_state.messages = []
        st.session_state.conversation_id = None
        st.rerun()
    
    st.markdown("---")
    
    # Pedal Selector
    st.markdown("### 📚 Select Manual")
    
    pedals = client.get_available_pedals()
    
    if pedals:
        pedal_names = [p.pedal_name for p in pedals]
        
        idx = 0
        if st.session_state.selected_pedal in pedal_names:
            idx = pedal_names.index(st.session_state.selected_pedal)
        
        selected = st.selectbox(
            "Select Manual",
            pedal_names,
            index=idx,
            label_visibility="collapsed"
        )
        st.session_state.selected_pedal = selected
        
        # Pedal info
        pedal_info = next((p for p in pedals if p.pedal_name == selected), None)
        if pedal_info:
            st.caption(f"📄 {pedal_info.chunk_count} indexed chunks")
    else:
        st.warning("No manuals available")
        st.caption("Upload a manual first")
    
    st.markdown("---")
    
    # Navigation
    st.markdown("### Navigation")
    st.page_link("Home.py", label="🏠 Home")
    st.page_link("pages/2_📤_Upload.py", label="📤 Upload Manual")
    st.page_link("pages/3_📚_Library.py", label="📚 Manual Library")
    st.page_link("pages/4_⚙️_Settings.py", label="⚙️ Settings")
    
    st.markdown("---")
    
    # API Status
    is_healthy = client.health_check()
    status = "🟢 Online" if is_healthy else "🔴 Offline"
    st.caption(f"API: {status}")


# ============ HELPER FUNCTIONS ============
def parse_sources(sources):
    """Parse sources to extract page numbers."""
    parsed = []
    if not sources:
        return parsed
        
    for source in sources:
        page_match = re.search(r'Page (\d+)', source)
        section_match = re.search(r'Section: ([^,\]]+)', source)
        
        page = page_match.group(1) if page_match else None
        section = section_match.group(1).strip() if section_match else None
        
        # Clean content
        content = re.sub(r'\[Excerpt \d+ - Page \d+, Section: [^\]]+\]\s*', '', source)
        
        parsed.append({
            'page': page,
            'section': section,
            'content': content.strip()
        })
    
    return parsed


def display_message(role, content, metadata=None):
    """Display a chat message."""
    if role == "user":
        st.markdown(f'<div class="user-msg">{content}</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="assistant-msg">{content}</div>', unsafe_allow_html=True)
        
        if metadata:
            # Metadata row
            meta_items = []
            
            # INTERNAL TRACES HIDDEN FROM PRODUCTION UI
            # These are kept in metadata for logging but not displayed
            # if metadata.get('agent_path'):
            #     path = ' → '.join(metadata['agent_path'])
            #     meta_items.append(f"🧠 {path}")
            # 
            # if metadata.get('confidence') is not None:
            #     conf = int(metadata['confidence'] * 100)
            #     meta_items.append(f"📊 {conf}% confidence")
            # 
            # if metadata.get('latency_ms'):
            #     meta_items.append(f"⚡ {metadata['latency_ms']}ms")
            
            # Show fallback reason if present (helps users understand why query failed)
            fallback_reason = metadata.get('fallback_reason')
            if fallback_reason and fallback_reason != 'none':
                reason_labels = {
                    'ambiguous_query': '❓ Ambiguous question',
                    'low_relevance': '🔍 Low relevance match',
                    'concept_not_explicit': '📖 Not explicitly documented',
                    'data_missing': '❌ Not in manual',
                    'hallucination_detected': '⚠️ Uncertain answer',
                    'retrieval_failed': '🔄 Search failed',
                    'router_error': '🤔 Couldn\'t understand question'
                }
                reason_label = reason_labels.get(fallback_reason, fallback_reason)
                meta_items.append(reason_label)
            
            if meta_items:
                meta_html = ' '.join([f'<span class="meta-item">{m}</span>' for m in meta_items])
                st.markdown(f'<div class="meta-row">{meta_html}</div>', unsafe_allow_html=True)
            
            # Sources
            sources = metadata.get('sources', [])
            if sources:
                with st.expander(f"📎 View Sources ({len(sources)})", expanded=False):
                    parsed = parse_sources(sources)
                    for i, src in enumerate(parsed, 1):
                        title = f"Source {i}"
                        if src['page']:
                            title += f" · Page {src['page']}"
                        if src['section']:
                            title += f" · {src['section']}"
                        
                        preview = src['content'][:300] + "..." if len(src['content']) > 300 else src['content']
                        
                        st.markdown(f"""
                        <div class="source-box">
                            <div class="source-title">{title}</div>
                            {preview}
                        </div>
                        """, unsafe_allow_html=True)


# ============ MAIN CHAT AREA ============
st.markdown("## 💬 Chat")

selected_pedal = st.session_state.get("selected_pedal")
if selected_pedal:
    st.caption(f"Asking about: **{selected_pedal}**")
else:
    st.info(" Select a manual from the sidebar to start chatting.")
    st.stop()

# Display existing messages
for msg in st.session_state.messages:
    display_message(msg["role"], msg["content"], msg.get("metadata"))

# Chat input
if prompt := st.chat_input("Ask a question about the manual..."):
    # Add user message
    st.session_state.messages.append({
        "role": "user",
        "content": prompt
    })
    
    # Display user message immediately
    display_message("user", prompt)
    
    # Get response with loading state
    with st.spinner("Processing your question..."):
        # Show skeleton message while loading
        skeleton_placeholder = st.empty()
        skeleton_placeholder.markdown('<div style="margin: 12px 0;">', unsafe_allow_html=True)
        with skeleton_placeholder.container():
            skeleton_message()
        
        try:
            response = client.query(
                query=prompt,
                pedal_name=st.session_state.selected_pedal,
                conversation_id=st.session_state.conversation_id
            )
            
            # Update conversation ID
            st.session_state.conversation_id = response.conversation_id
            
            # Add assistant response
            st.session_state.messages.append({
                "role": "assistant",
                "content": response.answer,
                "metadata": {
                    "agent_path": response.agent_path,
                    "confidence": response.confidence,
                    "sources": response.sources,
                    "latency_ms": response.latency_ms,
                    "intent": response.intent,
                    "fallback_reason": response.fallback_reason
                }
            })
            
            # Clear skeleton and rerun
            skeleton_placeholder.empty()
            st.rerun()
            
        except Exception as e:
            st.error(f"Error: {str(e)}")
