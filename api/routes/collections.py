"""
Collections API routes
"""

from fastapi import APIRouter, HTTPException, status, Depends, Query
import logging
import pandas as pd
from datetime import datetime
from urllib.parse import quote

from schemas.models import CollectionsResponse, TeamCollection, CollectionMember
from services.data_loader import load_loan_data, load_user_credentials, load_main_data
from services.auth_service import get_all_team_leads, get_team_members_from_credentials
from services.loan_services import get_team_member_active_loans
from services.metrics import calculate_metrics
from core.security import get_current_user
from services.data_processor import find_column, filter_by_month, normalize_member_name, to_float

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


def get_next_month_emi(df_user_loans: pd.DataFrame) -> float:
    """Calculate monthly EMI from user loans"""
    if df_user_loans.empty:
        return 0.0
    
    from services.data_processor import to_float
    
    monthly_emi = 0.0
    for _, row in df_user_loans.iterrows():
        amount_to_pay = to_float(row.get("Amount to Pay", 0))
        emi_remaining = int(row.get("EMI Remaining", 0) or 0)
        if emi_remaining > 0:
            monthly_emi += amount_to_pay / emi_remaining
    
    return monthly_emi


def get_amount_collected_for_period(df_main: pd.DataFrame, month: int, year: int) -> float:
    """Get amount collected for selected month/year from Main_Calculations."""
    if df_main.empty:
        return 0.0

    filtered = filter_by_month(df_main, year=year, month=month)
    if filtered.empty:
        return 0.0

    amount_col = find_column(
        filtered,
        [
            "Amount Collected",
            "Amount collected",
            "Collected Amount",
            "Collection Amount",
        ],
    )
    if not amount_col:
        return 0.0

    return float(filtered[amount_col].apply(to_float).sum() or 0.0)


def build_member_units_map(df_users: pd.DataFrame) -> dict:
    """Build normalized member -> units mapping from credentials sheet."""
    if df_users.empty:
        return {}

    member_col = find_column(df_users, ["member_name", "member name", "name", "full_name", "full name"])
    units_col = find_column(df_users, ["units", "unit", "no of units", "number of units", "share units"])

    if not member_col or not units_col:
        return {}

    units_map = {}
    for _, row in df_users.iterrows():
        member_name = str(row.get(member_col, "")).strip()
        if not member_name:
            continue
        units_map[normalize_member_name(member_name)] = to_float(row.get(units_col, 0))

    return units_map


def ensure_admin_access(token_payload: dict, df_users: pd.DataFrame) -> None:
    """Allow access only for users with admin role from credentials sheet."""
    username = str(token_payload.get("username") or token_payload.get("sub") or "").strip()
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload"
        )

    if df_users.empty:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Admin role required"
        )

    login_col = find_column(df_users, ["login_id", "login id", "username", "user_id", "userid", "id"])
    role_col = find_column(df_users, ["role", "user_role", "user role"])

    if not login_col or not role_col:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Role configuration missing in user credentials"
        )

    user_rows = df_users[
        df_users[login_col].astype(str).str.strip().str.lower() == username.lower()
    ]
    if user_rows.empty:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. User not found in credentials"
        )

    role_value = str(user_rows.iloc[0].get(role_col, "")).strip().lower()
    if role_value != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Admin role required"
        )


def _parse_period_value(value) -> pd.Period | None:
    """Parse month-like values into a monthly period."""
    text = str(value or "").strip()
    if not text:
        return None

    for fmt in ("%b-%y", "%b-%Y", "%B-%y", "%B-%Y"):
        try:
            parsed = datetime.strptime(text, fmt)
            return pd.Period(year=parsed.year, month=parsed.month, freq="M")
        except ValueError:
            continue

    parsed_dt = pd.to_datetime(text, errors="coerce", dayfirst=False)
    if pd.notna(parsed_dt):
        return pd.Period(year=int(parsed_dt.year), month=int(parsed_dt.month), freq="M")

    return None


def _format_money(value: float) -> str:
    """Format amount as rupee text for WhatsApp."""
    return f"₹{float(value or 0):,.0f}/-"


