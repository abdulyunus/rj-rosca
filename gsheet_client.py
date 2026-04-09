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
    Credentials are read from st.secrets["gcp_service_account"].
    """
    
    sec = st.secrets["gcp_service_account"]
    creds = Credentials.from_service_account_info(sec, scopes=scopes)
    return gspread.authorize(creds)
