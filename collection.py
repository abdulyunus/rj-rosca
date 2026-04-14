"""
Collection building, formatting, and styling functions.
"""
import pandas as pd
from loan_services import find_column, normalize_member_name, get_team_member_active_loans
from loan_services import to_float


def get_team_collection_from_overall(df_overall_collection, team_lead):
    """
    Extract team collection for a specific team lead from the overall collection summary.
    Filters rows where Team Lead matches and converts to upcoming collection format.
    """
    if df_overall_collection.empty or not team_lead:
        return pd.DataFrame()

    team_lead_key = normalize_member_name(team_lead)
    filtered_rows = []

    for _, row in df_overall_collection.iterrows():
        row_team_lead = str(row.get("Team Lead", "")).strip()
        if normalize_member_name(row_team_lead) != team_lead_key:
            continue

        member_name = str(row.get("Member Name", "")).strip()
        if not member_name:
            continue

        filtered_rows.append({
            "Team Member": member_name,
            "Monthly Share": row.get("Monthly Share", 0.0),
            "Monthly EMI": row.get("Monthly EMI", 0.0),
            "Upcoming Payment": row.get("Total", 0.0),
        })

    if not filtered_rows:
        return pd.DataFrame()

    team_df = pd.DataFrame(filtered_rows)
    return team_df.sort_values(by="Team Member", ascending=True).reset_index(drop=True)


def get_next_month_monthly_emi(df_user_active_loans):
    """Calculate monthly EMI for next month from user loans."""
    if df_user_active_loans.empty:
        return 0.0

    if "Amount to Pay" not in df_user_active_loans.columns or "EMI Remaining" not in df_user_active_loans.columns:
        return 0.0

    monthly_emi = 0.0
    for _, row in df_user_active_loans.iterrows():
        amount_to_pay = to_float(row.get("Amount to Pay", 0))
        emi_remaining = to_float(row.get("EMI Remaining", 0))
        if emi_remaining > 0:
            monthly_emi += amount_to_pay / emi_remaining

    return float(monthly_emi)


def build_overall_collection_summary(sheet, df_loan, credentials_df, credentials_helpers):
    """Build overall collection summary including all Team Leads and their members."""
    get_all_team_leads = credentials_helpers["get_all_team_leads"]
    get_team_members_from_credentials = credentials_helpers["get_team_members_from_credentials"]
    get_team_member_monthly_share = credentials_helpers["get_team_member_monthly_share_contribution"]
    get_user_monthly_share = credentials_helpers["get_user_monthly_share_contribution"]
    
    all_team_leads = get_all_team_leads(credentials_df, df_loan)
    if not all_team_leads:
        return pd.DataFrame()
    
    records = []
    
    for team_lead in all_team_leads:
        seen_member_keys = set()

        # Add Team Lead's own collection
        lead_share = get_user_monthly_share(sheet, "", team_lead, credentials_df)
        df_lead_loans = get_team_member_active_loans(df_loan, team_lead, team_lead)
        lead_emi = get_next_month_monthly_emi(df_lead_loans)
        lead_total = lead_share + lead_emi
        seen_member_keys.add(normalize_member_name(team_lead))

        records.append({
            "Team Lead": team_lead,
            "Member Name": team_lead,
            "Monthly Share": round(lead_share, 2),
            "Monthly EMI": round(lead_emi, 2),
            "Total": round(lead_total, 2),
        })
        
        # Add team members
        team_members = get_team_members_from_credentials(credentials_df, team_lead)

        for member in team_members:
            member_key = normalize_member_name(member)
            if member_key in seen_member_keys:
                continue

            seen_member_keys.add(member_key)
            member_share = get_team_member_monthly_share(credentials_df, team_lead, member)
            if member_share == 0.0:
                member_share = get_user_monthly_share(sheet, "", member, credentials_df)
            df_member_loans = get_team_member_active_loans(df_loan, team_lead, member)
            member_emi = get_next_month_monthly_emi(df_member_loans)
            member_total = member_share + member_emi

            records.append({
                "Team Lead": team_lead,
                "Member Name": member,
                "Monthly Share": round(member_share, 2),
                "Monthly EMI": round(member_emi, 2),
                "Total": round(member_total, 2),
            })
    
    return pd.DataFrame(records)


def append_team_collection_total_row(team_collection_df):
    """Add a totals row to team collection dataframe."""
    if team_collection_df.empty:
        return team_collection_df

    total_row_data = {
        "Team Member": "Total",
        "Monthly Share": float(team_collection_df["Monthly Share"].sum()),
        "Monthly EMI": float(team_collection_df["Monthly EMI"].sum()),
        "Upcoming Payment": float(team_collection_df["Upcoming Payment"].sum()),
    }

    total_row = pd.DataFrame([total_row_data])
    return pd.concat([team_collection_df, total_row], ignore_index=True)


def format_team_collection_table(team_collection_df):
    """Format team collection table with currency and numbers."""
    if team_collection_df.empty:
        return team_collection_df

    formatted_df = team_collection_df.copy()
    for column_name in ["Monthly Share", "Monthly EMI", "Upcoming Payment"]:
        formatted_df[column_name] = formatted_df[column_name].apply(lambda value: to_float(value)).map(lambda value: f"₹{value:,.0f}")
    return formatted_df


def style_team_collection_total_row(formatted_team_collection_df):
    """Apply styling to total row in team collection table."""
    if formatted_team_collection_df.empty:
        return formatted_team_collection_df

    def _highlight_total(row):
        is_total = str(row.get("Team Member", "")).strip().lower() == "total"
        if is_total:
            return ["background-color: #fff3bf; font-weight: 700; color: #1a1a1a; text-align: center;"] * len(row)
        return ["text-align: center;"] * len(row)

    return formatted_team_collection_df.style.apply(_highlight_total, axis=1)


def format_overall_collection(overall_collection_df):
    """Format overall collection summary with currency symbols and add Sr No column."""
    if overall_collection_df.empty:
        return overall_collection_df
    
    formatted_df = overall_collection_df.copy()
    formatted_df.insert(0, "Sr No", range(1, len(formatted_df) + 1))
    
    for col in ["Monthly Share", "Monthly EMI", "Total"]:
        if col in formatted_df.columns:
            formatted_df[col] = formatted_df[col].map(lambda v: f"₹{v:,.0f}")
    return formatted_df
