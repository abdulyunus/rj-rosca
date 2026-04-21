"""
Metrics calculation service
"""

import pandas as pd
import logging
from datetime import datetime
from schemas.models import MetricsResponse
from services.data_processor import filter_by_month

logger = logging.getLogger(__name__)


def calculate_metrics(df: pd.DataFrame, month: int = None, year: int = None) -> MetricsResponse:
    """Calculate key financial metrics"""
    now = datetime.now()
    selected_month = int(month or now.month)
    selected_year = int(year or now.year)

    metrics = MetricsResponse(
        total_collection=0.0,
        total_emi=0.0,
        total_share=0.0,
        total_loans=0.0,
        loan_processed=0,
        loan_cleared=0,
        balance_available=0.0,
        month=str(selected_month),
        year=selected_year
    )

    if df.empty:
        return metrics

    try:
        filtered_df = filter_by_month(df, selected_year, selected_month)

        # Calculate totals from dataframe
        metrics.total_collection = float(filtered_df.get('Total Amount', pd.Series([0])).sum() or 0)
        metrics.total_emi = float(filtered_df.get('EMI received', pd.Series([0])).sum() or 0)
        metrics.total_share = float(filtered_df.get('Share Amount for the month', pd.Series([0])).sum() or 0)
        metrics.total_loans = float(filtered_df.get('Loan', pd.Series([0])).sum() or 0)

        metrics.loan_processed = int(filtered_df.get('No of Application processed', pd.Series([0])).sum() or 0)
        metrics.loan_cleared = int(filtered_df.get('No of Loan cleared', pd.Series([0])).sum() or 0)

        # Calculate available balance
        metrics.balance_available = metrics.total_collection - metrics.total_loans

        logger.info(f"Metrics calculated: collection={metrics.total_collection}, emi={metrics.total_emi}")

    except Exception as e:
        logger.error(f"Error calculating metrics: {str(e)}")

    return metrics


def calculate_team_metrics(df: pd.DataFrame) -> dict:
    """Calculate team-level metrics"""
    if df.empty:
        return {}
    
    try:
        metrics = {
            'total_members': len(df),
            'total_share': float(df.get('Monthly Share', pd.Series([0])).sum() or 0),
            'total_emi': float(df.get('Monthly EMI', pd.Series([0])).sum() or 0),
            'total_collection': float(df.get('Total', pd.Series([0])).sum() or 0),
        }
        return metrics
    except Exception as e:
        logger.error(f"Error calculating team metrics: {str(e)}")
        return {}


def calculate_user_metrics(df: pd.DataFrame, user_name: str) -> dict:
    """Calculate user-specific metrics"""
    if df.empty or not user_name:
        return {}
    
    try:
        user_data = df[df['Member Name'].astype(str).str.contains(user_name, case=False, na=False)]
        
        if user_data.empty:
            return {}
        
        metrics = {
            'monthly_share': float(user_data.get('Monthly Share', pd.Series([0])).sum() or 0),
            'monthly_emi': float(user_data.get('Monthly EMI', pd.Series([0])).sum() or 0),
            'total_payment': float(user_data.get('Total', pd.Series([0])).sum() or 0),
            'active_loans': int(user_data.get('Active Loans', pd.Series([0])).count() or 0),
        }
        return metrics
    except Exception as e:
        logger.error(f"Error calculating user metrics: {str(e)}")
        return {}
