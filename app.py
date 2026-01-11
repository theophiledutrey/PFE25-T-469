import sys
from pathlib import Path
import streamlit as st

# Set up path to include local modules (reef.py and manager package)
current_dir = str(Path(__file__).parent.resolve())
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

try:
    from manager import run_app
except ImportError as e:
    st.error(f"Error loading application modules: {e}")
    st.stop()

if __name__ == "__main__":
    run_app()
