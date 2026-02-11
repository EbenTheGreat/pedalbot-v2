# PedalBot UI Enhancements

This document summarizes the visual and UX improvements made to the PedalBot Streamlit application.

## 🎨 Design Philosophy
The goal was to move from a standard "bootstrap-like" look to a premium, modern, and vibrant interface that feels alive and responsive.

## ✨ Key Enhancements

### 🌗 Dynamic Theme Engine
- **Dark/Light Mode**: Users can now toggle between a sleek "Deep Slate" dark mode and a clean, high-contrast light mode.
- **Persistence**: Theme status is managed via Streamlit session state.
- **Centralized Management**: All styles are defined in `frontend/utils/styles.py` and shared across all pages.

### 💎 Premium Aesthetics
- **Glassmorphism**: Subtle backdrop blur effects on cards, sidebars, and chat messages.
- **Enhanced Typography**: Integrated Google Fonts (Inter) for a modern, readable feel.
- **Vibrant Gradients**: 
    - Main logo utilizes a `3b82f6` to `ec4899` (Blue to Pink) gradient.
    - User message bubbles use a linear blue gradient for a "Message App" feel.
    - Metrics now feature a gradient value display.
- **Shadows & Depth**: Implemented multi-layered shadows for cards and message bubbles to create visual hierarchy.

### 🕹️ Interactive Elements
- **Micro-animations**: 
    - Cards lift and glow on hover.
    - Smooth transitions for theme switching.
- **Custom Scrollbars**: Modern, thin scrollbars that match the theme colors.
- **Sidebar UX**: Fixed the visibility of the sidebar toggle button by ensuring the application header remains visible but transparent.

### 💬 Chat Experience
- **Bubble Design**: Distinct styles for user (right-aligned, gradient) and assistant (left-aligned, glass card) messages.
- **Source Citations**: Redesigned source citation boxes with emphasis on the specific page and section.
- **Metadata Badges**: Clean, pill-shaped badges for agent path, confidence score, and latency.

## 📁 Files Modified
- `frontend/utils/styles.py` (Created) - The core design system.
- `frontend/Home.py` - Updated to use the new system and revamped the landing page.
- `frontend/pages/1_💬_Chat.py` - Major overhaul of the chat interface.
- `frontend/pages/2_📤_Upload.py` - Refined upload flow and status cards.
- `frontend/pages/3_📚_Library.py` - Enhanced manual library with thematic badges.
- `frontend/pages/4_⚙️_Settings.py` - Cleaned up settings layout.

## 🚀 Future Roadmap
- Implementation of a "Full Screen" mode for the chat.
- Real-time indexing progress bars with more granular steps.
- Hover-over definitions for technical terms in the manual.
