"""
Data processing service
"""

import pandas as pd
import logging
from datetime import datetime, date
from typing import Optional
import calendar
import re

logger = logging.getLogger(__name__)


def to_float(value) -> float:
    """Convert value to float, handling currency symbols and commas"""
    text = str(value).replace(",", "").replace("₹", "").strip()
    try:
        return float(text)
    except (ValueError, TypeError):
        return 0.0


def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Clean and standardize dataframe"""
    if df.empty:
        return df
    
    result = df.copy()
    
    # Convert numeric columns
    numeric_cols = [
        'Share Amount for the month', 'EMI received',
        'Total Amount', 'No of Application processed',
        'Loan', 'Total Balance', 'No of Loan cleared'
    ]
    
    for col in numeric_cols:
        if col in result.columns:
            result[col] = pd.to_numeric(result[col], errors='coerce').fillna(0)
    
    return result


def filter_by_month(df: pd.DataFrame, year: int, month: int) -> pd.DataFrame:
    """Filter data by year and month"""
    if df.empty:
        return df

    try:
        month_col = find_column(df, ['Month', 'month'])
        year_col = find_column(df, ['Year', 'year'])

        if month_col and year_col:
            month_series = df[month_col].apply(_parse_month_value)
            year_series = pd.to_numeric(df[year_col], errors='coerce')
            mask = (month_series == int(month)) & (year_series == int(year))
            return df[mask.fillna(False)].copy()

        if month_col:
            # Handle explicit month-year labels from sheet (for example: Apr-26, April 2026).
            month_year_series = df[month_col].apply(_parse_month_year_value)
            month_match = month_year_series.apply(lambda x: x[0] == int(month) if x else False)
            year_match = month_year_series.apply(
                lambda x: (x[1] == int(year)) if (x and x[1] is not None) else True
            )
            explicit_match = month_match & year_match
            if explicit_match.any():
                return df[explicit_match.fillna(False)].copy()

            parsed_dates = pd.to_datetime(df[month_col], errors='coerce', dayfirst=False)
            if parsed_dates.notna().any():
                mask = (
                    (parsed_dates.dt.month == int(month))
                    & (parsed_dates.dt.year == int(year))
                )
                return df[mask.fillna(False)].copy()

            month_series = df[month_col].apply(_parse_month_value)
            mask = month_series == int(month)
            return df[mask.fillna(False)].copy()

        date_col = find_column(
            df,
            ['Date', 'Month Year', 'Payment Date', 'Created At', 'Timestamp']
        )
        if date_col:
            parsed_dates = pd.to_datetime(df[date_col], errors='coerce', dayfirst=False)
            mask = (
                (parsed_dates.dt.month == int(month))
                & (parsed_dates.dt.year == int(year))
            )
            return df[mask.fillna(False)].copy()

        logger.warning("No month/year columns found; returning unfiltered data")
        return df
    except Exception as e:
        logger.warning(f"Month/year filtering failed: {str(e)}")
        return df


def _parse_month_value(value) -> Optional[int]:
    """Parse month value from numeric or month-name text"""
    text = str(value).strip()
    if not text:
        return None

    numeric = pd.to_numeric(pd.Series([text]), errors='coerce').iloc[0]
    if pd.notna(numeric):
        month = int(numeric)
        return month if 1 <= month <= 12 else None

    lower = text.lower()
    month_map = {name.lower(): idx for idx, name in enumerate(calendar.month_name) if name}
    month_map.update({abbr.lower(): idx for idx, abbr in enumerate(calendar.month_abbr) if abbr})

    for name, idx in month_map.items():
        if lower == name or lower.startswith(name + " ") or lower.startswith(name + "-") or lower.startswith(name + "/"):
            return idx

    parsed = pd.to_datetime(pd.Series([text]), errors='coerce', dayfirst=False).iloc[0]
    if pd.notna(parsed):
        return int(parsed.month)

    return None


def _parse_month_year_value(value) -> Optional[tuple[int, Optional[int]]]:
    """Parse month/year from values like Apr-26, Apr-2026, April 2026, 2026-04."""
    text = str(value).strip()
    if not text:
        return None

    mon_year_match = re.match(r"^([A-Za-z]{3,9})\s*[-/]\s*(\d{2}|\d{4})$", text)
    if mon_year_match:
        mon = _parse_month_value(mon_year_match.group(1))
        yy = mon_year_match.group(2)
        if mon:
            if len(yy) == 2:
                parsed_year = 2000 + int(yy) if int(yy) < 70 else 1900 + int(yy)
            else:
                parsed_year = int(yy)
            return mon, parsed_year

    dt = pd.to_datetime(pd.Series([text]), errors='coerce', dayfirst=False).iloc[0]
    if pd.notna(dt):
        return int(dt.month), int(dt.year)

    clean = re.sub(r"[^A-Za-z0-9]", " ", text).strip()
    if not clean:
        return None
    parts = [p for p in clean.split() if p]

    month_part = None
    year_part = None
    for part in parts:
        parsed_month = _parse_month_value(part)
        if parsed_month and month_part is None:
            month_part = parsed_month
            continue

        if part.isdigit():
            num = int(part)
            if len(part) == 4 and 1900 <= num <= 2100:
                year_part = num
            elif len(part) == 2:
                year_part = 2000 + num if num < 70 else 1900 + num

    if month_part is not None:
        return month_part, year_part

    short_match = re.match(r"^([A-Za-z]{3,9})\s*(\d{2}|\d{4})$", clean)
    if short_match:
        mon = _parse_month_value(short_match.group(1))
        yy = short_match.group(2)
        if mon:
            if len(yy) == 2:
                parsed_year = 2000 + int(yy) if int(yy) < 70 else 1900 + int(yy)
            else:
                parsed_year = int(yy)
            return mon, parsed_year

    return None


def filter_loan_disbursed(df: pd.DataFrame) -> pd.DataFrame:
    """Filter for disbursed loans"""
    if df.empty or 'Status' not in df.columns:
        return df
    
    status_col = find_column(df, ['Status', 'Loan Status'])
    if status_col:
        return df[df[status_col].astype(str).str.lower().isin(['disbursed', 'active'])].copy()
    
    return df


def filter_loan_closed(df: pd.DataFrame) -> pd.DataFrame:
    """Filter for closed loans"""
    if df.empty or 'Status' not in df.columns:
        return df
    
    status_col = find_column(df, ['Status', 'Loan Status'])
    if status_col:
        return df[df[status_col].astype(str).str.lower() == 'closed'].copy()
    
    return df


def filter_loan_requirements_current_and_future(
    df: pd.DataFrame,
    cutoff_date: Optional[date] = None,
    cutoff_day: int = 5,
) -> pd.DataFrame:
    """Filter loan requirements to current/future months using a cutoff day."""
    if df.empty:
        return df

    try:
        today = cutoff_date or date.today()
        if int(today.day) < int(cutoff_day):
            if today.month == 1:
                effective_year = today.year - 1
                effective_month = 12
            else:
                effective_year = today.year
                effective_month = today.month - 1
        else:
            effective_year = today.year
            effective_month = today.month

        effective_period = pd.Period(year=int(effective_year), month=int(effective_month), freq="M")

        month_col = find_column(df, ['Month', 'month'])
        year_col = find_column(df, ['Year', 'year'])
        date_col = find_column(df, ['Date', 'Month Year', 'Payment Date', 'Created At', 'Timestamp'])

        if month_col and year_col:
            month_series = df[month_col].apply(_parse_month_value)
            year_series = pd.to_numeric(df[year_col], errors='coerce')

            parsed_pairs = df[month_col].apply(_parse_month_year_value)
            parsed_month_series = parsed_pairs.apply(lambda x: x[0] if x else None)
            parsed_year_series = parsed_pairs.apply(lambda x: x[1] if x else None)

            month_series = month_series.fillna(pd.to_numeric(parsed_month_series, errors='coerce'))
            year_series = year_series.fillna(pd.to_numeric(parsed_year_series, errors='coerce'))

            two_digit_years = year_series.notna() & (year_series < 100)
            if two_digit_years.any():
                year_series.loc[two_digit_years] = year_series.loc[two_digit_years] + 2000

            valid = month_series.notna() & year_series.notna()
            dt_series = pd.Series(pd.NaT, index=df.index, dtype='datetime64[ns]')
            if valid.any():
                dt_series.loc[valid] = pd.to_datetime(
                    {
                        'year': year_series.loc[valid].astype(int),
                        'month': month_series.loc[valid].astype(int),
                        'day': 1,
                    },
                    errors='coerce'
                )
            mask = dt_series.notna() & (dt_series.dt.to_period('M') >= effective_period)
            return df[mask.fillna(False)].copy()

        if month_col:
            parsed_pairs = df[month_col].apply(_parse_month_year_value)
            month_series = parsed_pairs.apply(lambda x: x[0] if x else None)
            year_series = parsed_pairs.apply(lambda x: x[1] if x else None)

            has_explicit_year = year_series.notna().any()
            if has_explicit_year:
                month_num = pd.to_numeric(month_series, errors='coerce')
                year_num = pd.to_numeric(year_series, errors='coerce')
                valid = month_num.notna() & year_num.notna()
                dt_series = pd.Series(pd.NaT, index=df.index, dtype='datetime64[ns]')
                if valid.any():
                    dt_series.loc[valid] = pd.to_datetime(
                        {
                            'year': year_num.loc[valid].astype(int),
                            'month': month_num.loc[valid].astype(int),
                            'day': 1,
                        },
                        errors='coerce'
                    )
                mask = dt_series.notna() & (dt_series.dt.to_period('M') >= effective_period)
                return df[mask.fillna(False)].copy()

            parsed_dates = pd.to_datetime(df[month_col], errors='coerce', dayfirst=False)
            if parsed_dates.notna().any():
                mask = parsed_dates.dt.to_period('M') >= effective_period
                return df[mask.fillna(False)].copy()

            month_only = df[month_col].apply(_parse_month_value)
            mask = month_only >= int(effective_month)
            return df[mask.fillna(False)].copy()

        if date_col:
            parsed_dates = pd.to_datetime(df[date_col], errors='coerce', dayfirst=False)
            mask = parsed_dates.notna() & (parsed_dates.dt.to_period('M') >= effective_period)
            return df[mask.fillna(False)].copy()

        logger.warning("No date/month columns found in loan requirements; returning unfiltered data")
        return df
    except Exception as e:
        logger.warning(f"Loan requirements filtering failed: {str(e)}")
        return df


def find_column(df: pd.DataFrame, candidates: list) -> Optional[str]:
    """Find column by case-insensitive matching"""
    normalized = {str(col).strip().lower(): col for col in df.columns}
    
    for name in candidates:
        key = name.strip().lower()
        if key in normalized:
            return normalized[key]
    
    return None


def normalize_member_name(value: str) -> str:
    """Normalize member name by extracting first part and lowercasing"""
    return str(value).split("-", 1)[0].strip().lower()
