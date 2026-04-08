import streamlit as st
import datetime

from gsheet_client import get_gspread_client
from config import SHEET_NAME
from data_loader import load_main_data, load_loan_data
from data_processor import clean_dataframe, filter_by_month, filter_loan_closed, filter_loan_disbursed
from metrics import calculate_metrics
from utils import get_month_options, get_year_options


# -------------------------------
# 🎨 UI STYLES
# -------------------------------
def apply_styles():
    st.markdown("""
        <style>
        .main {background-color: #f5f7fa;}
        .stMetric {background-color: #e3f2fd; border-radius: 10px; padding: 10px;}
        .stDataFrame {background-color: #fff3e0; border-radius: 10px;}
        .stSelectbox {background-color: #e8f5e9; border-radius: 10px;}
        .stButton>button {background-color: #1976d2; color: white; border-radius: 8px;}

        @media (max-width: 600px) {
            .stApp { padding: 0.5rem !important; }
            .stMetric { font-size: 1.1rem !important; }
            .stDataFrame { font-size: 0.9rem !important; }
            .block-container { padding: 0.5rem 0.2rem !important; }
            .stSelectbox, .stButton>button { font-size: 1rem !important; }
        }
        </style>
    """, unsafe_allow_html=True)


# -------------------------------
# 🚀 MAIN APP
# -------------------------------
def main():
    st.set_page_config(
        page_title='RJ-ROSCA Dashboard',
        layout='wide',
        page_icon='💸'
    )

    apply_styles()

    st.title('💸 RJ-ROSCA Monthly Dashboard')
    st.markdown('---')

    # -------------------------------
    # 🔌 CONNECT
    # -------------------------------
    client = get_gspread_client()
    sheet = client.open(SHEET_NAME)

    # -------------------------------
    # 📊 LOAD DATA
    # -------------------------------
    df_main = clean_dataframe(load_main_data(sheet))
    df_loan = load_loan_data(sheet)

    # -------------------------------
    # 📅 YEAR & MONTH SELECTION
    # -------------------------------
    years = get_year_options(df_main)

    if not years:
        st.error('No year data found.')
        return

    current_year = str(datetime.datetime.now().year)
    default_year_idx = years.index(current_year) if current_year in years else 0

    year = st.selectbox('Select Year', years, index=default_year_idx)

    months = [m for m in get_month_options(df_main) if m.endswith(year[-2:])]

    if not months:
        st.error(f'No month data found for year {year}.')
        return

    current_month = datetime.datetime.now().strftime('%b-%y')
    next_month_date = datetime.datetime.now() + datetime.timedelta(days=30)
    previous_month_date = datetime.datetime.now() - datetime.timedelta(days=30)

    next_month = next_month_date.strftime('%b-%y')
    previous_month = previous_month_date.strftime('%b-%y')

    if next_month not in months:
        months = [next_month] + months

    default_month_idx = months.index(current_month) if current_month in months else 0

    month = st.selectbox('Select Month', months, index=default_month_idx)

    # -------------------------------
    # 📊 FILTER DATA
    # -------------------------------
    df_month = filter_by_month(df_main, month)

    if df_month.empty:
        st.warning(f'No data found for {month}')
        return

    # -------------------------------
    # 📈 METRICS
    # -------------------------------
    metrics = calculate_metrics(df_month)

    previous_month_balance = 0
    df_prev = filter_by_month(df_main, previous_month)

    if not df_prev.empty and 'Total Balance' in df_prev.columns:
        previous_month_balance = df_prev['Total Balance'].sum()

    st.info(f"📅 Showing data for the month: {month}")

    st.markdown("<h3 style='color:#1976d2;'>Key Metrics</h3>", unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Total Collection", f"₹{metrics['total_collection']:,.2f}")
        st.metric("Total Loans Disbursed", f"₹{metrics['total_loans']:,.2f}")
        st.metric("Prev Month Balance", f"₹{previous_month_balance:,.2f}")

    with col2:
        st.metric("Total EMI Received", f"₹{metrics['total_emi']:,.2f}")
        st.metric("Loan Applications Processed", int(metrics['loan_processed']))
        st.metric("Balance Available", f"₹{metrics['balance_available']:,.2f}")

    with col3:
        st.metric("Total Share Amount", f"₹{metrics['total_share']:,.2f}")
        st.metric("Loans Cleared", int(metrics['loan_cleared']))

    st.markdown('---')

    # -------------------------------
    # 💸 LOAN TABLES
    # -------------------------------
    st.markdown(f"<h4 style='color:#d84315;'>Loans Disbursed ({month})</h4>", unsafe_allow_html=True)

    df_disbursed = filter_loan_disbursed(df_loan, next_month)

    if not df_disbursed.empty:
        st.dataframe(
            df_disbursed.style.applymap(lambda _: 'background-color: #fffde7'),
            height=250
        )
    else:
        st.info(f'No loans disbursed in {month}', icon="💸")

    st.markdown('---')

    st.markdown(f"<h4 style='color:#1976d2;'>Loans to be Closed ({next_month})</h4>", unsafe_allow_html=True)

    df_to_close = filter_loan_closed(df_loan, next_month)

    if not df_to_close.empty:
        st.dataframe(
            df_to_close.style.applymap(lambda _: 'background-color: #e3f2fd'),
            height=250
        )
    else:
        st.info(f'No loans to be closed in {next_month}', icon="⏳")

    st.markdown('---')

    st.markdown(f"<h4 style='color:#388e3c;'>Loans Closed ({month})</h4>", unsafe_allow_html=True)

    df_closed = filter_loan_closed(df_loan, month)

    if not df_closed.empty:
        st.dataframe(
            df_closed.style.applymap(lambda _: 'background-color: #e8f5e9'),
            height=250
        )
    else:
        st.info(f'No loans closed in {month}', icon="✅")

    st.markdown('---')

    st.caption('Powered by ROSCA Automation | © 2026')


# -------------------------------
# ▶️ RUN
# -------------------------------
if __name__ == "__main__":
    main()