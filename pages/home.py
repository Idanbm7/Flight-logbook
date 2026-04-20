"""
pages/home.py — Home screen.
Layout: title → brightened Heron image → 2×2 navigation buttons.
"""

import os
import streamlit as st

_ROOT     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_BG_IMAGE = os.path.join(_ROOT, "Heron1.jpg")


def _load_brightened(path: str, factor: float = 1.5):
    try:
        from PIL import Image, ImageEnhance
    except ImportError:
        import subprocess, sys
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "Pillow"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        from PIL import Image, ImageEnhance
    try:
        return ImageEnhance.Brightness(Image.open(path)).enhance(factor)
    except Exception:
        return None


def render():
    # 1 ▸ Title — top of page
    st.title("FLIGHT LOGBOOK")

    # 2 ▸ Brightened Heron image directly below title
    img = _load_brightened(_BG_IMAGE, factor=1.5)
    if img:
        st.image(img, use_container_width=True)

    # 3 ▸ 2×2 navigation grid — all buttons use_container_width=True
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🏠  HOME", use_container_width=True):
            st.session_state.page = "home"
            st.rerun()
    with col2:
        if st.button("➕  NEW FLIGHT", use_container_width=True):
            st.session_state.page = "new_flight"
            st.rerun()

    col3, col4 = st.columns(2)
    with col3:
        if st.button("📋  MY FLIGHTS", use_container_width=True):
            st.session_state.page = "flight_history"
            st.rerun()
    with col4:
        if st.button("⚙️  SETTINGS", use_container_width=True):
            st.session_state.page = "settings"
            st.rerun()
