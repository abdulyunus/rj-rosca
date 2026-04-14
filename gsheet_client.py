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

    sec = None
    try:
        # Supported format A: st.secrets["gcp_service_account"] as dict
        # Supported format B: st.secrets["google"]["gcp_service_account"] as JSON string
        if "gcp_service_account" in st.secrets:
            sec = st.secrets["gcp_service_account"]
        elif "google" in st.secrets and "gcp_service_account" in st.secrets["google"]:
            sec = st.secrets["google"]["gcp_service_account"]

        if isinstance(sec, str):
            sec = json.loads(sec)

        if sec:
            creds = Credentials.from_service_account_info(sec, scopes=scopes)
            return gspread.authorize(creds)
    except Exception:
        pass

    # Fallback to local credentials.json for local development
    with open("credentials.json", "r") as f:
        sec = json.load(f)
    creds = Credentials.from_service_account_info(sec, scopes=scopes)
    return gspread.authorize(creds)
