import gspread
from oauth2client.service_account import ServiceAccountCredentials
import streamlit as st
import json

def get_gspread_client():
    scope = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive'
    ]
    # Write credentials from Streamlit secrets to a file if running on Streamlit Cloud
    if "google" in st.secrets and "gcp_service_account" in st.secrets["google"]:
        with open("credentials.json", "w") as f:
            f.write(st.secrets["google"]["gcp_service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
    return gspread.authorize(creds)
