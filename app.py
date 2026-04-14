import datetime

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from auth import render_login_page
from config import EMI_CUTOFF_DAY, SHEET_NAME, USER_CREDENTIALS_SHEET
from data_loader import load_main_data, load_loan_data
from data_processor import clean_dataframe, filter_by_month, filter_loan_closed, filter_loan_disbursed
from gsheet_client import get_gspread_client
from loan_services import (
    find_column,
    get_team_member_active_loans,
    get_team_members,
    get_user_active_loans,
    normalize_member_name,
    parse_month_label,
    to_float,
)
from metrics import calculate_metrics
from reporting import generate_pdf
from ui_components import apply_styles, get_screen_width, is_mobile, metric_card
from utils import get_month_options, get_year_options


def _render_filters(df_main):
    st.markdown(
        """
        <style>
        .filter-box {
            background: linear-gradient(135deg, #1e88e5, #42a5f5);
            padding: 12px;
            border-radius: 15px;
            color: white;
            margin-bottom: 10px;
            box-shadow: 0px 4px 10px rgba(0,0,0,0.2);
        }

        .filter-title {
            font-size: 18px;
            font-weight: bold;
            margin-bottom: 10px;
        }

        div[data-baseweb="select"] {
            background-color: white !important;
            border-radius: 10px !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    with st.container():
        st.markdown('<div class="filter-box">', unsafe_allow_html=True)

        col1, col2 = st.columns(2)

        with col1:
            years = get_year_options(df_main)
            if not years:
                st.error("No year data found.")
                return None, None, None, None

            current_year = str(datetime.datetime.now().year)
            default_year_idx = years.index(current_year) if current_year in years else 0
            year = st.selectbox("Year", years, index=default_year_idx)

        with col2:
            months = [m for m in get_month_options(df_main) if m.endswith(year[-2:])]
            if not months:
                st.error(f"No month data found for year {year}.")
                return None, None, None, None

            current_month = datetime.datetime.now().strftime("%b-%y")
            next_month_date = datetime.datetime.now() + datetime.timedelta(days=30)
            previous_month_date = datetime.datetime.now() - datetime.timedelta(days=30)

            next_month = next_month_date.strftime("%b-%y")
            previous_month = previous_month_date.strftime("%b-%y")

            if next_month not in months:
                months = [next_month] + months

            default_month_idx = months.index(current_month) if current_month in months else 0
            month = st.selectbox("Month", months, index=default_month_idx)

        st.markdown("</div>", unsafe_allow_html=True)

    return month, next_month, previous_month, year


def _render_loan_donut(total_loan_paid, total_amount_to_recover, total_loan_pending):
    labels = ["Loan Paid", "Amount to Recover"]
    values = [max(total_loan_paid, 0), max(total_amount_to_recover, 0)]
    colors = ["#2e7d32", "#ef6c00"]

    fig = go.Figure(go.Pie(
        labels=labels,
        values=values,
        hole=0.6,
        marker=dict(colors=colors),
        textinfo="label+percent",
        hovertemplate="%{label}: %{value:,.2f}<extra></extra>",
    ))
    fig.update_layout(
        annotations=[dict(
            text=f"<b>Pending</b><br>{int(total_loan_pending)}",
            x=0.5, y=0.5,
            font=dict(size=16, color="#1a1a1a"),
            showarrow=False,
        )],
        showlegend=True,
        margin=dict(t=30, b=10, l=10, r=10),
        height=300,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", yanchor="bottom", y=-0.15, xanchor="center", x=0.5),
    )
    st.plotly_chart(fig, use_container_width=True)


def _load_user_credentials_df(sheet):
    try:
        credentials_sheet = sheet.worksheet(USER_CREDENTIALS_SHEET)
        records = credentials_sheet.get_all_records()
    except Exception:
        return pd.DataFrame()

    if not records:
        return pd.DataFrame()

    df_users = pd.DataFrame(records)
    return df_users if not df_users.empty else pd.DataFrame()


def _get_user_monthly_share_contribution(sheet, user_id, user_display_name, credentials_df=None):
    df_users = credentials_df.copy() if credentials_df is not None else _load_user_credentials_df(sheet)
    if df_users.empty:
        return 0.0

    login_col = find_column(df_users, ["login_id", "login id", "username", "user_id", "userid", "id"])
    member_name_col = find_column(df_users, ["member_name", "member name", "name", "full_name", "full name"])
    units_col = find_column(df_users, ["units", "unit", "no of units"])
    unit_cost_col = find_column(df_users, ["unit_cost", "unit cost", "unitcost"])

    if not units_col or not unit_cost_col:
        return 0.0

    matched_row = None

    if login_col:
        login_matches = df_users[df_users[login_col].astype(str).str.strip() == str(user_id).strip()]
        if not login_matches.empty:
            matched_row = login_matches.iloc[0]

    if matched_row is None and member_name_col:
        user_key = normalize_member_name(user_display_name)
        name_matches = df_users[df_users[member_name_col].apply(normalize_member_name) == user_key]
        if not name_matches.empty:
            matched_row = name_matches.iloc[0]

    if matched_row is None:
        return 0.0

    units = to_float(matched_row.get(units_col, 0))
    unit_cost = to_float(matched_row.get(unit_cost_col, 0))
    return float(units * unit_cost)


def _get_next_month_monthly_emi(df_user_active_loans):
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


def _build_team_upcoming_collection_table(sheet, df_loan, admin_name, team_members, credentials_df=None):
    if not team_members:
        return pd.DataFrame()

    records = []
    for team_member in team_members:
        member_active_loans = get_team_member_active_loans(df_loan, admin_name, team_member)
        monthly_share = _get_user_monthly_share_contribution(
            sheet,
            user_id="",
            user_display_name=team_member,
            credentials_df=credentials_df,
        )
        monthly_emi = _get_next_month_monthly_emi(member_active_loans)
        total_upcoming_payment = monthly_share + monthly_emi
        records.append(
            {
                "Team Member": team_member,
                "Monthly Share": round(monthly_share, 2),
                "Monthly EMI": round(monthly_emi, 2),
                "Upcoming Payment": round(total_upcoming_payment, 2),
            }
        )

    team_df = pd.DataFrame(records)
    if team_df.empty:
        return team_df

    return team_df.sort_values(by="Team Member", ascending=True).reset_index(drop=True)


def _append_team_collection_total_row(team_collection_df):
    if team_collection_df.empty:
        return team_collection_df

    total_row = pd.DataFrame(
        [
            {
                "Team Member": "Total",
                "Monthly Share": float(team_collection_df["Monthly Share"].sum()),
                "Monthly EMI": float(team_collection_df["Monthly EMI"].sum()),
                "Upcoming Payment": float(team_collection_df["Upcoming Payment"].sum()),
            }
        ]
    )
    return pd.concat([team_collection_df, total_row], ignore_index=True)


def _format_team_collection_table(team_collection_df):
    if team_collection_df.empty:
        return team_collection_df

    formatted_df = team_collection_df.copy()
    for column_name in ["Monthly Share", "Monthly EMI", "Upcoming Payment"]:
        formatted_df[column_name] = formatted_df[column_name].map(lambda value: f"₹{value:,.2f}")
    return formatted_df


def _style_team_collection_total_row(formatted_team_collection_df):
    if formatted_team_collection_df.empty:
        return formatted_team_collection_df

    def _highlight_total(row):
        is_total = str(row.get("Team Member", "")).strip().lower() == "total"
        if is_total:
            return ["background-color: #fff3bf; font-weight: 700; color: #1a1a1a;"] * len(row)
        return [""] * len(row)

    return formatted_team_collection_df.style.apply(_highlight_total, axis=1)


def _get_upcoming_payment_month_label():
    today = datetime.date.today()
    if today.day > EMI_CUTOFF_DAY:
        if today.month == 12:
            target_date = datetime.date(today.year + 1, 1, 1)
        else:
            target_date = datetime.date(today.year, today.month + 1, 1)
    else:
        target_date = datetime.date(today.year, today.month, 1)
    return target_date.strftime("%B %Y")


def _render_upcoming_payment_summary(monthly_share_contribution, monthly_emi):
    upcoming_payment_month = _get_upcoming_payment_month_label()
    total_next_month_payment = monthly_share_contribution + monthly_emi
    st.markdown(
        f"""
        <div style="
            background: linear-gradient(135deg, #0f766e, #0ea5e9);
            border-radius: 18px;
            padding: 18px;
            margin: 18px 0 10px 0;
            color: white;
            box-shadow: 0 10px 24px rgba(14, 165, 233, 0.18);
        ">
            <div style="font-size: 14px; font-weight: 700; opacity: 0.92; letter-spacing: 0.03em;">
                Upcoming Payment Summary - {upcoming_payment_month}
            </div>
            <div style="font-size: 30px; font-weight: 800; margin-top: 14px; line-height: 1.1;">
                ₹{total_next_month_payment:,.2f}
            </div>
            <div style="display:flex; gap:12px; flex-wrap:wrap; margin-top:14px;">
                <div style="flex:1; min-width:180px; background:rgba(255,255,255,0.14); border-radius:12px; padding:12px;">
                    <div style="font-size:12px; opacity:0.9;">Monthly Share Contribution</div>
                    <div style="font-size:20px; font-weight:700; margin-top:4px;">₹{monthly_share_contribution:,.2f}</div>
                </div>
                <div style="flex:1; min-width:180px; background:rgba(255,255,255,0.14); border-radius:12px; padding:12px;">
                    <div style="font-size:12px; opacity:0.9;">Monthly EMI</div>
                    <div style="font-size:20px; font-weight:700; margin-top:4px;">₹{monthly_emi:,.2f}</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_key_metrics(mobile, metrics, previous_month_balance, user_display_name, total_loan_pending, total_amount_to_recover, total_loan_paid, month):
    parsed_metric_month = parse_month_label(month)
    metric_month_label = parsed_metric_month.strftime("%B %y") if parsed_metric_month else month

    st.subheader(f" Key Metrics - {metric_month_label}")

    loan_details_heading = (
        f"#### {user_display_name}' Loan details"
        if user_display_name.lower().endswith("s")
        else f"#### {user_display_name}'s Loan details"
    )

    if mobile:
        metric_card("Total Collection", f"{metrics['total_collection']:,.2f}", "blue", "")
        metric_card("Total EMI Received", f"{metrics['total_emi']:,.2f}", "green", "")
        metric_card("Total Loans Disbursed", f"{metrics['total_loans']:,.2f}", "orange", "")
        metric_card("Loan Applications Processed", int(metrics["loan_processed"]), "purple", "")
        metric_card("Loans Cleared", int(metrics["loan_cleared"]), "red", "")
        metric_card("Total Share Amount", f"{metrics['total_share']:,.2f}", "teal", "")
        metric_card("Balance Available", f"{metrics['balance_available']:,.2f}", "pink", "")
        metric_card("Previous Month Balance", f"{previous_month_balance:,.2f}", "indigo", "")
        st.markdown(loan_details_heading)
        metric_card("Total Loan Pending", int(total_loan_pending), "purple", "")
        metric_card("Total Amount to Recover", f"{total_amount_to_recover:,.2f}", "orange", "")
        metric_card("Total Loan Paid", f"{total_loan_paid:,.2f}", "green", "")
        _render_loan_donut(total_loan_paid, total_amount_to_recover, total_loan_pending)
        return

    col1, col2, col3 = st.columns(3)
    with col1:
        metric_card("Total Collection", f"{metrics['total_collection']:,.2f}", "blue", "")
        metric_card("Total Loans Disbursed", f"{metrics['total_loans']:,.2f}", "orange", "")
    with col2:
        metric_card("Total EMI Received", f"{metrics['total_emi']:,.2f}", "green", "")
        metric_card("Loan Applications Processed", int(metrics["loan_processed"]), "purple", "")
    with col3:
        metric_card("Balance Available", f"{metrics['balance_available']:,.2f}", "pink", "")
        metric_card("Loans Cleared", int(metrics["loan_cleared"]), "red", "")

    st.markdown(loan_details_heading)
    user_col1, user_col2, user_col3 = st.columns(3)
    with user_col1:
        metric_card("Total Loan Pending", int(total_loan_pending), "purple", "")
    with user_col2:
        metric_card("Total Loan Paid", f"{total_loan_paid:,.2f}", "green", "")
    with user_col3:
        metric_card("Total Amount to Recover", f"{total_amount_to_recover:,.2f}", "orange", "")
    _render_loan_donut(total_loan_paid, total_amount_to_recover, total_loan_pending)


def main():
    st.set_page_config(page_title="RJ-ROSCA Dashboard", layout="wide")
    apply_styles()

    client = get_gspread_client()
    sheet = client.open(SHEET_NAME)

    if not render_login_page(sheet):
        st.stop()

    # Handle mobile logout triggered via query param
    if st.query_params.get("action") == "logout":
        st.session_state.authenticated = False
        st.session_state.user_id = ""
        st.session_state.user_name = ""
        st.session_state.user_role = ""
        st.query_params.clear()
        st.rerun()

    mobile = is_mobile(get_screen_width())

    if mobile:
        user_name = st.session_state.get("user_name", st.session_state.user_id)
        st.markdown(
            f"""
            <div style="display:flex; justify-content:space-between; align-items:center;
                        padding:4px 0; margin-bottom:6px;">
                <span style="font-weight:600; font-size:15px; color:#1a1a1a;">
                    Welcome {user_name}!
                </span>
                <a href="?action=logout" target="_self" style="
                    background:linear-gradient(135deg,#ef5350,#c62828);
                    color:white; padding:6px 16px; border-radius:8px;
                    text-decoration:none; font-size:13px; font-weight:600;
                    box-shadow:0 2px 6px rgba(0,0,0,0.2);">
                    Logout
                </a>
            </div>
            """,
            unsafe_allow_html=True,
        )

    if not mobile:
        with st.sidebar:
            st.success(f"Welcome {st.session_state.get('user_name', st.session_state.user_id)}!")
            if st.button("Logout", key="logout_sidebar"):
                st.session_state.authenticated = False
                st.session_state.user_id = ""
                st.session_state.user_name = ""
                st.session_state.user_role = ""
                st.rerun()

    st.title("RJ-ROSCA Financial Report")

    if not mobile:
        st.caption(f"Welcome {st.session_state.get('user_name', st.session_state.user_id)}!")

    df_main = clean_dataframe(load_main_data(sheet))
    df_loan = load_loan_data(sheet)
    credentials_df = _load_user_credentials_df(sheet)

    user_display_name = st.session_state.get("user_name", st.session_state.get("user_id", ""))
    df_user_active_loans = get_user_active_loans(df_loan, user_display_name)

    total_loan_pending = len(df_user_active_loans)
    total_amount_to_recover = float(df_user_active_loans["Amount to Pay"].sum()) if "Amount to Pay" in df_user_active_loans.columns else 0.0

    loan_amount_col = find_column(df_user_active_loans, ["Loan Amount", "Loan", "Total Loan Amount", "Disbursed Amount"])
    total_loan_paid = 0.0
    if loan_amount_col and "Amount to Pay" in df_user_active_loans.columns:
        total_loan_paid = (
            (df_user_active_loans[loan_amount_col].apply(to_float) - df_user_active_loans["Amount to Pay"].apply(to_float))
            .clip(lower=0)
            .sum()
        )

    month, next_month, previous_month, _ = _render_filters(df_main)
    if not month:
        return

    monthly_share_contribution = _get_user_monthly_share_contribution(
        sheet,
        st.session_state.get("user_id", ""),
        user_display_name,
        credentials_df,
    )
    monthly_emi = _get_next_month_monthly_emi(df_user_active_loans)

    user_role = st.session_state.get("user_role", "").strip().lower()
    is_admin = user_role == "admin"
    upcoming_payment_month = _get_upcoming_payment_month_label()
    upcoming_team_collection_label = f"Upcoming Team Collection - {upcoming_payment_month}"
    team_members = get_team_members(df_loan, user_display_name) if is_admin else []
    df_team_upcoming_collection = (
        _build_team_upcoming_collection_table(sheet, df_loan, user_display_name, team_members, credentials_df)
        if is_admin
        else pd.DataFrame()
    )
    df_team_upcoming_collection_with_total = _append_team_collection_total_row(df_team_upcoming_collection)

    if "selected_dashboard_table" not in st.session_state:
        st.session_state.selected_dashboard_table = None
    if "selected_team_member" not in st.session_state:
        st.session_state.selected_team_member = team_members[0] if team_members else None

    df_month = filter_by_month(df_main, month)
    if df_month.empty:
        st.warning(f"No data found for {month}")
        return

    metrics = calculate_metrics(df_month)
    df_prev = filter_by_month(df_main, previous_month)
    previous_month_balance = df_prev["Total Balance"].sum() if not df_prev.empty else 0

    _render_key_metrics(
        mobile,
        metrics,
        previous_month_balance,
        user_display_name,
        total_loan_pending,
        total_amount_to_recover,
        total_loan_paid,
        month,
    )

    _render_upcoming_payment_summary(monthly_share_contribution, monthly_emi)

    if mobile:
        st.markdown("### Table Viewer")
        mobile_options = [
            "Your Active Loans",
            f"Loans Disbursed ({month})",
            f"Loans Closed ({month})",
            f"Loans to Close ({next_month})",
        ]
        if is_admin:
            mobile_options.append("Team Members Loans")
            mobile_options.append(upcoming_team_collection_label)

        selected_mobile_view = st.selectbox(
            "Choose section",
            options=mobile_options,
            key="mobile_table_selector_top",
            help="Select the table section to display",
        )

        if selected_mobile_view == "Team Members Loans":
            st.session_state.selected_dashboard_table = "team_member_viewer"
        elif selected_mobile_view == upcoming_team_collection_label:
            st.session_state.selected_dashboard_table = "team_upcoming_collection"
        else:
            st.session_state.selected_dashboard_table = selected_mobile_view

        if is_admin and st.session_state.selected_dashboard_table == "team_member_viewer":
            if team_members:
                current_idx = 0
                if st.session_state.selected_team_member and st.session_state.selected_team_member in team_members:
                    current_idx = team_members.index(st.session_state.selected_team_member)
                st.session_state.selected_team_member = st.selectbox(
                    "Choose a team member",
                    options=team_members,
                    index=current_idx,
                    key="team_member_selector_mobile_top",
                )
            else:
                st.warning("No team members found for your account.")

    st.divider()

    df_disbursed = filter_loan_disbursed(df_loan, month)
    df_closed = filter_loan_closed(df_loan, month)
    df_to_close = filter_loan_closed(df_loan, next_month)

    table_options = {
        "Your Active Loans": (" Your Active Loans", df_user_active_loans, f"{user_display_name} has {len(df_user_active_loans)} active loan(s)."),
        f"Loans Disbursed ({month})": (f" Loans Disbursed ({month})", df_disbursed, None),
        f"Loans Closed ({month})": (f" Loans Closed ({month})", df_closed, None),
        f"Loans to Close ({next_month})": (f" Loans to Close ({next_month})", df_to_close, None),
    }

    if is_admin:
        table_options[upcoming_team_collection_label] = (
            f" {upcoming_team_collection_label}",
            df_team_upcoming_collection_with_total,
            None,
        )

    if not mobile:
        with st.sidebar:
            st.markdown("### Table Viewer")
            st.caption("Tap a section to open it.")
            if st.button("Dashboard Home", use_container_width=True, key="nav_home"):
                st.session_state.selected_dashboard_table = None
            for table_name in table_options.keys():
                if st.button(table_name, use_container_width=True, key=f"nav_{table_name}"):
                    st.session_state.selected_dashboard_table = table_name

            if is_admin:
                st.markdown("---")
                st.markdown("###  Team Management")
                st.caption("View your team members' loans.")
                if st.button("Team Members Loans", use_container_width=True, key="nav_team"):
                    st.session_state.selected_dashboard_table = "team_member_viewer"
                if st.button(upcoming_team_collection_label, use_container_width=True, key="nav_team_collection"):
                    st.session_state.selected_dashboard_table = "team_upcoming_collection"

                if st.session_state.selected_dashboard_table == "team_member_viewer":
                    if team_members:
                        st.markdown("#### Select Team Member")
                        current_idx = 0
                        if st.session_state.selected_team_member and st.session_state.selected_team_member in team_members:
                            current_idx = team_members.index(st.session_state.selected_team_member)
                        st.session_state.selected_team_member = st.selectbox(
                            "Choose a team member",
                            options=team_members,
                            index=current_idx,
                            key="team_member_selector",
                        )
                    else:
                        st.warning("No team members found for your account.")

    selected_table = st.session_state.selected_dashboard_table
    if selected_table == "team_member_viewer" and is_admin:
        selected_member = st.session_state.selected_team_member
        if selected_member:
            df_team_member_loans = get_team_member_active_loans(df_loan, user_display_name, selected_member)
            st.subheader(f" {selected_member}'s Active Loans")
            st.info(f"Total active loans: {len(df_team_member_loans)}")
            st.dataframe(df_team_member_loans, use_container_width=True)
        else:
            st.info("Please select a team member from the sidebar to view loans.")
    elif selected_table == "team_upcoming_collection" and is_admin:
        st.subheader(f" {upcoming_team_collection_label}")
        if df_team_upcoming_collection.empty:
            st.info("No upcoming team collection data found.")
        else:
            total_team_collection = float(df_team_upcoming_collection["Upcoming Payment"].sum())
            st.info(f"Total upcoming collection from your team: ₹{total_team_collection:,.2f}")
            formatted_team_collection = _format_team_collection_table(df_team_upcoming_collection_with_total)
            styled_team_collection = _style_team_collection_total_row(formatted_team_collection)
            st.dataframe(styled_team_collection, use_container_width=True, hide_index=True)
    else:
        selected_table_config = table_options.get(selected_table)
        if selected_table_config:
            table_title, table_df, table_message = selected_table_config
            st.subheader(table_title)
            if table_message:
                st.info(table_message)
            hide_index_for_table = selected_table == upcoming_team_collection_label
            st.dataframe(table_df, use_container_width=True, hide_index=hide_index_for_table)
        else:
            pass

    pdf_buffer = generate_pdf(
        month,
        metrics,
        df_disbursed,
        df_closed,
        df_to_close,
        df_team_upcoming_collection_with_total if is_admin else None,
    )
    st.download_button(
        label=" Download Report as PDF",
        data=pdf_buffer,
        file_name=f"ROSCA_Report_{month}.pdf",
        mime="application/pdf",
    )

    st.divider()
    st.caption("Powered by ROSCA Automation |  2026")


if __name__ == "__main__":
    main()
