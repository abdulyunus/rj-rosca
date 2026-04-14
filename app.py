"""
ROSCA Financial Dashboard - Main Application
Modularized version with separated concerns.
"""
import pandas as pd
import streamlit as st

from auth import render_login_page
from collection import (
    append_team_collection_total_row,
    build_overall_collection_summary,
    format_overall_collection,
    format_team_collection_table,
    get_team_collection_from_overall,
    style_team_collection_total_row,
)
from config import SHEET_NAME
from credentials import (
    get_all_team_leads,
    get_logged_in_team_lead,
    get_team_members_from_credentials,
    get_user_monthly_share_contribution,
    include_member,
    load_user_credentials_df,
)
from data_loader import load_loan_data, load_main_data
from data_processor import (
    clean_dataframe,
    filter_by_month,
    filter_loan_closed,
    filter_loan_disbursed,
)
from gsheet_client import get_gspread_client
from loan_services import (
    get_team_member_active_loans,
    get_user_active_loans,
    to_float,
)
from metrics import calculate_metrics
from reporting import generate_pdf
from ui_components import apply_styles, get_screen_width, is_mobile, metric_card
from ui import (
    get_upcoming_payment_month_label,
    render_filters,
    render_key_metrics,
    render_upcoming_payment_summary,
)


def main():
    """Main dashboard application."""
    st.set_page_config(
        page_title="RJ-ROSCA Dashboard",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    apply_styles()
    mobile = is_mobile(get_screen_width())

    client = get_gspread_client()
    sheet = client.open(SHEET_NAME)

    if not render_login_page(sheet):
        return

    df_main = clean_dataframe(load_main_data(sheet))
    df_loan = load_loan_data(sheet)
    credentials_df = load_user_credentials_df(sheet)

    user_display_name = st.session_state.get("user_name", st.session_state.get("user_id", ""))
    df_user_active_loans = get_user_active_loans(df_loan, user_display_name)

    total_loan_pending = len(df_user_active_loans)
    total_amount_to_recover = (
        float(df_user_active_loans["Amount to Pay"].sum())
        if "Amount to Pay" in df_user_active_loans.columns
        else 0.0
    )

    loan_amount_col = "Loan Amount"  # Simplified for main module
    total_loan_paid = 0.0
    if loan_amount_col and "Amount to Pay" in df_user_active_loans.columns:
        total_loan_paid = (
            (
                df_user_active_loans[loan_amount_col].apply(to_float)
                - df_user_active_loans["Amount to Pay"].apply(to_float)
            )
            .clip(lower=0)
            .sum()
        )

    month, next_month, previous_month, _ = render_filters(df_main)
    if not month:
        return

    monthly_share_contribution = get_user_monthly_share_contribution(
        sheet,
        st.session_state.get("user_id", ""),
        user_display_name,
        credentials_df,
    )

    from collection import get_next_month_monthly_emi

    monthly_emi = get_next_month_monthly_emi(df_user_active_loans)

    user_role = st.session_state.get("user_role", "").strip().lower()
    is_admin = user_role == "admin"
    upcoming_payment_month = get_upcoming_payment_month_label()
    upcoming_team_collection_label = f"Upcoming Team Collection - {upcoming_payment_month}"

    # Get logged-in user's team lead
    current_team_lead = get_logged_in_team_lead(
        st.session_state.get("user_id", ""),
        user_display_name,
        credentials_df,
    )

    # Build overall collection summary (all team leads with their collections) first
    overall_collection_label = f"Overall Collection Summary - {upcoming_payment_month}"
    
    # Prepare credentials helpers for collection builder
    credentials_helpers = {
        "get_all_team_leads": get_all_team_leads,
        "get_team_members_from_credentials": get_team_members_from_credentials,
        "get_team_member_monthly_share_contribution": __import__("credentials").get_team_member_monthly_share_contribution,
        "get_user_monthly_share_contribution": get_user_monthly_share_contribution,
    }
    
    df_overall_collection = build_overall_collection_summary(
        sheet, df_loan, credentials_df, credentials_helpers
    )

    # Derive team's upcoming collection from overall summary as a subset
    df_team_upcoming_collection = (
        get_team_collection_from_overall(df_overall_collection, current_team_lead)
        if is_admin
        else pd.DataFrame()
    )
    df_team_upcoming_collection_with_total = append_team_collection_total_row(
        df_team_upcoming_collection
    )

    team_members = []
    if is_admin:
        team_members = df_team_upcoming_collection[
            df_team_upcoming_collection["Team Member"] != "Total"
        ]["Team Member"].tolist()

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

    render_key_metrics(
        mobile,
        metrics,
        previous_month_balance,
        user_display_name,
        total_loan_pending,
        total_amount_to_recover,
        total_loan_paid,
        month,
    )

    render_upcoming_payment_summary(monthly_share_contribution, monthly_emi)

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
            mobile_options.append(overall_collection_label)

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
                if (
                    st.session_state.selected_team_member
                    and st.session_state.selected_team_member in team_members
                ):
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
        "Your Active Loans": (
            " Your Active Loans",
            df_user_active_loans,
            f"{user_display_name} has {len(df_user_active_loans)} active loan(s).",
        ),
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
                if st.button(
                    "Team Members Loans", use_container_width=True, key="nav_team"
                ):
                    st.session_state.selected_dashboard_table = "team_member_viewer"
                if st.button(
                    upcoming_team_collection_label,
                    use_container_width=True,
                    key="nav_team_collection",
                ):
                    st.session_state.selected_dashboard_table = "team_upcoming_collection"
                if st.button(
                    overall_collection_label,
                    use_container_width=True,
                    key="nav_overall_collection",
                ):
                    st.session_state.selected_dashboard_table = overall_collection_label

                if st.session_state.selected_dashboard_table == "team_member_viewer":
                    if team_members:
                        st.markdown("#### Select Team Member")
                        current_idx = 0
                        if (
                            st.session_state.selected_team_member
                            and st.session_state.selected_team_member in team_members
                        ):
                            current_idx = team_members.index(
                                st.session_state.selected_team_member
                            )
                        st.session_state.selected_team_member = st.selectbox(
                            "Choose a team member",
                            options=team_members,
                            index=current_idx,
                            key="team_member_selector",
                        )
                    else:
                        st.warning("No team members found for your account.")

    selected_table = st.session_state.selected_dashboard_table
    restricted_tables = {
        "team_member_viewer",
        "team_upcoming_collection",
        overall_collection_label,
    }
    if not is_admin and selected_table in restricted_tables:
        st.session_state.selected_dashboard_table = None
        selected_table = None

    if selected_table == "team_member_viewer" and is_admin:
        selected_member = st.session_state.selected_team_member
        if selected_member:
            df_team_member_loans = get_team_member_active_loans(
                df_loan, current_team_lead, selected_member
            )
            st.subheader(f" {selected_member}'s Active Loans")
            st.info(f"Total active loans: {len(df_team_member_loans)}")
            st.dataframe(df_team_member_loans, use_container_width=True, hide_index=True)
        else:
            st.info("Please select a team member from the sidebar to view loans.")
    elif selected_table == "team_upcoming_collection" and is_admin:
        st.subheader(f" {upcoming_team_collection_label}")
        if df_team_upcoming_collection.empty:
            st.info("No upcoming team collection data found.")
        else:
            total_monthly_share = float(
                df_team_upcoming_collection["Monthly Share"].sum()
            )
            total_monthly_emi = float(df_team_upcoming_collection["Monthly EMI"].sum())
            total_upcoming_payment = float(
                df_team_upcoming_collection["Upcoming Payment"].sum()
            )

            st.info(
                f"Total upcoming collection from your team: ₹{total_upcoming_payment:,.0f}"
            )
            formatted_team_df = format_team_collection_table(
                df_team_upcoming_collection_with_total
            )
            styled_df = style_team_collection_total_row(formatted_team_df)
            st.dataframe(styled_df, use_container_width=True, hide_index=True)

            st.caption(
                f"📊 Collection Summary: Share ₹{total_monthly_share:,.0f} + EMI ₹{total_monthly_emi:,.0f} = Total ₹{total_upcoming_payment:,.0f}"
            )
    elif selected_table == overall_collection_label and is_admin:
        st.subheader(f" {overall_collection_label}")
        formatted_overall_df = format_overall_collection(df_overall_collection)
        st.dataframe(formatted_overall_df, use_container_width=True, hide_index=True)

        if not df_overall_collection.empty:
            total_share = float(df_overall_collection["Monthly Share"].sum())
            total_emi = float(df_overall_collection["Monthly EMI"].sum())
            total_amount = float(df_overall_collection["Total"].sum())

            st.markdown("---")
            st.markdown("#### Overall Collection Summary")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Monthly Share", f"₹{total_share:,.0f}")
            with col2:
                st.metric("Total EMI Received", f"₹{total_emi:,.0f}")
            with col3:
                st.metric("Total Amount", f"₹{total_amount:,.0f}")
    else:
        selected_table_config = table_options.get(selected_table)
        if selected_table_config:
            table_title, table_df, table_message = selected_table_config
            st.subheader(table_title)
            if table_message:
                st.info(table_message)
            # Hide index for loan and collection tables requested by product
            hide_index_for_table = selected_table in [
                "Your Active Loans",
                f"Loans Disbursed ({month})",
                f"Loans Closed ({month})",
                f"Loans to Close ({next_month})",
                upcoming_team_collection_label,
                overall_collection_label,
            ]
            st.dataframe(
                table_df, use_container_width=True, hide_index=hide_index_for_table
            )
        else:
            pass

    pdf_buffer = generate_pdf(
        month,
        metrics,
        df_disbursed,
        df_closed,
        df_to_close,
        df_team_upcoming_collection_with_total if is_admin else None,
        df_overall_collection if is_admin else None,
    )
    st.download_button(
        label="📥 Download PDF Report",
        data=pdf_buffer,
        file_name=f"ROSCA_Report_{month}.pdf",
        mime="application/pdf",
        key="download_pdf",
    )

    st.caption("Powered by ROSCA Automation |  2026")


if __name__ == "__main__":
    main()
