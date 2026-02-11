"""
Reusable Loading Components for PedalBot Frontend

Provides consistent loading states, progress indicators, and skeleton screens.
"""

import streamlit as st


def button_loading_state(is_loading, label, loading_label="Processing...", **kwargs):
    """
    Render a button with loading state.
    
    Args:
        is_loading: Boolean indicating if button should show loading state
        label: Button label when not loading
        loading_label: Button label when loading
        **kwargs: Additional arguments passed to st.button
    
    Returns:
        Boolean indicating if button was clicked
    """
    if is_loading:
        st.markdown(f"""
        <div style="text-align: center; padding: 8px 16px;">
            <span class="btn-spinner"></span>
            <span style="margin-left: 8px;">{loading_label}</span>
        </div>
        """, unsafe_allow_html=True)
        return False
    else:
        return st.button(label, **kwargs)


def skeleton_card(count=1):
    """Render skeleton loading cards."""
    for _ in range(count):
        st.markdown("""
        <div class="skeleton-card">
            <div class="skeleton-title"></div>
            <div class="skeleton-text"></div>
            <div class="skeleton-text short"></div>
        </div>
        """, unsafe_allow_html=True)


def skeleton_message():
    """Render skeleton loading message."""
    st.markdown("""
    <div class="skeleton-message">
        <div class="skeleton-text"></div>
        <div class="skeleton-text"></div>
        <div class="skeleton-text short"></div>
    </div>
    """, unsafe_allow_html=True)


def skeleton_list(count=3):
    """Render skeleton loading list items."""
    for _ in range(count):
        st.markdown("""
        <div class="skeleton-list-item">
            <div class="skeleton-title small"></div>
            <div class="skeleton-text short"></div>
        </div>
        """, unsafe_allow_html=True)


def progress_bar(progress, label=""):
    """
    Render a custom progress bar.
    
    Args:
        progress: Float between 0 and 1
        label: Optional label to display
    """
    percent = int(progress * 100)
    st.markdown(f"""
    <div class="progress-container">
        {f'<div class="progress-label">{label}</div>' if label else ''}
        <div class="progress-bar">
            <div class="progress-fill" style="width: {percent}%"></div>
        </div>
        <div class="progress-percent">{percent}%</div>
    </div>
    """, unsafe_allow_html=True)


def loading_spinner(text="Loading..."):
    """Render a custom loading spinner."""
    st.markdown(f"""
    <div class="loading-container">
        <div class="loading-spinner"></div>
        <div class="loading-text">{text}</div>
    </div>
    """, unsafe_allow_html=True)


def upload_progress(filename, progress, status="Uploading"):
    """
    Render upload progress indicator.
    
    Args:
        filename: Name of file being uploaded
        progress: Float between 0 and 1
        status: Status text (Uploading, Processing, Complete, etc.)
    """
    percent = int(progress * 100)
    status_colors = {
        "Uploading": "#3b82f6",
        "Processing": "#f59e0b",
        "Complete": "#22c55e",
        "Error": "#ef4444",
    }
    color = status_colors.get(status, "#3b82f6")
    
    st.markdown(f"""
    <div class="upload-progress">
        <div class="upload-header">
            <div class="upload-filename">{filename}</div>
            <div class="upload-status" style="color: {color}">{status}</div>
        </div>
        <div class="progress-bar">
            <div class="progress-fill" style="width: {percent}%; background-color: {color}"></div>
        </div>
        <div class="upload-percent">{percent}%</div>
    </div>
    """, unsafe_allow_html=True)
