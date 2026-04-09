import gspread
import json
import streamlit as st
from google.oauth2.service_account import Credentials

scopes = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly"]


@st.cache_resource(show_spinner=False)
def get_gspread_client() -> gspread.Client:
    """
    Build and return an authorised gspread client.
    Uses credentials from st.secrets["gcp_service_account"] if available (Streamlit Cloud),
    otherwise falls back to local credentials.json file.
    """

    try:
        sec = st.secrets["gcp_service_account"]
        creds = Credentials.from_service_account_info(sec, scopes=scopes)
    except Exception:
        # Fallback to local credentials.json
        with open("credentials.json", "r") as f:
            sec = json.load(f)
        creds = Credentials.from_service_account_info(sec, scopes=scopes)
    return gspread.authorize(creds)
