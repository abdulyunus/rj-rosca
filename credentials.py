"""
User credentials and team member helper functions.
"""
import pandas as pd
from config import USER_CREDENTIALS_SHEET
from loan_services import find_column, normalize_member_name, get_team_members
from loan_services import to_float


def load_user_credentials_df(sheet):
    """Load user credentials from Google Sheet."""
    try:
        credentials_sheet = sheet.worksheet(USER_CREDENTIALS_SHEET)
        records = credentials_sheet.get_all_records()
    except Exception:
        return pd.DataFrame()

    if not records:
        return pd.DataFrame()

    df_users = pd.DataFrame(records)
    return df_users if not df_users.empty else pd.DataFrame()


def find_user_credentials_row(df_users, user_id="", user_display_name=""):
    """Find a user's credentials row by login ID or display name."""
    if df_users is None or df_users.empty:
        return None

    login_col = find_column(df_users, ["login_id", "login id", "username", "user_id", "userid", "id"])
    member_name_col = find_column(df_users, ["member_name", "member name", "name", "full_name", "full name"])

    if login_col and str(user_id).strip():
        login_matches = df_users[df_users[login_col].astype(str).str.strip() == str(user_id).strip()]
        if not login_matches.empty:
            return login_matches.iloc[0]

    if member_name_col and str(user_display_name).strip():
        user_key = normalize_member_name(user_display_name)
        name_matches = df_users[df_users[member_name_col].apply(normalize_member_name) == user_key]
        if not name_matches.empty:
            return name_matches.iloc[0]

    return None


def get_logged_in_team_lead(user_id, user_display_name, credentials_df=None):
    """Resolve the logged-in user's team lead from credentials."""
    df_users = credentials_df.copy() if credentials_df is not None else pd.DataFrame()
    if df_users.empty:
        return str(user_display_name).strip()

    matched_row = find_user_credentials_row(df_users, user_id, user_display_name)
    if matched_row is None:
        return str(user_display_name).strip()

    team_lead_col = find_column(df_users, ["team_lead", "team lead", "teamlead"])
    member_name_col = find_column(df_users, ["member_name", "member name", "name", "full_name", "full name"])

    team_lead = str(matched_row.get(team_lead_col, "")).strip() if team_lead_col else ""
    member_name = str(matched_row.get(member_name_col, "")).strip() if member_name_col else ""
    return team_lead or member_name or str(user_display_name).strip()


def get_team_member_monthly_share_contribution(credentials_df, team_lead, member_name):
    """Get monthly share contribution for a team member within a team."""
    if credentials_df is None or credentials_df.empty or not team_lead or not member_name:
        return 0.0

    team_lead_col = find_column(credentials_df, ["team_lead", "team lead", "teamlead"])
    member_name_col = find_column(credentials_df, ["member_name", "member name", "name", "full_name", "full name"])
    units_col = find_column(credentials_df, ["units", "unit", "no of units"])
    unit_cost_col = find_column(credentials_df, ["unit_cost", "unit cost", "unitcost"])

    if not team_lead_col or not member_name_col or not units_col or not unit_cost_col:
        return 0.0

    team_lead_key = normalize_member_name(team_lead)
    member_key = normalize_member_name(member_name)

    team_matches = credentials_df[
        (credentials_df[team_lead_col].apply(normalize_member_name) == team_lead_key)
        & (credentials_df[member_name_col].apply(normalize_member_name) == member_key)
    ]
    if team_matches.empty:
        return 0.0

    matched_row = team_matches.iloc[0]
    units = to_float(matched_row.get(units_col, 0))
    unit_cost = to_float(matched_row.get(unit_cost_col, 0))
    return float(units * unit_cost)


def get_user_monthly_share_contribution(sheet, user_id, user_display_name, credentials_df=None):
    """Get monthly share contribution for a user."""
    df_users = credentials_df.copy() if credentials_df is not None else load_user_credentials_df(sheet)
    if df_users.empty:
        return 0.0

    units_col = find_column(df_users, ["units", "unit", "no of units"])
    unit_cost_col = find_column(df_users, ["unit_cost", "unit cost", "unitcost"])

    if not units_col or not unit_cost_col:
        return 0.0

    matched_row = find_user_credentials_row(df_users, user_id, user_display_name)
    if matched_row is None:
        return 0.0

    units = to_float(matched_row.get(units_col, 0))
    unit_cost = to_float(matched_row.get(unit_cost_col, 0))
    return float(units * unit_cost)


def get_team_members_from_credentials(credentials_df, team_lead):
    """Get team members for a team lead from credentials."""
    if credentials_df is None or credentials_df.empty or not team_lead:
        return []

    team_lead_col = find_column(credentials_df, ["team_lead", "team lead", "teamlead"])
    member_name_col = find_column(credentials_df, ["member_name", "member name", "name", "full_name", "full name"])

    if not team_lead_col or not member_name_col:
        return []

    team_lead_key = normalize_member_name(team_lead)
    members = []
    seen_members = set()

    for _, row in credentials_df.iterrows():
        row_team_lead = str(row.get(team_lead_col, "")).strip()
        member_name = str(row.get(member_name_col, "")).strip()

        if not member_name or normalize_member_name(row_team_lead) != team_lead_key:
            continue

        member_key = normalize_member_name(member_name)
        if member_key in seen_members:
            continue

        seen_members.add(member_key)
        members.append(member_name)

    return sorted(members)


def include_member(team_members, member_name):
    """Add member to team list if not already present."""
    normalized_members = {normalize_member_name(member): member for member in team_members}
    member_key = normalize_member_name(member_name)

    if member_name and member_key and member_key not in normalized_members:
        team_members.append(member_name)

    return sorted(team_members)


def get_all_team_leads(credentials_df, df_loan):
    """Get all unique team leads from credentials and loan data."""
    team_leads = []
    seen_team_leads = set()

    credentials_team_lead_col = None
    if credentials_df is not None and not credentials_df.empty:
        credentials_team_lead_col = find_column(credentials_df, ["team_lead", "team lead", "teamlead"])

    if credentials_team_lead_col:
        for value in credentials_df[credentials_team_lead_col].fillna(""):
            team_lead = str(value).strip()
            team_lead_key = normalize_member_name(team_lead)
            if not team_lead or not team_lead_key or team_lead_key in seen_team_leads:
                continue
            seen_team_leads.add(team_lead_key)
            team_leads.append(team_lead)

    loan_team_lead_col = find_column(df_loan, ["Team Lead", "Team_Lead", "Team lead", "TeamLead"])
    if loan_team_lead_col:
        for value in df_loan[loan_team_lead_col].fillna(""):
            team_lead = str(value).strip()
            team_lead_key = normalize_member_name(team_lead)
            if not team_lead or not team_lead_key or team_lead_key in seen_team_leads:
                continue
            seen_team_leads.add(team_lead_key)
            team_leads.append(team_lead)

    return sorted(team_leads)
