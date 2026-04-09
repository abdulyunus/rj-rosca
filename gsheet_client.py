import gspread
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
    creds_dict = dict(st.secrets["gcp_service_account"])   # mapping → plain dict
    print("Printing the creds")
    print(creds_dict)
    print("Credentials printed done!")
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    return gspread.authorize(creds)
