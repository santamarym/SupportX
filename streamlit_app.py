import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="TechServe / SupportX", layout="wide")

st.markdown("""
    <style>
        .block-container {
            padding: 0 !important;
            margin: 0 !important;
            max-width: 100% !important;
        }
        header {visibility: hidden;}
        footer {visibility: hidden;}
        #MainMenu {visibility: hidden;}
        iframe {
            height: 100vh !important;
            display: block;
        }
        html, body {
            overflow: hidden !important;
        }
    </style>
""", unsafe_allow_html=True)

# Decide which page to show based on a URL parameter, e.g. ?page=support
page = st.query_params.get("page", "home")

file_to_load = "frontend/index.html" if page == "support" else "home.html"

with open(file_to_load, "r", encoding="utf-8") as f:
    html_content = f.read()

components.html(html_content, height=1200, scrolling=False)