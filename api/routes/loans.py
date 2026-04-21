"""
Loans API routes
"""

from fastapi import APIRouter, HTTPException, status, Query, Depends
import logging
from datetime import date, datetime

from schemas.models import LoansResponse, LoanItem
from services.data_loader import load_loan_data
from services.loan_services import (
    get_user_active_loans,
    add_loan_projection_columns,
    convert_loans_to_items
)
from core.security import get_current_user
from core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()

# Global client reference
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


@router.get("/active")
async def get_active_loans(
    token_payload: dict = Depends(get_current_user),
    month: int = Query(None, ge=1, le=12),
    year: int = Query(None, ge=2000, le=2100),
):
    """
    Get active loans for the current user.
    Requires Bearer token via the Authorize button.
    """
    try:
        
        client = get_client()
        member_name = token_payload.get("member_name")
        selected_year = int(year or datetime.now().year)
        selected_month = int(month or datetime.now().month)
        as_of_date = date(selected_year, selected_month, settings.EMI_CUTOFF_DAY)
        
        # Load loan data
        df_loan = load_loan_data(client)
        
        if df_loan.empty:
            return LoansResponse(total_count=0, loans=[])
        
        # Get user's active loans
        user_loans = get_user_active_loans(df_loan, member_name, as_of_date=as_of_date)
        
        if user_loans.empty:
            return LoansResponse(total_count=0, loans=[])
        
        # Convert to items
        items = convert_loans_to_items(user_loans)
        active_loans_payload = [
            {
                key: value
                for key, value in item.model_dump().items()
                if key != "emi_received"
            }
            for item in items
        ]
        
        logger.info(f"Retrieved {len(items)} active loans for {member_name}")
        
        return {
            "total_count": len(active_loans_payload),
            "loans": active_loans_payload,
            "status": "disbursed",
            "month": str(selected_month),
            "year": selected_year,
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving active loans: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve active loans"
        )


@router.get("/all")
async def get_all_loans(
    status_filter: str = Query("all", description="Filter by status: all, disbursed, closed"),
    limit: int = Query(100),
    offset: int = Query(0),
):
    """
    Get all loans (admin endpoint)
    
    Query Parameters:
    - status_filter: all, disbursed, closed
    - limit: Maximum number of results
    - offset: Number of results to skip
    """
    try:
        client = get_client()
        
        # Load loan data
        df_loan = load_loan_data(client)
        
        if df_loan.empty:
            return LoansResponse(total_count=0, loans=[])
        
        # Filter by status if needed
        if status_filter != "all":
            from services.data_processor import find_column
            status_col = find_column(df_loan, ["Status", "Loan Status"])
            if status_col:
                df_loan = df_loan[
                    df_loan[status_col].astype(str).str.lower() == status_filter.lower()
                ].copy()
        
        # Add projections
        df_loan = add_loan_projection_columns(df_loan)
        
        # Apply pagination
        total_count = len(df_loan)
        df_loan = df_loan.iloc[offset:offset + limit]
        
        # Convert to items
        items = convert_loans_to_items(df_loan)
        
        logger.info(f"Retrieved {len(items)} loans with status filter: {status_filter}")
        
        return LoansResponse(
            total_count=total_count,
            loans=items,
            status=status_filter,
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving all loans: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve loans"
        )


@router.get("/{loan_id}")
async def get_loan_details(loan_id: str):
    """
    Get details for a specific loan
    """
    try:
        client = get_client()
        
        # Load loan data
        df_loan = load_loan_data(client)
        
        if df_loan.empty:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Loan not found"
            )
        
        # Find loan by ID
        idx = int(loan_id.split("_")[1])
        if idx >= len(df_loan):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Loan not found"
            )
        
        # Get loan row
        df_loan = add_loan_projection_columns(df_loan)
        loan_row = df_loan.iloc[idx:idx+1]
        
        items = convert_loans_to_items(loan_row)
        
        if not items:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Loan not found"
            )
        
        return items[0]
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving loan details: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve loan details"
        )
