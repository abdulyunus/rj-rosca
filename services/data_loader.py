"""
Data loading service for Google Sheets
"""

import pandas as pd
import logging
from typing import Optional
from core.database import get_worksheet
from core.config import settings

logger = logging.getLogger(__name__)


def load_sheet_data(client, sheet_name: str, worksheet_name: str, cell_range: str) -> pd.DataFrame:
    """Load data from Google Sheet"""
    try:
        worksheet = get_worksheet(client, sheet_name, worksheet_name)
        raw_data = worksheet.get(cell_range)
        
        if not raw_data or len(raw_data) < 2:
            logger.warning(f"No data found in {worksheet_name}")
            return pd.DataFrame()
        
        # Parse header and data
        header = raw_data[0]
        num_cols = len(header)
        
        # Pad rows to match header length
        padded_rows = [row + [""] * (num_cols - len(row)) for row in raw_data[1:]]
        
        df = pd.DataFrame(padded_rows, columns=header)
        df.columns = [col.strip() for col in df.columns]
        
        logger.info(f"Loaded {len(df)} rows from {worksheet_name}")
        return df
        
    except Exception as e:
        logger.error(f"Error loading data from {worksheet_name}: {str(e)}")
        raise


def load_main_data(client, sheet_name: str = None) -> pd.DataFrame:
    """Load main calculations data"""
    return load_sheet_data(
        client,
        sheet_name or settings.SHEET_NAME,
        settings.MAIN_SHEET,
        settings.MAIN_RANGE
    )


def load_loan_data(client, sheet_name: str = None) -> pd.DataFrame:
    """Load loan data"""
    return load_sheet_data(
        client,
        sheet_name or settings.SHEET_NAME,
        settings.LOAN_SHEET,
        settings.LOAN_RANGE
    )


def load_loan_requirements_data(client, sheet_name: str = None) -> pd.DataFrame:
    """Load loan requirements data"""
    return load_sheet_data(
        client,
        sheet_name or settings.SHEET_NAME,
        settings.LOAN_REQUIREMENTS_SHEET,
        settings.LOAN_REQUIREMENTS_RANGE
    )


def load_collections_data(client, sheet_name: str = None) -> pd.DataFrame:
    """Load collections data"""
    return load_sheet_data(
        client,
        sheet_name or settings.SHEET_NAME,
        settings.COLLECTIONS_SHEET,
        settings.COLLECTIONS_RANGE
    )


def load_miscellaneous_data(client, sheet_name: str = None) -> pd.DataFrame:
    """Load miscellaneous data"""
    return load_sheet_data(
        client,
        sheet_name or settings.SHEET_NAME,
        settings.MISCELLANEOUS_SHEET,
        settings.MISCELLANEOUS_RANGE
    )


def load_user_credentials(client, sheet_name: str = None) -> pd.DataFrame:
    """Load user credentials"""
    return load_sheet_data(
        client,
        sheet_name or settings.SHEET_NAME,
        settings.USER_CREDENTIALS_SHEET,
        "A1:Z1000"  # Large range for credentials
    )
