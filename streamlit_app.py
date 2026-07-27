import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="SupportX", layout="wide")

with open("frontend/index.html", "r", encoding="utf-8") as f:
    html_content = f.read()

components.html(html_content, height=900, scrolling=True)