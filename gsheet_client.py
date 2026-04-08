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
        # Remove leading/trailing whitespace and ensure valid JSON
        cred_json = st.secrets["google"]["gcp_service_account"].strip()
        # If TOML escaping added extra newlines, fix them
        if cred_json.startswith('"""') and cred_json.endswith('"""'):
            cred_json = cred_json[3:-3].strip()
        # Try to parse and re-dump to ensure valid JSON
        cred_dict = json.loads(cred_json)
        with open("credentials.json", "w") as f:
            json.dump(cred_dict, f)
    creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
    return gspread.authorize(creds)
