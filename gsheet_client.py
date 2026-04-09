import gspread
import streamlit as st
from google.oauth2.service_account import Credentials

@st.cache_resource
def get_gspread_client():
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]

    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],  # Directly read from secrets
        scopes=scope
    )

    client = gspread.authorize(creds)
    return client
