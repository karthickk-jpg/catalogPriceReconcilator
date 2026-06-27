import streamlit as st
from database.connection import init_db
from utils.helpers import get_logger

# Initialize application logger
logger = get_logger("app")

# Page Configuration
st.set_page_config(
    page_title="Catalog Price Reconciliation Portal",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize database schemas on application startup
try:
    pass  # init_db() is removed as part of database migration
except Exception as e:
    st.error("Failed to connect or initialize the local database. See application logs for details.")
    logger.critical(f"Critical error during database setup: {str(e)}", exc_info=True)

# Define native Streamlit multi-page views
dashboard_page = st.Page(
    "views/dashboard.py", 
    title="Dashboard", 
    icon="📊",
    default=True
)

history_page = st.Page(
    "views/history.py", 
    title="Run History Audit", 
    icon="📜"
)

reconcile_page = st.Page(
    "views/reconcile.py", 
    title="New Reconciliation Run", 
    icon="🔄"
)

settings_page = st.Page(
    "views/settings.py", 
    title="Portal Settings", 
    icon="⚙️"
)

# Build navigation menu structure
pg = st.navigation({
    "Overview": [dashboard_page],
    "Operations": [reconcile_page, history_page],
    "Administration": [settings_page]
})

# Run navigation engine
pg.run()
