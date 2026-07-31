import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="TechServe / SupportX", layout="wide")

page = st.query_params.get("page", "home")

if page == "support":
    # SupportX app manages its own internal scrolling per page —
    # lock the outer Streamlit page so only the app itself scrolls.
    st.markdown("""
        <style>
            .block-container { padding: 0 !important; margin: 0 !important; max-width: 100% !important; }
            header {visibility: hidden;}
            footer {visibility: hidden;}
            #MainMenu {visibility: hidden;}
            iframe { height: 100vh !important; display: block; }
            html, body { overflow: hidden !important; }
        </style>
    """, unsafe_allow_html=True)
    file_to_load = "frontend/index.html"
    iframe_height = 1200
    scrolling = False
else:
    # home.html is a normal long marketing page — let the whole page
    # scroll naturally instead of locking it.
    st.markdown("""
        <style>
            .block-container { padding: 0 !important; margin: 0 !important; max-width: 100% !important; }
            header {visibility: hidden;}
            footer {visibility: hidden;}
            #MainMenu {visibility: hidden;}
            iframe { display: block; border: none; }
        </style>
    """, unsafe_allow_html=True)
    file_to_load = "home.html"
    iframe_height = 1900
    scrolling = True

with open(file_to_load, "r", encoding="utf-8") as f:
    html_content = f.read()

components.html(html_content, height=iframe_height, scrolling=scrolling)