def _build_member_units_map(df_users: pd.DataFrame) -> dict[str, int]:
    """Build normalized member name -> units map."""
    if df_users.empty:
        return {}

    member_col = find_column(df_users, ["member_name", "member name", "name", "full_name", "full name"])
    units_col = find_column(df_users, ["units", "unit", "no of units", "number of units", "share units"])
    if not member_col or not units_col:
        return {}

    units_map = {}
    for _, row in df_users.iterrows():
        member_name = str(row.get(member_col, "")).strip().lower()
        if not member_name:
            continue
        units_map[member_name] = int(to_float(row.get(units_col, 0)) or 0)

    return units_map


@router.get("/team/{team_lead}")
async def get_team_collection(
    team_lead: str,
    token_payload: dict = Depends(get_current_user),
    month: int = Query(default=datetime.now().month, ge=1, le=12),
    year: int = Query(default=datetime.now().year, ge=2000, le=2100),
):
    """
    Get collection summary for a specific team.
    Requires Bearer token via the Authorize button.
    """
    try:
        
        client = get_client()
        
        # Load data
        df_users = load_user_credentials(client)
        df_loan = load_loan_data(client)
        df_main = load_main_data(client)
        
        if df_users.empty:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Team not found"
            )

        ensure_admin_access(token_payload, df_users)
        
        # Get team members
        team_members = get_team_members_from_credentials(df_users, team_lead)
        lead_name = str(team_lead).strip()
        if lead_name and all(normalize_member_name(m) != normalize_member_name(lead_name) for m in team_members):
            team_members = [lead_name] + team_members

        amount_collected = get_amount_collected_for_period(df_main, month=month, year=year)
        units_map = build_member_units_map(df_users)
        
        # Build collection data
        team_collection = TeamCollection(
            team_lead=team_lead,
            team_members=[],
            total_share=0.0,
            total_emi=0.0,
            total_collection=0.0,
        )
        
        # Add team members
        for member in team_members:
            user_loans = get_team_member_active_loans(df_loan, team_lead, member)
            monthly_emi = get_next_month_emi(user_loans)
            member_units = units_map.get(normalize_member_name(member), 0.0)
            monthly_share = float(amount_collected * member_units)
            
            team_collection.team_members.append(
                CollectionMember(
                    team_member=member,
                    monthly_share=monthly_share,
                    monthly_emi=monthly_emi,
                    upcoming_payment=monthly_share + monthly_emi,
                )
            )
            
            team_collection.total_share += monthly_share
            team_collection.total_emi += monthly_emi
            team_collection.total_collection += monthly_share + monthly_emi
        
        logger.info(f"Retrieved collection for team: {team_lead}")
        
        return CollectionsResponse(
            teams=[team_collection],
            total_collection=team_collection.total_collection,
            month=str(month),
            year=year,
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving team collection: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve team collection"
        )


@router.get("/all-teams")
async def get_all_teams_collection(
    token_payload: dict = Depends(get_current_user),
    month: int = Query(default=datetime.now().month, ge=1, le=12),
    year: int = Query(default=datetime.now().year, ge=2000, le=2100),
):
    """
    Get collection summary for all teams.
    Requires Bearer token via the Authorize button.
    """
    try:
        
        client = get_client()
        
        # Load data
        df_users = load_user_credentials(client)
        df_loan = load_loan_data(client)
        df_main = load_main_data(client)
        
        if df_users.empty:
            return CollectionsResponse(teams=[], total_collection=0.0)
        
        # Get all team leads
        team_leads = get_all_team_leads(df_users, df_loan)
        amount_collected = get_amount_collected_for_period(df_main, month=month, year=year)
        units_map = build_member_units_map(df_users)
        
        # Build collections
        collections = CollectionsResponse(teams=[], total_collection=0.0)
        
        for team_lead in team_leads:
            team_members = get_team_members_from_credentials(df_users, team_lead)
            lead_name = str(team_lead).strip()
            if lead_name and all(normalize_member_name(m) != normalize_member_name(lead_name) for m in team_members):
                team_members = [lead_name] + team_members
            
            team_collection = TeamCollection(
                team_lead=team_lead,
                team_members=[],
                total_share=0.0,
                total_emi=0.0,
                total_collection=0.0,
            )
            
            # Add team members
            for member in team_members:
                user_loans = get_team_member_active_loans(df_loan, team_lead, member)
                monthly_emi = get_next_month_emi(user_loans)
                member_units = units_map.get(normalize_member_name(member), 0.0)
                monthly_share = float(amount_collected * member_units)
                
                team_collection.team_members.append(
                    CollectionMember(
                        team_member=member,
                        monthly_share=monthly_share,
                        monthly_emi=monthly_emi,
                        upcoming_payment=monthly_share + monthly_emi,
                    )
                )
                team_collection.total_share += monthly_share
                team_collection.total_emi += monthly_emi
                team_collection.total_collection += monthly_share + monthly_emi
            
            collections.teams.append(team_collection)
            collections.total_collection += team_collection.total_collection
        
        logger.info(f"Retrieved collections for {len(team_leads)} teams")
        
        collections.month = str(month)
        collections.year = year
        return collections
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving all teams collections: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve collections"
        )


