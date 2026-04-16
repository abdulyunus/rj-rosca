import pandas as pd
from config import (
    MAIN_RANGE,
    LOAN_RANGE,
    MAIN_SHEET,
    LOAN_SHEET,
    LOAN_REQUIREMENTS_RANGE,
    LOAN_REQUIREMENTS_SHEET,
    MISCELLANEOUS_RANGE,
    MISCELLANEOUS_SHEET,
)

def load_sheet_data(sheet, sheet_name, cell_range):
    worksheet = sheet.worksheet(sheet_name)
    raw_data = worksheet.get(cell_range)

    if not raw_data or len(raw_data) < 2:
        return pd.DataFrame()

    header = raw_data[0]
    num_cols = len(header)
    padded_rows = [row + [""] * (num_cols - len(row)) for row in raw_data[1:]]
    df = pd.DataFrame(padded_rows, columns=header)
    df.columns = [col.strip() for col in df.columns]
    return df


def load_main_data(sheet):
    return load_sheet_data(sheet, MAIN_SHEET, MAIN_RANGE)


def load_loan_data(sheet):
    return load_sheet_data(sheet, LOAN_SHEET, LOAN_RANGE)


def load_loan_requirements_data(sheet):
    return load_sheet_data(sheet, LOAN_REQUIREMENTS_SHEET, LOAN_REQUIREMENTS_RANGE)


def load_miscellaneous_data(sheet):
    return load_sheet_data(sheet, MISCELLANEOUS_SHEET, MISCELLANEOUS_RANGE)
