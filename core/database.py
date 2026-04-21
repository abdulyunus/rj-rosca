"""
Database/Google Sheets client initialization and management
"""

import gspread
from google.oauth2.service_account import Credentials
from core.config import settings
import logging
import os
import json

logger = logging.getLogger(__name__)


def init_gsheet_client():
    """Initialize Google Sheets client using service account credentials"""
    try:
        # Try reading from environment variable first (for Render deployment)
        creds_json = os.getenv('GOOGLE_CREDENTIALS_JSON')
        
        if creds_json:
            # Parse JSON from environment variable
            logger.info("Loading credentials from GOOGLE_CREDENTIALS_JSON environment variable")
            try:
                creds_dict = json.loads(creds_json)
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON in GOOGLE_CREDENTIALS_JSON: {str(e)}")
                raise ValueError("GOOGLE_CREDENTIALS_JSON is not valid JSON")
        else:
            # Fall back to file-based credentials (for local development)
            creds_path = settings.CREDENTIALS_FILE
            
            if not os.path.exists(creds_path):
                raise FileNotFoundError(
                    f"Credentials file not found at {creds_path}. "
                    "Set GOOGLE_CREDENTIALS_JSON env variable or place credentials.json in project root"
                )
            
            logger.info(f"Loading credentials from file: {creds_path}")
            with open(creds_path, 'r') as f:
                creds_dict = json.load(f)
        
        # Create credentials object
        scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        
        # Create client
        client = gspread.authorize(creds)
        logger.info("✓ Google Sheets client initialized successfully")
        return client
        
    except FileNotFoundError as e:
        logger.error(f"✗ Credentials file error: {str(e)}")
        raise
    except json.JSONDecodeError as e:
        logger.error(f"✗ JSON parsing error: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"✗ Error initializing Google Sheets client: {str(e)}")
        raise


def get_spreadsheet(client, sheet_name: str = None):
    """Get spreadsheet by name"""
    try:
        sheet = client.open(sheet_name or settings.SHEET_NAME)
        return sheet
    except Exception as e:
        logger.error(f"Error opening spreadsheet: {str(e)}")
        raise


def get_worksheet(client, sheet_name: str, worksheet_name: str):
    """Get worksheet from spreadsheet"""
    try:
        sheet = get_spreadsheet(client, sheet_name)
        worksheet = sheet.worksheet(worksheet_name)
        return worksheet
    except Exception as e:
        logger.error(f"Error getting worksheet {worksheet_name}: {str(e)}")
        raise
