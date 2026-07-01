import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import streamlit as st

from utils.helpers import get_logger

logger = get_logger("app")

st.set_page_config(
    page_title="Catalog Price Validation Portal",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="collapsed",
)

from views.dashboard import render_dashboard

render_dashboard()
