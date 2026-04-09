import streamlit as st
import datetime
import streamlit.components.v1 as components

from gsheet_client import get_gspread_client
from config import SHEET_NAME
from data_loader import load_main_data, load_loan_data
from data_processor import clean_dataframe, filter_by_month, filter_loan_closed, filter_loan_disbursed
from metrics import calculate_metrics
from utils import get_month_options, get_year_options


# -------------------------------
# 📱 DEVICE DETECTION
# -------------------------------
def get_screen_width():
    width = components.html(
        """
        <script>
        const width = window.innerWidth;
        document.write(width);
        </script>
        """,
        height=0,
    )
    try:
        return int(width)
    except:
        return 1024  # fallback (desktop)


def is_mobile(width):
    return width < 768


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
            .block-container {
                padding: 0.5rem !important;
            }

            h1, h2, h3 {
                font-size: 1.2rem !important;
            }

            button {
                width: 100% !important;
            }

            div[data-testid="column"] {
                width: 100% !important;
                flex: 1 1 100% !important;
            }
        }
        </style>
    """, unsafe_allow_html=True)


# -------------------------------
# 📦 METRIC CARD
# -------------------------------
def metric_card(title, value):
    st.markdown(f"""
        <div class="metric-card">
            <strong>{title}</strong><br>
            {value}
        </div>
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

    # Detect device
    screen_width = get_screen_width()
    mobile = is_mobile(screen_width)

    st.title('💸 RJ-ROSCA Dashboard')

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
    # 📅 FILTERS
    # -------------------------------
    with st.expander("📅 Select Filters", expanded=True):

        years = get_year_options(df_main)

        if not years:
            st.error('No year data found.')
            return

        current_year = str(datetime.datetime.now().year)
        default_year_idx = years.index(current_year) if current_year in years else 0

        year = st.selectbox('Year', years, index=default_year_idx)

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

        month = st.selectbox('Month', months, index=default_month_idx)

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

    df_prev = filter_by_month(df_main, previous_month)
    previous_month_balance = df_prev['Total Balance'].sum() if not df_prev.empty else 0

    st.info(f"📅 Showing data for: {month}")
    st.subheader("📊 Key Metrics")

    if mobile:
        # 📱 Mobile Layout
        metric_card("Total Collection", f"₹{metrics['total_collection']:,.2f}")
        metric_card("Total EMI Received", f"₹{metrics['total_emi']:,.2f}")
        metric_card("Total Loans Disbursed", f"₹{metrics['total_loans']:,.2f}")
        metric_card("Loan Applications Processed", int(metrics['loan_processed']))
        metric_card("Loans Cleared", int(metrics['loan_cleared']))
        metric_card("Total Share Amount", f"₹{metrics['total_share']:,.2f}")
        metric_card("Balance Available", f"₹{metrics['balance_available']:,.2f}")
        metric_card("Previous Month Balance", f"₹{previous_month_balance:,.2f}")

    else:
        # 🖥 Desktop Layout
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

    st.divider()

    # -------------------------------
    # 💸 LOAN TABLES
    # -------------------------------
    df_disbursed = filter_loan_disbursed(df_loan, next_month)
    df_to_close = filter_loan_closed(df_loan, next_month)
    df_closed = filter_loan_closed(df_loan, month)

    if mobile:
        # 📱 Mobile → Expanders
        with st.expander(f"💸 Loans Disbursed ({month})"):
            st.dataframe(df_disbursed, use_container_width=True)

        with st.expander(f"⏳ Loans to Close ({next_month})"):
            st.dataframe(df_to_close, use_container_width=True)

        with st.expander(f"✅ Loans Closed ({month})"):
            st.dataframe(df_closed, use_container_width=True)

    else:
        # 🖥 Desktop → Full tables
        st.subheader(f"💸 Loans Disbursed ({month})")
        st.dataframe(df_disbursed, use_container_width=True)

        st.subheader(f"⏳ Loans to Close ({next_month})")
        st.dataframe(df_to_close, use_container_width=True)

        st.subheader(f"✅ Loans Closed ({month})")
        st.dataframe(df_closed, use_container_width=True)

    st.divider()
    st.caption('Powered by ROSCA Automation | © 2026')


# -------------------------------
# ▶️ RUN
# -------------------------------
if __name__ == "__main__":
    main()
