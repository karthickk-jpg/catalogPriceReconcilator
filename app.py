import streamlit as st
from database.connection import init_db
from utils.helpers import get_logger

# Initialize application logger
logger = get_logger("app")

# Page Configuration
st.set_page_config(
    page_title="Catalog Price Validation Portal",
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

# Define native Streamlit dashboard view
dashboard_page = st.Page(
    "views/dashboard.py", 
    title="Dashboard", 
    icon="📊",
    default=True
)

# Build navigation menu structure for Dashboard-only
pg = st.navigation([dashboard_page])

# Run navigation engine
pg.run()
