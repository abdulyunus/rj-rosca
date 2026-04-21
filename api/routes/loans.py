"""
Loans API routes
"""

from fastapi import APIRouter, HTTPException, status, Query, Depends
import logging
from datetime import date, datetime
import pandas as pd

from schemas.models import LoansResponse, LoanItem
from services.data_loader import load_loan_data, load_loan_requirements_data
from services.loan_services import (
    get_user_active_loans,
    add_loan_projection_columns,
    convert_loans_to_items,
    parse_month_label,
)
from services.data_processor import filter_loan_requirements_current_and_future, find_column
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


@router.get("/requirements")
async def get_loan_requirements(token_payload: dict = Depends(get_current_user)):
    """
    Get loan requirements table as-is, filtered to current/future months.
    Cutoff rule: before 5th -> previous month, on/after 5th -> current month.
    """
    try:
        client = get_client()
        _ = token_payload
        logger.info("Fetching loan requirements")

        df_requirements = load_loan_requirements_data(client)
        if df_requirements.empty:
            return {
                "total_count": 0,
                "requirements": [],
                "month": None,
                "year": None,
            }

        cutoff_day = int(getattr(settings, "EMI_CUTOFF_DAY", 5) or 5)
        today = date.today()
        if today.day < cutoff_day:
            if today.month == 1:
                cutoff_year = today.year - 1
                cutoff_month = 12
            else:
                cutoff_year = today.year
                cutoff_month = today.month - 1
        else:
            cutoff_year = today.year
            cutoff_month = today.month

        filtered_df = filter_loan_requirements_current_and_future(
            df_requirements,
            cutoff_date=today,
            cutoff_day=cutoff_day,
        )
        rows = filtered_df.fillna("").to_dict(orient="records")

        return {
            "total_count": len(rows),
            "requirements": rows,
            "month": str(cutoff_month),
            "year": cutoff_year,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving loan requirements: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve loan requirements"
        )

def _parse_period(value):
    """Parse a value into pandas monthly period when possible."""
    parsed = parse_month_label(value)
    if parsed:
        return pd.Period(year=parsed.year, month=parsed.month, freq="M")

    dt = pd.to_datetime(str(value).strip(), errors="coerce", dayfirst=False)
    if pd.notna(dt):
        return pd.Period(year=int(dt.year), month=int(dt.month), freq="M")

    return None


@router.get("/monthly-loan-summary")
async def get_monthly_loan_summary(token_payload: dict = Depends(get_current_user)):
    """
    Get monthly loan summary from loan_waterfall_c2.

    Returns filtered lists from loan_waterfall_c2:
    - processed_current_month_loans
    - closed_current_month_loans
    - upcoming_closed_loans
    """
    try:
        client = get_client()
        _ = token_payload

        df_loan = load_loan_data(client)
        if df_loan.empty:
            return {
                "month": None,
                "year": None,
                "processed_current_month_loans": [],
                "closed_current_month_loans": [],
                "upcoming_closed_loans": [],
            }

        today = date.today()
        cutoff_day = int(getattr(settings, "EMI_CUTOFF_DAY", 5) or 5)
        if today.day < cutoff_day:
            if today.month == 1:
                effective_year = today.year - 1
                effective_month = 12
            else:
                effective_year = today.year
                effective_month = today.month - 1
        else:
            effective_year = today.year
            effective_month = today.month

        effective_period = pd.Period(year=effective_year, month=effective_month, freq="M")

        month_col = find_column(df_loan, ["Month", "Loan Month", "Month-Year", "Month Year"])
        status_col = find_column(df_loan, ["Status", "Loan Status"])
        close_month_col = find_column(
            df_loan,
            [
                "Last Month EMI",
                "Last EMI Month",
                "Last_EMI_Month",
                "Closed Month",
                "Closure Month",
                "Close Month",
                "End Month",
            ],
        )
        name_col = find_column(df_loan, ["Name", "Member Name", "Customer Name"])
        team_lead_col = find_column(df_loan, ["Team Lead", "TeamLead", "Team_Lead", "TL"])

        month_periods = df_loan[month_col].apply(_parse_period) if month_col else pd.Series([None] * len(df_loan), index=df_loan.index)
        close_periods = df_loan[close_month_col].apply(_parse_period) if close_month_col else pd.Series([None] * len(df_loan), index=df_loan.index)
        status_series = (
            df_loan[status_col].astype(str).str.strip().str.lower()
            if status_col else pd.Series([""] * len(df_loan), index=df_loan.index)
        )

        processed_mask = month_periods.apply(lambda p: p == effective_period)
        processed_current_month_df = df_loan[processed_mask].copy()

        if close_month_col:
            closed_current_mask = close_periods.apply(lambda p: p == effective_period)
        else:
            closed_current_mask = processed_mask & status_series.eq("closed")
        closed_current_month_df = df_loan[closed_current_mask].copy()

        next_period = effective_period + 1
        if close_month_col:
            # Upcoming means loans whose closing month is next month.
            upcoming_closed_mask = close_periods.apply(lambda p: p == next_period)
        else:
            upcoming_closed_mask = pd.Series([False] * len(df_loan), index=df_loan.index)

        upcoming_closed_df = df_loan[upcoming_closed_mask].copy()

        upcoming_closed_loans = []
        for idx, row in upcoming_closed_df.iterrows():
            close_period = _parse_period(row.get(close_month_col, "")) if close_month_col else None
            upcoming_closed_loans.append(
                {
                    "id": f"loan_{idx}",
                    "name": str(row.get(name_col, "")).strip() if name_col else "",
                    "team_lead": str(row.get(team_lead_col, "")).strip() if team_lead_col else "",
                    "status": str(row.get(status_col, "")).strip() if status_col else "",
                    "close_month": str(close_period) if close_period else str(row.get(close_month_col, "")).strip(),
                }
            )

        processed_current_month_loans = processed_current_month_df.fillna("").to_dict(orient="records")
        closed_current_month_loans = closed_current_month_df.fillna("").to_dict(orient="records")

        return {
            "month": str(effective_month),
            "year": effective_year,
            "processed_current_month_loans": processed_current_month_loans,
            "closed_current_month_loans": closed_current_month_loans,
            "upcoming_closed_loans": upcoming_closed_loans,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving monthly loan summary: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve monthly loan summary"
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
