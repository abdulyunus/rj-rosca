import pandas as pd
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
    return df[df['EMI Start Month'] == month] if 'EMI Start Month' in df.columns else pd.DataFrame()