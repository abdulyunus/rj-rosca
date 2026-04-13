import datetime

from config import EMI_CUTOFF_DAY


def find_column(df, candidates):
    normalized = {str(col).strip().lower(): col for col in df.columns}
    for name in candidates:
        key = name.strip().lower()
        if key in normalized:
            return normalized[key]
    return None


def normalize_member_name(value):
    return str(value).split("-", 1)[0].strip().lower()


def parse_month_label(month_value):
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


def month_span_inclusive(start_month, end_month):
    if not start_month or not end_month:
        return 0
    if end_month < start_month:
        return 0
    return (end_month.year - start_month.year) * 12 + (end_month.month - start_month.month) + 1


def to_float(value):
    text = str(value).replace(",", "").replace("₹", "").strip()
    try:
        return float(text)
    except ValueError:
        return 0.0


def derive_team_member(value):
    return str(value).split("-", 1)[0].strip()


def add_loan_projection_columns(df, emi_start_col, last_emi_col, loan_amount_col, total_months_col):
    if df.empty:
        return df

    today = datetime.date.today()
    current_month = today.replace(day=1)
    post_due_day_adjustment = 1 if today.day > EMI_CUTOFF_DAY else 0

    def _remaining_emi(row):
        if not emi_start_col or not last_emi_col:
            return 0
        start_month = parse_month_label(row.get(emi_start_col, ""))
        end_month = parse_month_label(row.get(last_emi_col, ""))
        effective_start = max(start_month, current_month) if start_month else current_month
        remaining = month_span_inclusive(effective_start, end_month)
        if post_due_day_adjustment:
            remaining = max(remaining - post_due_day_adjustment, 0)
        return remaining

    result = df.copy()
    result["EMI Remaining"] = result.apply(_remaining_emi, axis=1)

    if loan_amount_col and total_months_col:
        loan_amount_series = result[loan_amount_col].apply(to_float)
        total_months_series = result[total_months_col].apply(to_float)
        monthly_component = loan_amount_series / total_months_series.replace(0, float("nan"))
        result["Amount to Pay"] = result["EMI Remaining"] * monthly_component.fillna(0)
    else:
        result["Amount to Pay"] = 0.0

    result["Amount to Pay"] = result["Amount to Pay"].astype(float).round(2)
    return result


def get_user_active_loans(df_loan, user_name):
    if df_loan.empty:
        return df_loan

    name_col = find_column(df_loan, ["Name", "Member Name", "Customer Name"])
    status_col = find_column(df_loan, ["Status", "Loan Status"])
    emi_start_col = find_column(df_loan, ["EMI Start Month", "EMI_Start_Month", "Start Month"])
    last_emi_col = find_column(df_loan, ["Last EMI Month", "Last_EMI_Month", "End Month"])
    loan_amount_col = find_column(df_loan, ["Loan Amount", "Loan", "Total Loan Amount", "Disbursed Amount"])
    total_months_col = find_column(df_loan, ["Total Months", "Tenure", "Loan Tenure", "EMI Months"])

    if not name_col or not status_col:
        return df_loan.iloc[0:0]

    user_key = normalize_member_name(user_name)
    df_filtered = df_loan.copy()
    df_filtered["_name_key"] = df_filtered[name_col].apply(normalize_member_name)
    df_filtered["_status_key"] = df_filtered[status_col].astype(str).str.strip().str.lower()

    user_active_loans = df_filtered[
        (df_filtered["_name_key"] == user_key)
        & (df_filtered["_status_key"] == "active")
    ].copy()

    user_active_loans = add_loan_projection_columns(
        user_active_loans,
        emi_start_col,
        last_emi_col,
        loan_amount_col,
        total_months_col,
    )

    return user_active_loans.drop(columns=["_name_key", "_status_key"], errors="ignore")


def get_team_members(df_loan, admin_name):
    if df_loan.empty or not admin_name:
        return []

    team_lead_col = find_column(df_loan, ["Team Lead", "Team_Lead", "Team lead", "TeamLead"])
    name_col = find_column(df_loan, ["Name", "Member Name", "Customer Name"])
    status_col = find_column(df_loan, ["Status", "Loan Status"])

    if not team_lead_col or not name_col or not status_col:
        return []

    admin_name_stripped = admin_name.strip()
    df_filtered = df_loan[
        (df_loan[team_lead_col].astype(str).str.strip() == admin_name_stripped)
        & (df_loan[status_col].astype(str).str.strip().str.lower() == "active")
    ].copy()

    df_filtered["Team Member"] = df_filtered[name_col].apply(derive_team_member)
    team_members = df_filtered["Team Member"].dropna().unique()
    return sorted([str(m).strip() for m in team_members if str(m).strip()])


def get_team_member_active_loans(df_loan, admin_name, team_member_name):
    if df_loan.empty or not admin_name or not team_member_name:
        return df_loan.iloc[0:0]

    team_lead_col = find_column(df_loan, ["Team Lead", "Team_Lead", "Team lead", "TeamLead"])
    name_col = find_column(df_loan, ["Name", "Member Name", "Customer Name"])
    status_col = find_column(df_loan, ["Status", "Loan Status"])
    emi_start_col = find_column(df_loan, ["EMI Start Month", "EMI_Start_Month", "Start Month"])
    last_emi_col = find_column(df_loan, ["Last EMI Month", "Last_EMI_Month", "End Month"])
    loan_amount_col = find_column(df_loan, ["Loan Amount", "Loan", "Total Loan Amount", "Disbursed Amount"])
    total_months_col = find_column(df_loan, ["Total Months", "Tenure", "Loan Tenure", "EMI Months"])

    if not team_lead_col or not name_col or not status_col:
        return df_loan.iloc[0:0]

    admin_name_stripped = admin_name.strip()
    team_member_name_stripped = team_member_name.strip()

    df_filtered = df_loan.copy()
    df_filtered["Team Member"] = df_filtered[name_col].apply(derive_team_member)

    team_member_loans = df_filtered[
        (df_filtered[team_lead_col].astype(str).str.strip() == admin_name_stripped)
        & (df_filtered["Team Member"].astype(str).str.strip() == team_member_name_stripped)
        & (df_filtered[status_col].astype(str).str.strip().str.lower() == "active")
    ].copy()

    if team_member_loans.empty:
        return team_member_loans

    team_member_loans = add_loan_projection_columns(
        team_member_loans,
        emi_start_col,
        last_emi_col,
        loan_amount_col,
        total_months_col,
    )

    return team_member_loans.drop(columns=[status_col, "Team Member", team_lead_col], errors="ignore")
