import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="SupportX", layout="wide")

# Remove Streamlit's default padding, header, and footer so the embedded
# app fills the whole browser window instead of sitting inside a white box
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
    </style>
""", unsafe_allow_html=True)

with open("frontend/index.html", "r", encoding="utf-8") as f:
    html_content = f.read()

components.html(html_content, height=1000, scrolling=True)