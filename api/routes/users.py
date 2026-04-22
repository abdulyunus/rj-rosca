"""
Users API routes
"""

from fastapi import APIRouter, HTTPException, status, Depends
import logging
from datetime import date
from datetime import datetime
import pandas as pd

from schemas.models import UserInfo
from services.data_loader import load_user_credentials, load_main_data, load_miscellaneous_data
from core.security import get_current_user
from services.data_processor import find_column, to_float
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


@router.get("/profile", response_model=UserInfo)
async def get_user_profile(token_payload: dict = Depends(get_current_user)):
    """
    Get current user profile.
    Requires Bearer token via the Authorize button.
    """
    try:
        client = get_client()
        df_users = load_user_credentials(client)
        df_main = load_main_data(client)
        df_misc = load_miscellaneous_data(client)

        username = str(token_payload.get("username") or token_payload.get("sub") or "").strip()
        role = token_payload.get("role")
        user_units = 0.0
        member_count = 0

        if not df_users.empty and username:
            login_col = find_column(df_users, ["login_id", "login id", "username", "user_id", "userid", "id"])
            role_col = find_column(df_users, ["role", "user_role", "user role"])
            units_col = find_column(df_users, ["units", "unit", "no of units", "number of units"])
            member_name_col = find_column(df_users, ["member_name", "member name", "name"])

            if member_name_col:
                member_count = int(df_users[member_name_col].astype(str).str.strip().ne("").sum())

            if login_col:
                user_rows = df_users[
                    df_users[login_col].astype(str).str.strip().str.lower() == username.lower()
                ]
                if not user_rows.empty:
                    if role_col:
                        role = str(user_rows.iloc[0].get(role_col, "")).strip() or role
                    if units_col:
                        user_units = to_float(user_rows.iloc[0].get(units_col, 0))

        today = date.today()
        cutoff_day = int(getattr(settings, "EMI_CUTOFF_DAY", 5) or 5)
        # Recompute for the current month from cutoff day onward; before that, use previous month.
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

        def _build_month_year_series(df: pd.DataFrame) -> pd.Series:
            month_col = find_column(df, ["month"])
            year_col = find_column(df, ["year"])

            if month_col and year_col:
                parsed_from_month = pd.to_datetime(df[month_col], errors="coerce")
                month_series = pd.to_numeric(df[month_col], errors="coerce")
                missing_month = month_series.isna()
                if missing_month.any():
                    month_series.loc[missing_month] = parsed_from_month.loc[missing_month].dt.month

                year_series = pd.to_numeric(df[year_col], errors="coerce")
                missing_year = year_series.isna()
                if missing_year.any():
                    year_series.loc[missing_year] = parsed_from_month.loc[missing_year].dt.year

                # Normalize 2-digit years to 2000+ (for example, 23 -> 2023).
                two_digit_years = year_series.notna() & (year_series < 100)
                if two_digit_years.any():
                    year_series.loc[two_digit_years] = 2000 + year_series.loc[two_digit_years]

                valid = month_series.notna() & year_series.notna()
                result = pd.Series(pd.NaT, index=df.index, dtype="datetime64[ns]")
                if valid.any():
                    result.loc[valid] = pd.to_datetime(
                        {
                            "year": year_series.loc[valid].astype(int),
                            "month": month_series.loc[valid].astype(int),
                            "day": 1,
                        },
                        errors="coerce",
                    )
                return result

            date_col = find_column(df, ["date", "month year", "payment date", "created at", "timestamp"])
            if date_col:
                return pd.to_datetime(df[date_col], errors="coerce")

            if month_col:
                parsed = pd.to_datetime(df[month_col], errors="coerce")
                return parsed

            return pd.Series(pd.NaT, index=df.index, dtype="datetime64[ns]")

        def _parse_sheet_month_period(value):
            """Parse values like Jan-25, Apr-26, May-27 into monthly periods."""
            text = str(value).strip()
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

        total_payment_till_date = 0.0
        total_number_of_months = 0
        if not df_main.empty:
            amount_col = find_column(df_main, ["Amount Collected", "amount collected", "collection amount"])
            if amount_col:
                row_dates = _build_month_year_series(df_main)
                cutoff_period = pd.Period(year=cutoff_year, month=cutoff_month, freq="M")

                month_col_main = find_column(df_main, ["Month", "month"])
                payment_valid_rows = pd.Series([False] * len(df_main), index=df_main.index)
                if month_col_main:
                    month_periods_for_payment = df_main[month_col_main].apply(_parse_sheet_month_period)
                    payment_valid_rows = month_periods_for_payment.notna() & (month_periods_for_payment <= cutoff_period)
                else:
                    payment_valid_rows = row_dates.notna() & (row_dates.dt.to_period("M") <= cutoff_period)

                amount_sum = df_main.loc[payment_valid_rows, amount_col].apply(to_float).sum()
                total_payment_till_date = float(amount_sum) * float(user_units)

                start_dt = None
                month_col = find_column(df_main, ["month"])
                if month_col:
                    first_month_idx = df_main[
                        df_main[month_col].astype(str).str.strip().ne("")
                    ].index.min()
                    if pd.notna(first_month_idx):
                        first_row_dt = _build_month_year_series(df_main.loc[[first_month_idx]]).iloc[0]
                        if pd.notna(first_row_dt):
                            start_dt = pd.Timestamp(
                                year=int(first_row_dt.year),
                                month=int(first_row_dt.month),
                                day=1,
                            )

                if start_dt is None:
                    first_valid_dt = row_dates.dropna().iloc[0] if not row_dates.dropna().empty else None
                    if first_valid_dt is not None:
                        start_dt = pd.Timestamp(
                            year=int(first_valid_dt.year),
                            month=int(first_valid_dt.month),
                            day=1,
                        )

                cutoff_dt = pd.Timestamp(year=cutoff_year, month=cutoff_month, day=1)
                valid_rows = row_dates.notna() & (row_dates.dt.to_period("M") <= cutoff_dt.to_period("M"))
                if start_dt is not None:
                    valid_rows = valid_rows & (row_dates.dt.to_period("M") >= start_dt.to_period("M"))

                # Count rows between first Month value and current Month value from Month column, inclusive.
                month_col_for_count = find_column(df_main, ["month"])
                if month_col_for_count:
                    month_dates = pd.to_datetime(df_main[month_col_for_count], errors="coerce")
                else:
                    month_dates = row_dates

                month_periods = month_dates.dt.to_period("M")
                if month_col_for_count:
                    first_month_idx = df_main[df_main[month_col_for_count].astype(str).str.strip().ne("")].index.min()
                    if pd.notna(first_month_idx):
                        first_period = month_periods.loc[first_month_idx]
                    else:
                        first_period = month_periods[month_periods.notna()].min()
                else:
                    first_period = month_periods[month_periods.notna()].min()

                eligible_periods = month_periods[(month_periods.notna()) & (month_periods <= cutoff_dt.to_period("M"))]
                current_period = eligible_periods.max() if not eligible_periods.empty else None

                if first_period is not None and pd.notna(first_period) and current_period is not None and pd.notna(current_period):
                    if current_period >= first_period:
                        total_number_of_months = int(((month_periods >= first_period) & (month_periods <= current_period)).sum()) + 1
                    else:
                        total_number_of_months = 0
                else:
                    total_number_of_months = 0

        miscellaneous_total = 0.0
        miscellaneous_per_member = 0.0
        registration_amount = float(user_units) * 500.0
        your_money = float(total_payment_till_date) + float(registration_amount)
        if not df_misc.empty:
            misc_amount_col = find_column(df_misc, ["Amount", "amount", "expense amount"])
            if misc_amount_col:
                miscellaneous_total = float(df_misc[misc_amount_col].apply(to_float).sum())
                if member_count > 0:
                    miscellaneous_per_member = miscellaneous_total / float(member_count)

        return UserInfo(
            user_id=token_payload.get("sub"),
            username=token_payload.get("username"),
            member_name=token_payload.get("member_name"),
            role=role,
            team_lead=token_payload.get("team_lead"),
            total_payment_till_date=round(total_payment_till_date, 2),
            total_number_of_months=total_number_of_months,
            registration_amount=round(registration_amount, 2),
            your_money=round(your_money, 2),
            miscellaneous_total=round(miscellaneous_total, 2),
            miscellaneous_per_member=round(miscellaneous_per_member, 2),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving user profile: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve user profile"
        )


@router.get("/")
async def list_users(
    token_payload: dict = Depends(get_current_user),
    limit: int = 100,
    offset: int = 0,
):
    """
    List all users (admin only).
    Requires Bearer token via the Authorize button.
    """
    try:
        
        client = get_client()
        
        # Load user credentials
        df_users = load_user_credentials(client)
        
        if df_users.empty:
            return {
                "total": 0,
                "users": [],
                "limit": limit,
                "offset": offset,
            }
        
        # Convert to list (implement proper user listing logic)
        users = []
        
        logger.info(f"Retrieved {len(users)} users")
        
        return {
            "total": len(df_users),
            "users": users,
            "limit": limit,
            "offset": offset,
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing users: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list users"
        )
