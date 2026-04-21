"""
Loan services for loan calculations and queries
"""

import pandas as pd
import datetime
import logging
from typing import Optional, List
from core.config import settings
from services.data_processor import find_column, normalize_member_name, to_float
from schemas.models import LoanItem

logger = logging.getLogger(__name__)


def to_float(value) -> float:
    """Convert value to float, handling currency symbols and commas"""
    text = str(value).replace(",", "").replace("₹", "").strip()
    try:
        return float(text)
    except (ValueError, TypeError):
        return 0.0


def parse_month_label(month_value) -> Optional[datetime.date]:
    """Parse month label in format like 'Jan-23' or 'January-2023'"""
    text = str(month_value).strip()
    if not text:
        return None
    
    patterns = ["%b-%y", "%b-%Y", "%B-%y", "%B-%Y"]
    for pattern in patterns:
        try:
            parsed = datetime.datetime.strptime(text, pattern)
            return datetime.date(parsed.year, parsed.month, 1)
        except ValueError:
            continue
    
    return None


def month_span_inclusive(start_month: Optional[datetime.date], end_month: Optional[datetime.date]) -> int:
    """Calculate inclusive month span between two dates"""
    if not start_month or not end_month:
        return 0
    if end_month < start_month:
        return 0
    
    return (end_month.year - start_month.year) * 12 + (end_month.month - start_month.month) + 1


def add_loan_projection_columns(
    df: pd.DataFrame,
    as_of_date: Optional[datetime.date] = None,
) -> pd.DataFrame:
    """Add EMI projection columns to loan dataframe"""
    if df.empty:
        return df
    
    result = df.copy()
    today = datetime.date.today()
    reference_date = as_of_date or today
    current_month = reference_date.replace(day=1)
    post_due_day_adjustment = 1 if reference_date.day >= settings.EMI_CUTOFF_DAY else 0
    
    # Find column names
    emi_start_col = find_column(df, ["EMI Start Month", "EMI_Start_Month", "Start Month", "emiStart"])
    last_emi_col = find_column(df, ["Last EMI Month", "Last_EMI_Month", "End Month", "emiEnd"])
    loan_amount_col = find_column(df, ["Loan Amount", "Loan", "Total Loan Amount", "Disbursed Amount"])
    total_months_col = find_column(df, ["Total Months", "Tenure", "Loan Tenure", "EMI Months"])
    
    def _remaining_emi(row):
        """Calculate remaining EMI"""
        if not emi_start_col or not last_emi_col:
            return 0
        
        start_month = parse_month_label(row.get(emi_start_col, ""))
        end_month = parse_month_label(row.get(last_emi_col, ""))
        
        if not end_month:
            return 0
        
        effective_start = max(start_month, current_month) if start_month else current_month
        remaining = month_span_inclusive(effective_start, end_month)
        
        # Apply cutoff day adjustment
        if post_due_day_adjustment and (not start_month or start_month <= current_month):
            remaining = max(remaining - post_due_day_adjustment, 0)
        
        return remaining
    
    result["EMI Remaining"] = result.apply(_remaining_emi, axis=1)
    
    # Calculate amount to pay
    if loan_amount_col and total_months_col:
        loan_amount_series = result[loan_amount_col].apply(to_float)
        total_months_series = result[total_months_col].apply(to_float)
        
        # Avoid division by zero
        monthly_component = loan_amount_series / total_months_series.replace(0, float("nan"))
        result["Amount to Pay"] = result["EMI Remaining"] * monthly_component.fillna(0)
    else:
        result["Amount to Pay"] = 0.0
    
    result["Amount to Pay"] = result["Amount to Pay"].astype(float).round(2)
    
    return result


