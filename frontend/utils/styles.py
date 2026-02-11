import streamlit as st
from .design_tokens import get_colors, TYPOGRAPHY, SPACING, RADIUS, SHADOWS, ANIMATIONS

def init_styles():
    """Initialize theme and inject global CSS using design tokens."""
    
    # Initialize theme in session state
    if "theme" not in st.session_state:
        st.session_state.theme = "dark"

    # Theme toggle in sidebar
    with st.sidebar:
        st.markdown("### Theme Control")
        
        # Show the opposite theme as the button label
        button_label = "🌙 Dark Mode" if st.session_state.theme == "light" else "☀️ Light Mode"
        
        if st.button(button_label, use_container_width=True):
            # Toggle theme
            st.session_state.theme = "light" if st.session_state.theme == "dark" else "dark"
            st.rerun()
        
        st.markdown("---")

    # Get theme colors
    colors = get_colors(st.session_state.theme)
    
    # Extract frequently used values
    bg_app = colors["bg_app"]
    bg_sidebar = colors["bg_sidebar"]
    bg_card = colors["bg_card"]
    bg_card_hover = colors["bg_card_hover"]
    bg_assistant = colors["bg_assistant"]
    bg_source = colors["bg_source"]
    text_primary = colors["text_primary"]
    text_secondary = colors["text_secondary"]
    text_tertiary = colors["text_tertiary"]
    border_subtle = colors["border_subtle"]
    border_medium = colors["border_medium"]
    primary = colors["primary"]
    primary_hover = colors["primary_hover"]
    success = colors["success"]
    warning = colors["warning"]
    error = colors["error"]
    meta_bg = colors["meta_bg"]
    meta_border = colors["meta_border"]

    # Typography
    font_family = TYPOGRAPHY["font_family"]
    
    # Spacing
    spacing_sm = SPACING["sm"]
    spacing_md = SPACING["md"]
    spacing_base = SPACING["base"]
    spacing_lg = SPACING["lg"]
    spacing_xl = SPACING["xl"]
    spacing_2xl = SPACING["2xl"]
    
    # Radius
    radius_sm = RADIUS["sm"]
    radius_md = RADIUS["md"]
    radius_lg = RADIUS["lg"]
    
    # Shadows
    shadow_card = SHADOWS["card"]
    shadow_card_hover = SHADOWS["card_hover"]
    shadow_subtle = SHADOWS["subtle"]
    
    # Animations
    anim_normal = ANIMATIONS["normal"]
    anim_fast = ANIMATIONS["fast"]
    easing = ANIMATIONS["easing"]
    lift_md = ANIMATIONS["lift_md"]

    # Global CSS injection
    st.markdown(f"""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

        /* ============ BASE STYLES ============ */
        .stApp {{ 
            background-color: {bg_app}; 
            color: {text_primary};
            font-family: {font_family};
        }}
        
        /* Show the header so sidebar can be reopened */
        header {{ 
            visibility: visible !important; 
            background: rgba(0,0,0,0) !important;
        }}
        
        /* Sidebar styling */
        [data-testid="stSidebar"] {{ 
            background-color: {bg_sidebar}; 
            border-right: 1px solid {border_subtle};
        }}
        
        /* ============ CARD COMPONENTS ============ */
        .card {{
            background: {bg_card};
            border: 1px solid {border_subtle};
            border-radius: {radius_md};
            padding: {spacing_xl};
            margin-bottom: {spacing_base};
            transition: all {anim_normal} {easing};
            box-shadow: none;
        }}
        
        .card:hover {{
            transform: translateY(-2px);
            border-color: {border_medium};
            background: {bg_card_hover};
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
        }}
        
        /* ============ MESSAGE BUBBLES ============ */
        .user-msg {{
            background: {primary};
            color: white;
            padding: 14px 18px;
            border-radius: {radius_md};
            margin: {spacing_md} 0;
            max-width: 85%;
            margin-left: auto;
            box-shadow: none;
            font-weight: 400;
            transition: transform {anim_fast} {easing};
        }}
        
          .assistant-msg {{
            background: {bg_assistant};
            border: 1px solid {border_subtle};
            color: {text_primary};
            padding: {spacing_lg};
            border-radius: {radius_md};
            margin: {spacing_md} 0;
            line-height: 1.6;
            box-shadow: none;
        }}
        
        /* ============ SOURCE CITATIONS ============ */
        .source-box {{
            background: {bg_source};
            border-left: 3px solid {primary};
            padding: {spacing_base};
            margin: {spacing_md} 0;
            font-size: 14px;
            color: {text_secondary};
            border-radius: {radius_sm};
            border: 1px solid {border_subtle};
            border-left: 3px solid {primary};
        }}
        
        .source-title {{
            color: {primary};
            font-weight: 700;
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: {spacing_sm};
        }}
        
        /* ============ METADATA TAGS ============ */
        .meta-row {{
            display: flex;
            flex-wrap: wrap;
            gap: {spacing_sm};
            margin-top: 14px;
            font-size: 12px;
            font-weight: 500;
            color: {text_secondary};
        }}
        
        .meta-item {{
            background: {meta_bg};
            padding: {spacing_sm} {spacing_md};
            border-radius: {radius_sm};
            border: 1px solid {meta_border};
            display: flex;
            align-items: center;
            gap: {spacing_sm};
        }}
        
        /* ============ BUTTONS ============ */
        .stButton>button {{
            border-radius: {radius_md};
            font-weight: 600;
            transition: all {anim_normal} {easing};
            position: relative;
            z-index: 1;
            border: 1px solid {border_medium};
            background-color: {bg_card} !important;
            color: {text_primary} !important;
        }}
        
        .stButton>button:hover {{
            transform: none;
            opacity: 0.9;
            background-color: {bg_card_hover} !important;
            border-color: {primary} !important;
        }}
        
        .stButton>button[kind="primary"] {{
            background-color: {primary} !important;
            color: white !important;
            border-color: {primary} !important;
        }}
        
        .stButton>button[kind="primary"]:hover {{
            background-color: {primary_hover} !important;
        }}
        
        /* ============ METRICS ============ */
        [data-testid="stMetricValue"] {{
            font-weight: 700;
            color: {primary};
        }}
        
        /* ============ TEXT COLORS ============ */
        .stMarkdown, .stText, p, li, label, .stMetric, [data-testid="stMetricValue"], .stCaption {{
            color: {text_primary} !important;
        }}
        
        .stCaption, p.small-text {{
            color: {text_secondary} !important;
        }}
        
        /* ============ SIDEBAR TEXT COLORS ============ */
        /* Force dark text in sidebar for light mode */
        [data-testid="stSidebar"] * {{
            color: {text_primary} !important;
        }}
        
        [data-testid="stSidebar"] .stMarkdown {{
            color: {text_primary} !important;
        }}
        
        [data-testid="stSidebar"] h1, 
        [data-testid="stSidebar"] h2, 
        [data-testid="stSidebar"] h3, 
        [data-testid="stSidebar"] h4, 
        [data-testid="stSidebar"] h5, 
        [data-testid="stSidebar"] h6 {{
            color: {text_primary} !important;
        }}
        
        [data-testid="stSidebar"] p, 
        [data-testid="stSidebar"] span, 
        [data-testid="stSidebar"] a, 
        [data-testid="stSidebar"] label {{
            color: {text_primary} !important;
        }}
        
        [data-testid="stSidebar"] .stButton>button {{
            color: {text_primary} !important;
            background: {bg_card} !important;
            border: 1px solid {border_medium} !important;
        }}
        
        [data-testid="stSidebar"] .stButton>button:hover {{
            background: {bg_card_hover} !important;
        }}
        
        /* ============ MAIN CONTENT TEXT COLORS ============ */
        /* Ensure all main content text is visible in light mode */
        .main .stMarkdown {{
            color: {text_primary} !important;
        }}
        
        .main h1, .main h2, .main h3, .main h4, .main h5, .main h6 {{
            color: {text_primary} !important;
        }}
        
        .main p, .main span, .main li, .main label, .main div {{
            color: {text_primary} !important;
        }}
        
        /* ============ FILE UPLOADER ============ */
        /* File uploader text */
        [data-testid="stFileUploader"] label {{
            color: {text_primary} !important;
        }}
        
        [data-testid="stFileUploader"] small {{
            color: {text_secondary} !important;
        }}
        
        /* File uploader drag and drop zone */
        [data-testid="stFileUploader"] {{
            position: relative;
            z-index: 1;
        }}
        
        [data-testid="stFileUploader"] section {{
            background-color: {bg_card} !important;
            border: 2px dashed {border_medium} !important;
            border-radius: {radius_md} !important;
            padding: {spacing_xl} !important;
            position: relative;
            z-index: 1;
            transition: all {anim_normal} {easing};
        }}
        
        [data-testid="stFileUploader"] section:hover {{
            border-color: {primary} !important;
            background-color: {bg_card_hover} !important;
        }}
        
        [data-testid="stFileUploader"] section button {{
            background-color: {bg_card} !important;
            color: {text_primary} !important;
            border: 1px solid {border_medium} !important;
            position: relative;
            z-index: 2;
        }}
        
        /* File uploader icon and text */
        [data-testid="stFileUploader"] section svg {{
            color: {text_secondary} !important;
            opacity: 1 !important;
        }}
        
        [data-testid="stFileUploader"] section span {{
            color: {text_primary} !important;
            opacity: 1 !important;
        }}
        
        /* ============ TEXT INPUTS ============ */
        /* Text input styling */
        [data-testid="stTextInput"] {{
            position: relative;
            z-index: 1;
        }}
        
        [data-testid="stTextInput"] input {{
            background-color: {bg_card} !important;
            color: {text_primary} !important;
            border: 1px solid {border_medium} !important;
            border-radius: {radius_md} !important;
            position: relative;
            z-index: 1;
        }}
        
        [data-testid="stTextInput"] input:focus {{
            border-color: {primary} !important;
            outline: none !important;
            box-shadow: 0 0 0 1px {primary} !important;
        }}
        
        [data-testid="stTextInput"] input:disabled {{
            opacity: 0.6;
            cursor: not-allowed;
        }}
        
        /* Success/Info/Error text */
        .stSuccess, .stInfo, .stWarning, .stError {{
            color: {text_primary} !important;
        }}


        /* ============ SCROLLBAR ============ */
        ::-webkit-scrollbar {{
            width: 8px;
            height: 8px;
        }}
        ::-webkit-scrollbar-track {{
            background: rgba(0,0,0,0.05);
        }}
        ::-webkit-scrollbar-thumb {{
            background: {border_subtle};
            border-radius: {radius_sm};
        }}
        ::-webkit-scrollbar-thumb:hover {{
            background: {text_secondary};
        }}
        
        /* ============ LOADING STATES ============ */
        .btn-spinner {{
            display: inline-block;
            width: 14px;
            height: 14px;
            border: 2px solid rgba(255,255,255,0.3);
            border-radius: 50%;
            border-top-color: white;
            animation: spin {anim_normal} linear infinite;
        }}
        
        @keyframes spin {{
            to {{ transform: rotate(360deg); }}
        }}
        
        .loading-container {{
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: {spacing_md};
            padding: {spacing_2xl};
        }}
        
        .loading-spinner {{
            width: 40px;
            height: 40px;
            border: 3px solid {border_subtle};
            border-radius: 50%;
            border-top-color: {primary};
            animation: spin {anim_normal} linear infinite;
        }}
        
        .loading-text {{
            color: {text_secondary};
            font-size: 14px;
        }}
        
        /* ============ SKELETON SCREENS ============ */
        @keyframes skeleton-pulse {{
            0%, 100% {{ opacity: 1; }}
            50% {{ opacity: 0.5; }}
        }}
        
        .skeleton-card {{
            background: {bg_card};
            border: 1px solid {border_subtle};
            border-radius: {radius_md};
            padding: {spacing_xl};
            margin-bottom: {spacing_base};
        }}
        
        .skeleton-title {{
            height: 24px;
            background: {border_subtle};
            border-radius: {radius_sm};
            margin-bottom: {spacing_md};
            animation: skeleton-pulse 1.5s {easing} infinite;
        }}
        
        .skeleton-text {{
            height: 16px;
            background: {border_subtle};
            border-radius: {radius_sm};
            margin-bottom: {spacing_sm};
            animation: skeleton-pulse 1.5s {easing} infinite;
        }}
        
        .skeleton-text.short {{
            width: 60%;
        }}
        
        .skeleton-message {{
            background: {bg_assistant};
            border: 1px solid {border_subtle};
            padding: {spacing_lg};
            border-radius: {radius_sm} {radius_lg} {radius_lg} {radius_lg};
            margin: {spacing_md} 0;
        }}
        
        .skeleton-list-item {{
            padding: {spacing_md};
            border-bottom: 1px solid {border_subtle};
        }}
        
        .skeleton-title.small {{
            height: 18px;
            width: 40%;
        }}
        
        /* ============ PROGRESS BARS ============ */
        .progress-container {{
            margin: {spacing_base} 0;
        }}
        
        .progress-label {{
            font-size: 14px;
            color: {text_secondary};
            margin-bottom: {spacing_sm};
        }}
        
        .progress-bar {{
            width: 100%;
            height: 8px;
            background: {border_subtle};
            border-radius: {radius_sm};
            overflow: hidden;
        }}
        
        .progress-fill {{
            height: 100%;
            background: {primary};
            border-radius: {radius_sm};
            transition: width {anim_normal} {easing};
        }}
        
        .progress-percent {{
            font-size: 12px;
            color: {text_tertiary};
            margin-top: {spacing_sm};
            text-align: right;
        }}
        
        .upload-progress {{
            background: {bg_card};
            border: 1px solid {border_subtle};
            border-radius: {radius_md};
            padding: {spacing_base};
            margin: {spacing_md} 0;
        }}
        
        .upload-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: {spacing_sm};
        }}
        
        .upload-filename {{
            font-weight: 600;
            color: {text_primary};
            font-size: 14px;
        }}
        
        .upload-status {{
            font-size: 12px;
            font-weight: 600;
        }}
        
        .upload-percent {{
            font-size: 12px;
            color: {text_tertiary};
            margin-top: {spacing_sm};
        }}
        
        /* ============ STATUS CARDS ============ */
        .status-card {{
            background: {bg_card};
            border: 1px solid {border_subtle};
            border-radius: {radius_md};
            padding: {spacing_base};
            margin: {spacing_sm} 0;
            transition: all {anim_normal} {easing};
        }}
        
        .status-pending {{ border-left: 3px solid {warning}; }}
        .status-processing {{ border-left: 3px solid {primary}; }}
        .status-completed {{ border-left: 3px solid {success}; }}
        .status-failed {{ border-left: 3px solid {error}; }}
        
        /* Hide menu but keep header */
        #MainMenu, footer {{ visibility: hidden; }}
    </style>
    """, unsafe_allow_html=True)
