import streamlit as st
from manager.core import BASE_DIR

def render_docs():
    st.title("Documentation")
    docs_dir = BASE_DIR / "docs"
    docs = list(docs_dir.glob("*.md")) + [BASE_DIR / "README.md"]
    
    doc = st.selectbox("Select Document", [d.name for d in docs])
    
    selected_path = next((d for d in docs if d.name == doc), None)
    if selected_path:
        st.markdown(selected_path.read_text())