@router.get("/whatsapp-message")
async def get_collections_whatsapp_message(
    token_payload: dict = Depends(get_current_user),
    month: int = Query(default=datetime.now().month, ge=1, le=12),
    year: int = Query(default=datetime.now().year, ge=2000, le=2100),
):
    """
    Build an admin-only WhatsApp message for collection summary.

    This endpoint only generates message text. Frontend can share it using WhatsApp.
    """
    try:
        client = get_client()

        # Admin-only access
        df_users = load_user_credentials(client)
        ensure_admin_access(token_payload, df_users)

        # Dashboard-level metrics for the selected period
        df_main = load_main_data(client)
        metrics = calculate_metrics(df_main, month=month, year=year)

        # Loan processed/cleared names for selected period
        df_loan = load_loan_data(client)

        name_col = find_column(df_loan, ["Name", "Member Name", "Customer Name"]) if not df_loan.empty else None
        month_col = find_column(df_loan, ["Month", "Loan Month", "Month-Year", "Month Year"]) if not df_loan.empty else None
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
        ) if not df_loan.empty else None

        selected_period = pd.Period(year=int(year), month=int(month), freq="M")
        processed_names = []
        cleared_names = []

        if not df_loan.empty and name_col and month_col:
            month_periods = df_loan[month_col].apply(_parse_period_value)
            processed_df = df_loan[month_periods.apply(lambda p: p == selected_period)].copy()
            processed_names = [
                str(name).strip()
                for name in processed_df[name_col].tolist()
                if str(name).strip()
            ]

        if not df_loan.empty and name_col and close_month_col:
            close_periods = df_loan[close_month_col].apply(_parse_period_value)
            cleared_df = df_loan[close_periods.apply(lambda p: p == selected_period)].copy()
            cleared_names = [
                str(name).strip()
                for name in cleared_df[name_col].tolist()
                if str(name).strip()
            ]

        # Deduplicate while preserving order
        processed_names = list(dict.fromkeys(processed_names))
        cleared_names = list(dict.fromkeys(cleared_names))

        period_label = datetime(year, month, 1).strftime("%B %Y")
        lines = [
            "📊 RJ-ROSCA Financial Summary",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            "",
            f"📅 Period: {period_label}",
            "",
            "💰 COLLECTION METRICS",
            f"   💵 Total Collection: {_format_money(metrics.total_collection)}",
            f"   📊 Total EMI: {_format_money(metrics.total_emi)}",
            f"   🤝 Monthly Share: {_format_money(metrics.total_share)}",
            f"   💳 Balance Available: {_format_money(metrics.balance_available)}",
            "",
            "📋 LOAN STATUS BREAKDOWN",
            f"   Total Loans: {int(metrics.total_loans or 0)}",
            f"   ✅ Processed: {int(metrics.loan_processed or 0)}",
            f"   ✔️ Cleared: {int(metrics.loan_cleared or 0)}",
            "",
            "   Loan Processed:",
        ]

        if processed_names:
            for index, member_name in enumerate(processed_names, start=1):
                lines.append(f"   {index}. {member_name}")
        else:
            lines.append("   1. None")

        lines.extend(["", "   Loan Cleared:"])
        if cleared_names:
            for index, member_name in enumerate(cleared_names, start=1):
                lines.append(f"   {index}. {member_name}")
        else:
            lines.append("   1. None")

        message = "\n".join(lines)
        encoded_message = quote(message)

        return {
            "status": "success",
            "month": str(month),
            "year": year,
            "message": message,
            "whatsapp_url": f"https://wa.me/?text={encoded_message}",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating WhatsApp message: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate WhatsApp message"
        )
