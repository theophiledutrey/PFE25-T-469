import streamlit as st
from manager.core import GROUP_VARS_FILE
from manager.styles import load_css
from manager.pages import (
    render_dashboard,
    render_configuration,
    render_prerequisites,
    render_deploy,
    render_docs
)

def run_app():
    # Setup page config (Must be the first Streamlit command)
    st.set_page_config(
        page_title="REEF Manager",
        page_icon="🌊",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # Load styles
    load_css()

    if 'page' not in st.session_state:
        st.session_state.page = "Dashboard"
        
    with st.sidebar:
        #st.title("🌊 REEF")
        #st.markdown('<p style="color: #94a3b8; margin-top: -20px; font-size: 0.9em;">Security Automation</p>', unsafe_allow_html=True)
        st.markdown("---")
        
        # Navigation Buttons
        nav_options = [
            ("Dashboard", "📊"),
            ("Configuration", "⚙️"),
            ("Prerequisites Check", "✅"),
            ("Deploy & Manage", "🚀"),
            ("Documentation", "📚")
        ]
        
        for page_name, icon in nav_options:
            # Highlight active page button using type="primary" for the active one
            is_active = (st.session_state.page == page_name)
            btn_type = "primary" if is_active else "secondary"
            
            if st.button(f"{icon}  {page_name}", key=f"nav_{page_name}", width='stretch', type=btn_type):
                st.session_state.page = page_name
                st.rerun()

        st.markdown("---")
        status_color = "#34d399" if GROUP_VARS_FILE.exists() else "#f87171"
        status_text = "Ready" if GROUP_VARS_FILE.exists() else "Not Configured"
        st.markdown(f"""
        <div style="background: rgba(255,255,255,0.05); padding: 10px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.1); text-align: center;">
            <div style="color: #94a3b8; font-size: 0.8em; text-transform: uppercase; letter-spacing: 1px;">System Status</div>
            <div style="color: {status_color}; font-weight: bold; margin-top: 4px;">● {status_text}</div>
        </div>
        """, unsafe_allow_html=True)

    # Main Content Router
    page = st.session_state.page
    
    if page == "Dashboard":
        render_dashboard()
    elif page == "Configuration":
        render_configuration()
    elif page == "Prerequisites Check":
        render_prerequisites()
    elif page == "Deploy & Manage":
        render_deploy()
    elif page == "Documentation":
        render_docs()
