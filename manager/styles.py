import streamlit as st
from manager.core import GROUP_VARS_FILE

# We import GROUP_VARS_FILE only if needed for conditional styling in future, 
# but currently the styles are static except for some classes.

def load_css():
    st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Outfit', sans-serif;
    }

    /* Dark Theme Background & Text */
    .stApp {
        background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%);
        color: #e2e8f0;
    }
    
    /* Headers */
    h1, h2, h3 {
        color: #f8fafc !important;
        font-weight: 700;
        letter-spacing: -0.02em;
    }

    /* Cards / Containers */
    .css-card {
        background: rgba(255, 255, 255, 0.05);
        backdrop-filter: blur(10px);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 16px;
        padding: 2rem;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
        /* Ensure equal height appearance */
        height: 100%; 
        min-height: 18em;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
    }
    .css-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.2);
        border-color: rgba(99, 102, 241, 0.4);
    }
    
    /* Metrics */
    [data-testid="stMetric"] {
        background: rgba(255, 255, 255, 0.03);
        padding: 1rem;
        border-radius: 12px;
        border: 1px solid rgba(255, 255, 255, 0.05);
    }
    [data-testid="stMetricLabel"] {
        color: #94a3b8;
    }
    [data-testid="stMetricValue"] {
        color: #38bdf8;
        font-weight: 700;
    }

    /* Buttons (General/Secondary) */
    .stButton>button {
        background: rgba(255, 255, 255, 0.05);
        color: #e2e8f0;
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 8px;
        min-height: 3em;
        height: auto;
        padding: 1em 1.5em;
        font-weight: 500;
        transition: all 0.2s ease;
        line-height: 1.6;
        white-space: pre-wrap; /* Allow wrapping */
    }
    .stButton>button:hover {
        background: rgba(255, 255, 255, 0.1);
        border-color: rgba(255, 255, 255, 0.2);
        color: white;
    }

    /* Primary Button (Active Navigation / Actions) */
    .stButton>button[kind="primary"] {
        background: linear-gradient(90deg, #4f46e5 0%, #06b6d4 100%);
        color: white;
        border: none;
        font-weight: 600;
        box-shadow: 0 4px 14px 0 rgba(0,118,255,0.39);
    }
    .stButton>button[kind="primary"]:hover {
        transform: scale(1.02);
        box-shadow: 0 6px 20px rgba(0,118,255,0.23);
        border: none;
    }
    
    /* Inputs */
    .stTextInput>div>div>input {
        background-color: rgba(15, 23, 42, 0.6);
        color: white;
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 8px;
    }
    .stTextInput>div>div>input:focus {
        border-color: #38bdf8;
        box-shadow: 0 0 0 1px #38bdf8;
    }
    
    /* Sidebar */
    [data-testid="stSidebar"] {
        background-color: rgba(15, 23, 42, 0.95);
        border-right: 1px solid rgba(255, 255, 255, 0.05);
    }
    
    /* Success/Error/Info Messages overhaul */
    .stSuccess, .stInfo, .stWarning, .stError {
        background: rgba(16, 185, 129, 0.1) !important;
        border: 1px solid rgba(16, 185, 129, 0.2) !important;
        color: #34d399 !important;
        border-radius: 12px;
    }
    .stError {
        background: rgba(239, 68, 68, 0.1) !important;
        border-color: rgba(239, 68, 68, 0.2) !important;
        color: #f87171 !important;
    }
    .stWarning {
         background: rgba(245, 158, 11, 0.1) !important;
         border-color: rgba(245, 158, 11, 0.2) !important;
         color: #fbbf24 !important;
    }
    .stInfo {
        background: rgba(59, 130, 246, 0.1) !important;
        border-color: rgba(59, 130, 246, 0.2) !important;
        color: #60a5fa !important;
    }
    
    /* Header Tweaks */
    [data-testid="stHeader"] {
        background: transparent !important;
    }
    
    /* Remove the "Deploy" button specifically */
    .stDeployButton, 
    .stAppDeployButton,
    [data-testid="stDeployButton"],
    [data-testid="stAppDeployButton"] {
        display: none !important;
        visibility: hidden !important;
    }
    
    /* Hide the hamburger menu (Main Menu) */
    #MainMenu {
        visibility: hidden;
    }
    
    /* Hide the footer */
    footer {
        visibility: hidden;
    }
    
    /* Green Toggles */
    div[data-baseweb="checkbox"] div[aria-checked="true"] {
        background-color: #10b981 !important;
    }
    
</style>
""", unsafe_allow_html=True)
