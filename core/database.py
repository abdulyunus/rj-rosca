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


def update_worksheet_row(client, sheet_name: str, worksheet_name: str, row_number: int, fields_to_update: dict, header_row: list = None):
    """
    Update a row in a worksheet.
    
    Args:
        client: gspread client
        sheet_name: Name of the spreadsheet
        worksheet_name: Name of the worksheet
        row_number: Row number to update (1-based index, row 1 is header)
        fields_to_update: Dictionary of {column_name: value} to update
        header_row: Optional list of header column names. If not provided, will fetch from row 1
    
    Returns:
        Dictionary with update status and updated cell count
    
    Raises:
        ValueError: If field name not found in header
        HTTPException: If row number is invalid or update fails
    """
    try:
        worksheet = get_worksheet(client, sheet_name, worksheet_name)
        
        # Validate row number (must be > 1 since row 1 is header)
        if row_number <= 1:
            raise ValueError(f"Invalid row number {row_number}. Row 1 is header, use row >= 2")
        
        # Get header if not provided
        if header_row is None:
            header_row = worksheet.row_values(1)
        
        header_row = [col.strip() for col in header_row]
        
        # Get current row data for validation
        try:
            current_row = worksheet.row_values(row_number)
        except Exception:
            raise ValueError(f"Row {row_number} does not exist in worksheet {worksheet_name}")
        
        # Validate that all field names exist in header
        invalid_fields = [field for field in fields_to_update.keys() if field not in header_row]
        if invalid_fields:
            raise ValueError(f"Column(s) not found in header: {', '.join(invalid_fields)}. Available columns: {', '.join(header_row)}")
        
        # Build list of cell updates
        updates = []
        updated_count = 0
        
        for field_name, new_value in fields_to_update.items():
            col_index = header_row.index(field_name) + 1  # gspread uses 1-based column index
            cell_ref = gspread.utils.rowcol_to_a1(row_number, col_index)
            updates.append({
                'range': cell_ref,
                'values': [[str(new_value)]]
            })
            updated_count += 1
        
        # Perform batch update
        if updates:
            worksheet.batch_update(updates, value_input_option='USER_ENTERED')
            logger.info(f"Updated {updated_count} field(s) in row {row_number} of worksheet {worksheet_name}")
        
        return {
            "status": "success",
            "row_number": row_number,
            "updated_fields": updated_count,
            "fields": list(fields_to_update.keys())
        }
    
    except ValueError as e:
        logger.warning(f"Validation error during update: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Error updating row {row_number} in {worksheet_name}: {str(e)}")
        raise
