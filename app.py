import datetime

import streamlit as st

from auth import render_login_page
from config import SHEET_NAME
from data_loader import load_main_data, load_loan_data
from data_processor import clean_dataframe, filter_by_month, filter_loan_closed, filter_loan_disbursed
from gsheet_client import get_gspread_client
from loan_services import (
    find_column,
    get_team_member_active_loans,
    get_team_members,
    get_user_active_loans,
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
            padding: 15px;
            border-radius: 15px;
            color: white;
            margin-bottom: 15px;
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
        st.markdown('<div class="filter-title"> Select Filters</div>', unsafe_allow_html=True)

        col1, col2 = st.columns(2)

        with col1:
            years = get_year_options(df_main)
            if not years:
                st.error("No year data found.")
                return None, None, None, None

            current_year = str(datetime.datetime.now().year)
            default_year_idx = years.index(current_year) if current_year in years else 0
            year = st.selectbox(" Year", years, index=default_year_idx)

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
            month = st.selectbox(" Month", months, index=default_month_idx)

        st.markdown("</div>", unsafe_allow_html=True)

    return month, next_month, previous_month, year


def _render_key_metrics(mobile, metrics, previous_month_balance, user_display_name, total_loan_pending, total_amount_to_recover, total_loan_paid, month):
    parsed_metric_month = parse_month_label(month)
    metric_month_label = parsed_metric_month.strftime("%B %y") if parsed_metric_month else month

    st.info(f" Showing data for: {month}")
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


def main():
    st.set_page_config(page_title="RJ-ROSCA Dashboard", layout="wide", page_icon="ROSCA.png")
    apply_styles()

    client = get_gspread_client()
    sheet = client.open(SHEET_NAME)

    if not render_login_page(sheet):
        st.stop()

    mobile = is_mobile(get_screen_width())

    auth_col, logout_col = st.columns([0.75, 0.25])
    with auth_col:
        st.caption(f"Welcome {st.session_state.get('user_name', st.session_state.user_id)}!")
    with logout_col:
        if st.button("Logout", use_container_width=True, key="logout_main"):
            st.session_state.authenticated = False
            st.session_state.user_id = ""
            st.session_state.user_name = ""
            st.session_state.user_role = ""
            st.rerun()

    if not mobile:
        with st.sidebar:
            st.success(f"Welcome {st.session_state.get('user_name', st.session_state.user_id)}!")
            if st.button("Logout", key="logout_sidebar"):
                st.session_state.authenticated = False
                st.session_state.user_id = ""
                st.session_state.user_name = ""
                st.session_state.user_role = ""
                st.rerun()

    st.title(" RJ-ROSCA Financial Report")

    df_main = clean_dataframe(load_main_data(sheet))
    df_loan = load_loan_data(sheet)

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

    user_role = st.session_state.get("user_role", "").strip().lower()
    is_admin = user_role == "admin"
    team_members = get_team_members(df_loan, user_display_name) if is_admin else []

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

    if mobile:
        st.markdown("### Table Viewer")
        mobile_options = [
            "Dashboard Home",
            "Your Active Loans",
            f"Loans Disbursed ({month})",
            f"Loans Closed ({month})",
            f"Loans to Close ({next_month})",
        ]
        if is_admin:
            mobile_options.append("Team Members Loans")

        selected_mobile_view = st.selectbox(
            "Choose section",
            options=mobile_options,
            key="mobile_table_selector_top",
            help="Select the table section to display",
        )

        if selected_mobile_view == "Dashboard Home":
            st.session_state.selected_dashboard_table = None
        elif selected_mobile_view == "Team Members Loans":
            st.session_state.selected_dashboard_table = "team_member_viewer"
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
    else:
        selected_table_config = table_options.get(selected_table)
        if selected_table_config:
            table_title, table_df, table_message = selected_table_config
            st.subheader(table_title)
            if table_message:
                st.info(table_message)
            st.dataframe(table_df, use_container_width=True)
        else:
            st.info("Choose a section from the Table Viewer to view it.")

    pdf_buffer = generate_pdf(month, metrics, df_disbursed, df_closed, df_to_close)
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
