"""
UI rendering and layout components.
"""
import datetime
import streamlit as st
from config import EMI_CUTOFF_DAY
from ui_components import metric_card
from utils import get_month_options, get_year_options


def render_filters(df_main):
    """Render date and time filters."""
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


def get_upcoming_payment_month_label():
    """Get the label for the upcoming payment month."""
    today = datetime.date.today()
    if today.day > EMI_CUTOFF_DAY:
        if today.month == 12:
            target_date = datetime.date(today.year + 1, 1, 1)
        else:
            target_date = datetime.date(today.year, today.month + 1, 1)
    else:
        target_date = datetime.date(today.year, today.month, 1)
    return target_date.strftime("%B %Y")


def render_upcoming_payment_summary(monthly_share_contribution, monthly_emi):
    """Render upcoming payment summary section."""
    upcoming_payment_month = get_upcoming_payment_month_label()
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
            <h4 style="margin-top: 0;">
                💰 Upcoming Payment Summary - {upcoming_payment_month}
            </h4>
            <p style="margin: 8px 0;">
                <strong>Share Amount:</strong> ₹{monthly_share_contribution:,.0f} | 
                <strong>Monthly EMI:</strong> ₹{monthly_emi:,.0f} | 
                <strong>Total:</strong> ₹{total_next_month_payment:,.0f}
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_key_metrics(mobile, metrics, previous_month_balance, user_display_name, total_loan_pending, total_amount_to_recover, total_loan_paid, month):
    """Render key metrics dashboard."""
    st.subheader(f" Key Metrics - {month}")

    loan_details_heading = (
        f"#### {user_display_name}' Loan details"
        if user_display_name.lower().endswith("s")
        else f"#### {user_display_name}'s Loan details"
    )

    if mobile:
        metric_card("Total Collection", f"₹{metrics['total_collection']:,.2f}", "blue", "")
        metric_card("Total EMI Received", f"₹{metrics['total_emi']:,.2f}", "green", "")
        metric_card("Total Loans Disbursed", f"₹{metrics['total_loans']:,.2f}", "orange", "")
        metric_card("Loan Applications Processed", int(metrics["loan_processed"]), "purple", "")
        metric_card("Loans Cleared", int(metrics["loan_cleared"]), "red", "")
        metric_card("Balance Available", f"₹{metrics['balance_available']:,.2f}", "pink", "")
        st.markdown(loan_details_heading)
        metric_card("Total Loan Pending", int(total_loan_pending), "purple", "")
        metric_card("Total Amount to Recover", f"₹{total_amount_to_recover:,.2f}", "orange", "")
        metric_card("Total Loan Paid", f"₹{total_loan_paid:,.2f}", "green", "")
        return

    row1_col1, row1_col2, row1_col3 = st.columns(3)
    with row1_col1:
        metric_card("Total Collection", f"₹{metrics['total_collection']:,.2f}", "blue", "")
    with row1_col2:
        metric_card("Total EMI Received", f"₹{metrics['total_emi']:,.2f}", "green", "")
    with row1_col3:
        metric_card("Total Loans Disbursed", f"₹{metrics['total_loans']:,.2f}", "orange", "")

    row2_col1, row2_col2, row2_col3 = st.columns(3)
    with row2_col1:
        metric_card("Loan Applications Processed", int(metrics["loan_processed"]), "purple", "")
    with row2_col2:
        metric_card("Loans Cleared", int(metrics["loan_cleared"]), "red", "")
    with row2_col3:
        metric_card("Balance Available", f"₹{metrics['balance_available']:,.2f}", "pink", "")

    st.markdown(loan_details_heading)
    user_col1, user_col2, user_col3 = st.columns(3)
    with user_col1:
        metric_card("Total Loan Pending", int(total_loan_pending), "purple", "")
    with user_col2:
        metric_card("Total Loan Paid", f"₹{total_loan_paid:,.2f}", "green", "")
    with user_col3:
        metric_card("Total Amount to Recover", f"₹{total_amount_to_recover:,.2f}", "orange", "")
