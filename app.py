import streamlit as st
import datetime

from gsheet_client import get_gspread_client
from config import SHEET_NAME
from data_loader import load_main_data, load_loan_data
from data_processor import clean_dataframe, filter_by_month, filter_loan_disbursed
from metrics import calculate_metrics
from utils import get_month_options, get_year_options


# -------------------------------
# 🎨 STYLES
# -------------------------------
def apply_styles():
    st.markdown("""
        <style>
        .main {background-color: #f5f7fa;}

        .metric-card {
            background: #e3f2fd;
            padding: 12px;
            border-radius: 12px;
            margin-bottom: 10px;
        }

        @media (max-width: 768px) {
            .block-container { padding: 0.5rem !important; }
            button { width: 100% !important; }
        }
        </style>
    """, unsafe_allow_html=True)


def metric_card(title, value):
    st.markdown(f"""
        <div class="metric-card">
            <strong>{title}</strong><br>
            {value}
        </div>
    """, unsafe_allow_html=True)


# -------------------------------
# 📱 PAGE 1: KEY METRICS
# -------------------------------
def page_key_metrics(sheet):

    st.title("📊 Key Metrics Dashboard")

    df_main = clean_dataframe(load_main_data(sheet))

    # Filters
    with st.expander("📅 Select Filters", expanded=True):

        years = get_year_options(df_main)

        if not years:
            st.error("No year data found")
            return

        year = st.selectbox("Year", years)

        months = [m for m in get_month_options(df_main) if m.endswith(year[-2:])]

        if not months:
            st.error("No month data found")
            return

        month = st.selectbox("Month", months)

    df_month = filter_by_month(df_main, month)

    if df_month.empty:
        st.warning(f"No data for {month}")
        return

    metrics = calculate_metrics(df_month)

    st.subheader("📊 Key Metrics")

    # Mobile-first stacked cards
    metric_card("Total Collection", f"₹{metrics['total_collection']:,.2f}")
    metric_card("Total EMI Received", f"₹{metrics['total_emi']:,.2f}")
    metric_card("Total Loans Disbursed", f"₹{metrics['total_loans']:,.2f}")
    metric_card("Loan Applications Processed", int(metrics['loan_processed']))
    metric_card("Loans Cleared", int(metrics['loan_cleared']))
    metric_card("Total Share Amount", f"₹{metrics['total_share']:,.2f}")
    metric_card("Balance Available", f"₹{metrics['balance_available']:,.2f}")


# -------------------------------
# 💸 PAGE 2: LOANS DISBURSED
# -------------------------------
def page_loans_disbursed(sheet):

    st.title("💸 Loans Disbursed")

    df_loan = load_loan_data(sheet)

    today = datetime.datetime.now()
    next_month = (today + datetime.timedelta(days=30)).strftime('%b-%y')

    month = st.text_input("Enter Month (e.g. Jan-26)", value=next_month)

    df_disbursed = filter_loan_disbursed(df_loan, month)

    if df_disbursed.empty:
        st.warning(f"No loans disbursed in {month}")
    else:
        st.dataframe(df_disbursed, use_container_width=True)


# -------------------------------
# 🚀 MAIN APP
# -------------------------------
def main():
    st.set_page_config(
        page_title="RJ-ROSCA Dashboard",
        layout="wide",
        page_icon="💸"
    )

    apply_styles()

    # -------------------------------
    # 📌 NAVIGATION (2 Pages)
    # -------------------------------
    page = st.sidebar.radio(
        "📂 Navigation",
        ["Key Metrics", "Loans Disbursed"]
    )

    # -------------------------------
    # 🔌 CONNECT ONCE
    # -------------------------------
    client = get_gspread_client()
    sheet = client.open(SHEET_NAME)

    # -------------------------------
    # 📄 ROUTING
    # -------------------------------
    if page == "Key Metrics":
        page_key_metrics(sheet)

    elif page == "Loans Disbursed":
        page_loans_disbursed(sheet)

    # Footer
    st.divider()
    st.caption("Powered by ROSCA Automation | © 2026")


# -------------------------------
# ▶️ RUN
# -------------------------------
if __name__ == "__main__":
    main()
