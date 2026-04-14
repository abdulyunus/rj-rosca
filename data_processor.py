import pandas as pd
from datetime import datetime
from config import NUMERIC_COLS

def clean_dataframe(df):
    if df.empty:
        return df

    for col in NUMERIC_COLS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    return df


def filter_by_month(df, month, column='Month'):
    if column not in df.columns:
        return pd.DataFrame()
    return df[df[column] == month]


def filter_loan_closed(df, month):
    return df[df['Last EMI Month'] == month] if 'Last EMI Month' in df.columns else pd.DataFrame()


def filter_loan_disbursed(df, month):
    # return df[df['EMI Start Month'] == month] if 'EMI Start Month' in df.columns else pd.DataFrame()
    return df[df['Month'] == month] if 'EMI Start Month' in df.columns else pd.DataFrame()


def filter_loan_requirements_current_and_future(df):
    """Keep only rows where the month column (col A) is >= the current calendar month."""
    if df.empty:
        return df

    month_col = df.columns[0]
    current = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    formats = ["%b-%y", "%b-%Y", "%B-%y", "%B-%Y", "%b %y", "%b %Y", "%B %y", "%B %Y",
               "%Y-%m", "%m/%Y", "%m-%Y"]

    def parse_month(val):
        if pd.isna(val) or str(val).strip() == "":
            return None
        raw = str(val).strip()
        for fmt in formats:
            try:
                return datetime.strptime(raw, fmt).replace(day=1)
            except ValueError:
                continue
        return None

    parsed = df[month_col].apply(parse_month)
    mask = parsed.apply(lambda d: d is not None and d >= current)
    return df[mask].reset_index(drop=True)
