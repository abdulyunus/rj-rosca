"""
Dashboard API routes
"""

from fastapi import APIRouter, HTTPException, status, Query
import logging
from datetime import datetime

from schemas.models import MetricsResponse, DashboardResponse
from services.data_loader import load_main_data
from services.data_processor import clean_dataframe
from services.metrics import calculate_metrics

logger = logging.getLogger(__name__)

router = APIRouter()

# Global client reference (set by main app)
_client = None


def set_client(client):
    """Set the Google Sheets client"""
    global _client
    _client = client


def get_client():
    """Get the Google Sheets client"""
    if _client is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database client not initialized"
        )
    return _client


@router.get(
    "/metrics",
    response_model=MetricsResponse
)
async def get_metrics(
    year: int = Query(default=datetime.now().year, ge=2000, le=2100),
    month: int = Query(default=datetime.now().month, ge=1, le=12)
):
    """
    Get financial metrics for specified month and year
    
    Returns:
    - total_collection: Total amount collected
    - total_emi: Total EMI received
    - total_share: Total share amount
    - total_loans: Total loans disbursed
    - loan_processed: Number of loans processed
    - loan_cleared: Number of loans cleared
    - balance_available: Available balance
    """
    try:
        client = get_client()
        
        # Load and process data
        df = load_main_data(client)
        df = clean_dataframe(df)
        
        # Calculate metrics
        metrics = calculate_metrics(df, month, year)
        
        logger.info(f"Metrics retrieved for {year}-{month:02d}")
        return metrics
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving metrics: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve metrics"
        )


@router.get("/summary")
async def get_dashboard_summary(
    year: int = Query(default=datetime.now().year, ge=2000, le=2100),
    month: int = Query(default=datetime.now().month, ge=1, le=12)
):
    """
    Get complete dashboard summary
    """
    try:
        client = get_client()
        
        # Load main data
        df = load_main_data(client)
        df = clean_dataframe(df)
        
        # Calculate metrics
        metrics = calculate_metrics(df, month, year)
        
        return {
            "metrics": metrics,
            "timestamp": datetime.utcnow().isoformat(),
            "month": month,
            "year": year,
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving dashboard summary: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve dashboard summary"
        )