def get_user_active_loans(
    df_loan: pd.DataFrame,
    user_name: str,
    as_of_date: Optional[datetime.date] = None,
) -> pd.DataFrame:
    """Get active loans for a specific user"""
    if df_loan.empty or not user_name:
        return pd.DataFrame()
    
    # Find column names
    name_col = find_column(df_loan, ["Name", "Member Name", "Customer Name"])
    status_col = find_column(df_loan, ["Status", "Loan Status"])
    
    if not name_col or not status_col:
        return pd.DataFrame()
    
    # Filter by user name and active status
    filtered = df_loan[
        (df_loan[name_col].astype(str).str.contains(user_name, case=False, na=False)) &
        (df_loan[status_col].astype(str).str.lower().isin(['disbursed', 'active']))
    ].copy()
    
    if filtered.empty:
        return pd.DataFrame()
    
    # Add projection columns
    return add_loan_projection_columns(filtered, as_of_date=as_of_date)


def get_team_member_active_loans(df_loan: pd.DataFrame, team_lead: str, member_name: str) -> pd.DataFrame:
    """Get active loans for a team member"""
    if df_loan.empty:
        return pd.DataFrame()
    
    # First filter by team lead, then by member
    name_col = find_column(df_loan, ["Name", "Member Name", "Customer Name"])
    status_col = find_column(df_loan, ["Status", "Loan Status"])
    
    if not name_col or not status_col:
        return pd.DataFrame()
    
    # Filter for active loans
    active_loans = df_loan[
        df_loan[status_col].astype(str).str.lower().isin(['disbursed', 'active'])
    ].copy()
    
    if active_loans.empty:
        return pd.DataFrame()
    
    # Filter by member name (within the team)
    filtered = active_loans[
        active_loans[name_col].astype(str).str.contains(member_name, case=False, na=False)
    ].copy()
    
    if filtered.empty:
        return pd.DataFrame()
    
    return add_loan_projection_columns(filtered)


def convert_loans_to_items(df: pd.DataFrame) -> List[LoanItem]:
    """Convert loan dataframe to list of LoanItem models"""
    items = []
    
    if df.empty:
        return items
    
    try:
        name_col = find_column(df, ["Name", "Member Name", "Customer Name"])
        month_col = find_column(df, ["Month", "Loan Month", "Month-Year", "Month Year"])
        team_lead_col = find_column(df, ["Team Lead", "TeamLead", "Team_Lead", "TL"])
        status_col = find_column(df, ["Status", "Loan Status"])
        loan_amount_col = find_column(df, ["Loan Amount", "Loan", "Total Loan Amount", "Disbursed Amount"])
        emi_col = find_column(df, ["EMI received", "EMI Received", "EMI"])
        emi_start_col = find_column(df, ["EMI Start Month", "EMI_Start_Month", "Start Month"])
        last_emi_col = find_column(df, ["Last EMI Month", "Last_EMI_Month", "End Month"])
        total_months_col = find_column(df, ["Total Months", "Tenure", "Loan Tenure"])
        
        for idx, row in df.iterrows():
            item = LoanItem(
                id=f"loan_{idx}",
                month=str(row.get(month_col, "")).strip() if month_col else None,
                name=str(row.get(name_col, "")) if name_col else "",
                team_lead=str(row.get(team_lead_col, "")).strip() if team_lead_col else None,
                status=str(row.get(status_col, "")) if status_col else "unknown",
                loan_amount=to_float(row.get(loan_amount_col, 0)) if loan_amount_col else 0.0,
                emi_received=to_float(row.get(emi_col, 0)) if emi_col else 0.0,
                emi_remaining=int(row.get("EMI Remaining", 0) or 0),
                amount_to_pay=float(row.get("Amount to Pay", 0) or 0),
                emi_start_month=str(row.get(emi_start_col, "")) if emi_start_col else None,
                last_emi_month=str(row.get(last_emi_col, "")) if last_emi_col else None,
                total_months=int(row.get(total_months_col, 0) or 0) if total_months_col else None,
            )
            items.append(item)
    
    except Exception as e:
        logger.error(f"Error converting loans to items: {str(e)}")
    
    return items
