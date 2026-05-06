"""
Loans API routes
"""

from fastapi import APIRouter, HTTPException, status, Query, Depends
import logging
from datetime import date, datetime
import pandas as pd
import gspread

from schemas.models import LoansResponse, LoanItem, LoanRequirementCreateRequest, LoanRequirementCreateResponse
from services.data_loader import load_loan_data, load_loan_requirements_data, load_user_credentials
from services.loan_services import (
    get_user_active_loans,
    add_loan_projection_columns,
    convert_loans_to_items,
    parse_month_label,
    to_float,
)
from services.data_processor import filter_loan_requirements_current_and_future, find_column
from core.security import get_current_user
from core.config import settings
from core.database import get_worksheet

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

    Each row includes:
    - row_number: actual Google Sheet row number (use this for DELETE)
    - can_delete: true only when the row belongs to the authenticated user
    """
    try:
        client = get_client()
        requester_member_name = _normalize_name(token_payload.get("member_name", ""))
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

        # DataFrame index is 0-based; sheet row = index + 2 (row 1 is header)
        member_col = find_column(filtered_df, ["member_name", "Member Name", "Name"])
        rows = []
        for idx, row in filtered_df.fillna("").iterrows():
            row_dict = row.to_dict()
            owner = _normalize_name(row_dict.get(member_col, "")) if member_col else ""
            row_dict["row_number"] = int(idx) + 2
            row_dict["can_delete"] = owner == requester_member_name
            rows.append(row_dict)

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


def _find_header_column(headers, candidates):
    """Find a header name using exact/case-insensitive candidate matching."""
    header_map = {str(h).strip().lower(): str(h) for h in headers}
    for candidate in candidates:
        normalized = str(candidate).strip().lower()
        if normalized in header_map:
            return header_map[normalized]
    return None


def _effective_month_label(today: date, cutoff_day: int) -> str:
    """Return effective month label as Mon YYYY using cutoff rule."""
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

    return datetime(effective_year, effective_month, 1).strftime("%b %Y")


def _normalize_text(value: str) -> str:
    """Normalize text for case-insensitive comparisons."""
    return str(value or "").strip().lower()


def _normalize_name(value: str) -> str:
    """Normalize a member name exactly as POST stores it (strip, lowercase)."""
    return str(value or "").strip().lower()


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
        loan_amount_col = find_column(df_loan, ["Loan Amount", "Loan", "Total Loan Amount", "Disbursed Amount"])
        emi_start_col = find_column(df_loan, ["EMI Start Month", "EMI_Start_Month", "EMI Start Date", "Start Month"])
        loan_taken_date_col = find_column(df_loan, ["Loan Taken Date", "Loan Date", "Disbursed Date", "Date"])

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
                    "loan_amount": to_float(row.get(loan_amount_col, 0)) if loan_amount_col else 0.0,
                    "emi_start_date": str(row.get(emi_start_col, "")).strip() if emi_start_col else "",
                    "loan_taken_date": str(row.get(loan_taken_date_col, "")).strip() if loan_taken_date_col else "",
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


@router.post("/requirements")
async def create_loan_requirement(
    request_data: LoanRequirementCreateRequest,
    token_payload: dict = Depends(get_current_user),
):
    """
    Create a new loan requirement request in loan_requirements sheet.

    Inserts at the first empty row and auto-resolves team lead
    from user_credentails using member_name.
    """
    try:
        client = get_client()
        _ = token_payload

        df_users = load_user_credentials(client)
        if df_users.empty:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User credentials data not found"
            )

        member_col = find_column(df_users, ["Member Name", "member_name", "Name"])
        team_lead_col = find_column(df_users, ["Team Lead", "team_lead", "TeamLead", "TL"])
        if not member_col or not team_lead_col:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Required columns not found in user_credentails (Member Name, Team Lead)"
            )

        member_series = df_users[member_col].astype(str).str.strip().str.lower()
        requested_member = request_data.member_name.strip()
        matches = df_users[member_series == requested_member.lower()]
        if matches.empty:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Member '{requested_member}' not found in user_credentails"
            )

        team_lead = str(matches.iloc[0].get(team_lead_col, "")).strip()

        worksheet = get_worksheet(client, settings.SHEET_NAME, settings.LOAN_REQUIREMENTS_SHEET)
        all_values = worksheet.get_all_values()
        if not all_values:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="loan_requirements sheet has no header row"
            )

        headers = [str(h).strip() for h in all_values[0]]
        month_col = _find_header_column(headers, ["Month"])
        member_name_col = _find_header_column(headers, ["member_name", "Member Name", "Name"])
        team_lead_target_col = _find_header_column(headers, ["team_lead", "Team Lead", "TeamLead", "TL"])
        loan_unit_req_col = _find_header_column(headers, ["loan_unit_req", "Loan Unit Req", "Loan Unit", "Unit Req"])
        loan_amount_req_col = _find_header_column(headers, ["loan_amount_req", "Loan Amount Req", "Loan Amount", "Amount Req"])
        reason_col = _find_header_column(headers, ["Reason", "reason", "Loan Reason"])

        missing_cols = []
        for column_name, column_value in [
            ("Month", month_col),
            ("member_name", member_name_col),
            ("team_lead", team_lead_target_col),
            ("loan_unit_req", loan_unit_req_col),
            ("loan_amount_req", loan_amount_req_col),
        ]:
            if not column_value:
                missing_cols.append(column_name)

        if missing_cols:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Required column(s) not found in loan_requirements: {', '.join(missing_cols)}"
            )

        # Find first empty row (after header); if none empty in current data, append next row.
        target_row_number = None
        for idx, row in enumerate(all_values[1:], start=2):
            if not any(str(cell).strip() for cell in row):
                target_row_number = idx
                break
        if target_row_number is None:
            target_row_number = len(all_values) + 1

        cutoff_day = int(getattr(settings, "EMI_CUTOFF_DAY", 5) or 5)
        month_value = (request_data.month or "").strip() or _effective_month_label(date.today(), cutoff_day)

        row_payload = {
            month_col: month_value,
            member_name_col: requested_member,
            team_lead_target_col: team_lead,
            loan_unit_req_col: request_data.loan_unit_req,
            loan_amount_req_col: request_data.loan_amount_req,
        }
        if reason_col:
            row_payload[reason_col] = request_data.reason or ""

        full_row = [""] * len(headers)
        for col_name, col_value in row_payload.items():
            full_row[headers.index(col_name)] = str(col_value)

        end_cell = gspread.utils.rowcol_to_a1(target_row_number, len(headers))
        worksheet.update(
            f"A{target_row_number}:{end_cell}",
            [full_row],
            value_input_option="USER_ENTERED",
        )

        inserted_data = {
            "Month": month_value,
            "member_name": requested_member,
            "team_lead": team_lead,
            "loan_unit_req": request_data.loan_unit_req,
            "loan_amount_req": request_data.loan_amount_req,
            "Reason": request_data.reason or "",
        }

        return LoanRequirementCreateResponse(
            status="success",
            message=f"Loan requirement added successfully at row {target_row_number}",
            row_number=target_row_number,
            inserted_data=inserted_data,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating loan requirement: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create loan requirement"
        )


@router.delete("/requirements/{row_number}")
async def delete_loan_requirement(
    row_number: int,
    token_payload: dict = Depends(get_current_user),
):
    """
    Delete a loan requirement row by its sheet row number.

    row_number is returned by GET /requirements in each row's 'row_number' field.
    Authorization: only the owner of the row (member_name match) may delete it.
    """
    try:
        # Row 1 is the header; data starts at row 2
        if row_number < 2:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="row_number must be 2 or greater (row 1 is the header)"
            )

        client = get_client()

        # Load via the same path as GET so index arithmetic is identical:
        # DataFrame index 0 = sheet row 2, index N = sheet row N+2
        df_requirements = load_loan_requirements_data(client)
        if df_requirements.empty:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No loan requirements data found"
            )

        # Translate sheet row_number -> DataFrame index
        df_index = row_number - 2
        if df_index not in df_requirements.index:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Requirement at row {row_number} not found"
            )

        target_row = df_requirements.loc[df_index]
        member_col = find_column(df_requirements, ["member_name", "Member Name", "Name"])
        if not member_col:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Required column 'member_name' not found in loan_requirements"
            )

        owner_member_name = str(target_row.get(member_col, ""))
        if not owner_member_name.strip():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Requirement at row {row_number} is empty"
            )

        requester_member_name = token_payload.get("member_name", "")
        if _normalize_name(owner_member_name) != _normalize_name(requester_member_name):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only delete your own requirement"
            )

        # Clear the row in Google Sheets using the worksheet directly
        worksheet = get_worksheet(client, settings.SHEET_NAME, settings.LOAN_REQUIREMENTS_SHEET)
        num_cols = len(df_requirements.columns)
        end_cell = gspread.utils.rowcol_to_a1(row_number, num_cols)
        worksheet.update(
            f"A{row_number}:{end_cell}",
            [[""] * num_cols],
            value_input_option="USER_ENTERED",
        )

        logger.info(
            f"Requirement row {row_number} deleted by {requester_member_name}"
        )
        return {
            "status": "success",
            "message": f"Loan requirement deleted successfully",
            "row_number": row_number,
            "deleted_by": token_payload.get("username") or token_payload.get("member_name"),
            "deleted_owner": owner_member_name,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting loan requirement row {row_number}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete loan requirement"
        )
