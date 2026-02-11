"""
Design Tokens for PedalBot Frontend

Centralized design system tokens for colors, typography, spacing, shadows,
border radius, and animations. All components should reference these tokens
instead of hardcoding values.
"""

# ============ COLOR PALETTE ============

COLORS_DARK = {
    # Surface colors
    "bg_app": "#0f172a",
    "bg_sidebar": "#1e293b",
    "bg_card": "rgba(30, 41, 59, 0.7)",
    "bg_card_hover": "rgba(30, 41, 59, 0.85)",
    "bg_input": "rgba(15, 23, 42, 0.6)",
    "bg_assistant": "rgba(30, 41, 59, 0.5)",
    "bg_source": "rgba(15, 23, 42, 0.8)",
    
    # Text colors
    "text_primary": "#f1f5f9",
    "text_secondary": "#94a3b8",
    "text_tertiary": "#64748b",
    
    # Border colors
    "border_subtle": "rgba(255, 255, 255, 0.1)",
    "border_medium": "rgba(255, 255, 255, 0.15)",
    
    # Semantic colors
    "primary": "#2563eb",
    "primary_hover": "#1d4ed8",
    "success": "#22c55e",
    "warning": "#f59e0b",
    "error": "#ef4444",
    "info": "#3b82f6",
    
    # Meta/tag backgrounds
    "meta_bg": "rgba(0, 0, 0, 0.2)",
    "meta_border": "rgba(255, 255, 255, 0.05)",
}

COLORS_LIGHT = {
    # Surface colors - ChatGPT style
    "bg_app": "#ffffff",  # Pure white like ChatGPT
    "bg_sidebar": "#f9f9f9",  # Very subtle gray sidebar
    "bg_card": "#ffffff",  # Clean white cards
    "bg_card_hover": "#f7f7f8",  # Subtle hover
    "bg_input": "#ffffff",
    "bg_assistant": "#f7f7f8",  # Very light gray for assistant messages
    "bg_source": "#ffffff",
    
    # Text colors - ChatGPT style
    "text_primary": "#2e3338",  # Near-black, not pure black
    "text_secondary": "#6e6e80",  # Medium gray
    "text_tertiary": "#9a9a9f",  # Light gray
    
    # Border colors - Very subtle like ChatGPT
    "border_subtle": "rgba(0, 0, 0, 0.06)",
    "border_medium": "rgba(0, 0, 0, 0.1)",
    
    # Semantic colors
    "primary": "#2563eb",
    "primary_hover": "#1d4ed8",
    "success": "#10a37f",  # ChatGPT green
    "warning": "#f59e0b",
    "error": "#ef4444",
    "info": "#3b82f6",
    
    # Meta/tag backgrounds
    "meta_bg": "#ececf1",  # Light gray like ChatGPT tags
    "meta_border": "rgba(0, 0, 0, 0.08)",
}


# ============ TYPOGRAPHY ============

TYPOGRAPHY = {
    # Font family
    "font_family": "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
    
    # Type scale (size / weight / line-height)
    "display": {"size": "32px", "weight": "700", "line_height": "1.2"},
    "h1": {"size": "24px", "weight": "700", "line_height": "1.3"},
    "h2": {"size": "20px", "weight": "600", "line_height": "1.4"},
    "h3": {"size": "18px", "weight": "600", "line_height": "1.4"},
    "h4": {"size": "16px", "weight": "600", "line_height": "1.5"},
    "body": {"size": "16px", "weight": "400", "line_height": "1.6"},
    "small": {"size": "14px", "weight": "400", "line_height": "1.5"},
    "caption": {"size": "12px", "weight": "500", "line_height": "1.4"},
}


# ============ SPACING SCALE ============
# All spacing uses 4px base unit

SPACING = {
    "xs": "4px",
    "sm": "8px",
    "md": "12px",
    "base": "16px",
    "lg": "20px",
    "xl": "24px",
    "2xl": "32px",
    "3xl": "40px",
    "4xl": "48px",
    "5xl": "64px",
}


# ============ BORDER RADIUS ============

RADIUS = {
    "sm": "6px",     # inputs, tags, small elements
    "md": "12px",    # cards, buttons, standard containers
    "lg": "18px",    # modals, large containers, message bubbles
}


# ============ SHADOWS ============

SHADOWS = {
    "subtle": "0 1px 3px rgba(0, 0, 0, 0.12)",
    "medium": "0 4px 6px rgba(0, 0, 0, 0.1)",
    "large": "0 10px 20px rgba(0, 0, 0, 0.15)",
    "card": "0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)",
    "card_hover": "0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)",
}


# ============ ANIMATIONS ============

ANIMATIONS = {
    # Duration
    "fast": "150ms",
    "normal": "250ms",
    "slow": "350ms",
    
    # Easing (Material Design standard)
    "easing": "cubic-bezier(0.4, 0.0, 0.2, 1)",
    "easing_in": "cubic-bezier(0.4, 0.0, 1, 1)",
    "easing_out": "cubic-bezier(0.0, 0.0, 0.2, 1)",
    
    # Hover lift
    "lift_sm": "2px",
    "lift_md": "3px",
}


# ============ HELPER FUNCTIONS ============

def get_colors(theme="dark"):
    """Get color tokens for the specified theme."""
    return COLORS_DARK if theme == "dark" else COLORS_LIGHT


def generate_css_vars(theme="dark"):
    """Generate CSS custom properties from design tokens."""
    colors = get_colors(theme)
    
    # Build CSS variables string
    css_vars = []
    
    # Colors
    for key, value in colors.items():
        css_vars.append(f"    --{key.replace('_', '-')}: {value};")
    
    # Typography
    for key, values in TYPOGRAPHY.items():
        if key != "font_family":
            css_vars.append(f"    --font-{key}-size: {values['size']};")
            css_vars.append(f"    --font-{key}-weight: {values['weight']};")
            css_vars.append(f"    --font-{key}-line-height: {values['line_height']};")
    
    # Spacing
    for key, value in SPACING.items():
        css_vars.append(f"    --spacing-{key}: {value};")
    
    # Radius
    for key, value in RADIUS.items():
        css_vars.append(f"    --radius-{key}: {value};")
    
    # Shadows
    for key, value in SHADOWS.items():
        css_vars.append(f"    --shadow-{key}: {value};")
    
    # Animations
    for key, value in ANIMATIONS.items():
        css_vars.append(f"    --anim-{key.replace('_', '-')}: {value};")
    
    return ":root {\n" + "\n".join(css_vars) + "\n}"
