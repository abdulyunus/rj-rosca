import pandas as pd
from config import MAIN_RANGE, LOAN_RANGE, MAIN_SHEET, LOAN_SHEET

def load_sheet_data(sheet, sheet_name, cell_range):
    worksheet = sheet.worksheet(sheet_name)
    raw_data = worksheet.get(cell_range)

    if not raw_data or len(raw_data) < 2:
        return pd.DataFrame()

    df = pd.DataFrame(raw_data[1:], columns=raw_data[0])
    df.columns = [col.strip() for col in df.columns]
    return df


def load_main_data(sheet):
    return load_sheet_data(sheet, MAIN_SHEET, MAIN_RANGE)


def load_loan_data(sheet):
    return load_sheet_data(sheet, LOAN_SHEET, LOAN_RANGE)