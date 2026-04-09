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
        return 1024


def is_mobile(width):
    return width < 768


# -------------------------------
# 🎨 STYLES (Animated + Colorful)
# -------------------------------
def apply_styles():
    st.markdown("""
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <meta name="theme-color" content="#1976d2">
        <link rel="apple-touch-icon" href="logo.png">
    """, unsafe_allow_html=True)

    st.markdown("""
        <style>

        /* 🌈 Background */
        .stApp {
            background: linear-gradient(135deg, #e3f2fd, #fce4ec, #e8f5e9);
            background-attachment: fixed;
        }

        .block-container {
            padding-top: 1rem;
            padding-bottom: 1rem;
        }

        /* 🎯 KPI Cards */
        .metric-card {
            padding: 16px;
            border-radius: 16px;
            margin-bottom: 14px;
            color: white;
            font-weight: 500;
            box-shadow: 0px 4px 12px rgba(0,0,0,0.15);

            transition: all 0.3s ease-in-out;
            cursor: pointer;
        }

        /* ✨ Hover Animation */
        .metric-card:hover {
            transform: translateY(-6px) scale(1.02);
            box-shadow: 0px 8px 20px rgba(0,0,0,0.25);
        }

        /* 🎨 Colors */
        .blue { background: linear-gradient(135deg, #42a5f5, #1e88e5); }
        .green { background: linear-gradient(135deg, #66bb6a, #2e7d32); }
        .orange { background: linear-gradient(135deg, #ffa726, #ef6c00); }
        .purple { background: linear-gradient(135deg, #ab47bc, #6a1b9a); }
        .red { background: linear-gradient(135deg, #ef5350, #c62828); }
        .teal { background: linear-gradient(135deg, #26c6da, #00838f); }
        .pink { background: linear-gradient(135deg, #ec407a, #ad1457); }
        .indigo { background: linear-gradient(135deg, #5c6bc0, #283593); }

        /* 📱 Mobile */
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

            .metric-card:hover {
                transform: none;
                box-shadow: 0px 4px 12px rgba(0,0,0,0.15);
            }
        }

        </style>
    """, unsafe_allow_html=True)

st.markdown("""
<style>

/* 🔥 Hide Streamlit default UI */
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}

/* 🔥 Remove top bar completely */
[data-testid="stHeader"] {
    display: none;
}

/* 🔥 Remove toolbar (GitHub / Deploy button) */
[data-testid="stToolbar"] {
    display: none !important;
}

/* 🔥 Remove decoration (top right icons) */
[data-testid="stDecoration"] {
    display: none !important;
}

/* 🔥 Remove status widget */
[data-testid="stStatusWidget"] {
    display: none !important;
}

/* 🔥 Remove fullscreen button */
button[title="View fullscreen"] {
    display: none !important;
}

/* 🔥 Prevent top spacing issue */
.block-container {
    padding-top: 0rem !important;
}

</style>
""", unsafe_allow_html=True)

st.markdown("""
<style>
html, body, .stApp {
    overflow-x: hidden !important;
}
</style>
""", unsafe_allow_html=True)

st.set_page_config(layout="centered")

# -------------------------------
# 📦 KPI CARD
# -------------------------------
def metric_card(title, value, color, icon="📊"):
    st.markdown(f"""
        <div class="metric-card {color}">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <div style="font-size:14px;">{title}</div>
                <div style="font-size:22px;">{icon}</div>
            </div>
            <div style="font-size:22px; font-weight:bold; margin-top:5px;">
                {value}
            </div>
        </div>
    """, unsafe_allow_html=True)


# -------------------------------
# 🚀 MAIN APP
# -------------------------------
def main():
    st.set_page_config(
        page_title='RJ-ROSCA Dashboard',
        layout='wide',
        # page_icon='💸'
        page_icon='logo.png'
    )

    apply_styles()

    # Detect device
    screen_width = get_screen_width()
    mobile = is_mobile(screen_width)

    # Title and logo side by side
    col_title, col_logo = st.columns([0.8, 0.2])
    with col_title:
        st.title('💸 RJ-ROSCA Financial Report')
    with col_logo:
        st.image("logo.png", width=80)

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
    # 📅 FILTERS (FANCY UI)
    # -------------------------------
    st.markdown("""
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
    """, unsafe_allow_html=True)

    with st.container():
        st.markdown('<div class="filter-box">', unsafe_allow_html=True)
        st.markdown('<div class="filter-title">📅 Select Filters</div>', unsafe_allow_html=True)

        col1, col2 = st.columns(2)

        # Year Dropdown
        with col1:
            years = get_year_options(df_main)

            if not years:
                st.error('No year data found.')
                return

            current_year = str(datetime.datetime.now().year)
            default_year_idx = years.index(current_year) if current_year in years else 0

            year = st.selectbox("📆 Year", years, index=default_year_idx)

        # Month Dropdown
        with col2:
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

            month = st.selectbox("📅 Month", months, index=default_month_idx)

        st.markdown('</div>', unsafe_allow_html=True)

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
        metric_card("Total Collection", f"₹{metrics['total_collection']:,.2f}", "blue", "💰")
        metric_card("Total EMI Received", f"₹{metrics['total_emi']:,.2f}", "green", "💵")
        metric_card("Total Loans Disbursed", f"₹{metrics['total_loans']:,.2f}", "orange", "🏦")
        metric_card("Loan Applications Processed", int(metrics['loan_processed']), "purple", "📄")
        metric_card("Loans Cleared", int(metrics['loan_cleared']), "red", "✅")
        metric_card("Total Share Amount", f"₹{metrics['total_share']:,.2f}", "teal", "📊")
        metric_card("Balance Available", f"₹{metrics['balance_available']:,.2f}", "pink", "💳")
        metric_card("Previous Month Balance", f"₹{previous_month_balance:,.2f}", "indigo", "📅")

    else:
        col1, col2, col3 = st.columns(3)

        with col1:
            metric_card("Total Collection", f"₹{metrics['total_collection']:,.2f}", "blue", "💰")
            metric_card("Total Loans Disbursed", f"₹{metrics['total_loans']:,.2f}", "orange", "🏦")

        with col2:
            metric_card("Total EMI Received", f"₹{metrics['total_emi']:,.2f}", "green", "💵")
            metric_card("Loan Applications Processed", int(metrics['loan_processed']), "purple", "📄")

        with col3:
            metric_card("Balance Available", f"₹{metrics['balance_available']:,.2f}", "pink", "💳")
            metric_card("Loans Cleared", int(metrics['loan_cleared']), "red", "✅")

    st.divider()

    # -------------------------------
    # 💸 LOAN TABLES
    # -------------------------------
    # df_disbursed = filter_loan_disbursed(df_loan, next_month)
    # df_to_close = filter_loan_closed(df_loan, next_month)
    # df_closed = filter_loan_closed(df_loan, month)

    # 💸 Loans Disbursed → Selected Month
    df_disbursed = filter_loan_disbursed(df_loan, month)

    # ✅ Loans Closed → Selected Month
    df_closed = filter_loan_closed(df_loan, month)

    # ⏳ Loans to Close → Next Month
    df_to_close = filter_loan_closed(df_loan, next_month)

    if mobile:
        with st.expander(f"💸 Loans Disbursed ({month})"):
            st.dataframe(df_disbursed, use_container_width=True)

        with st.expander(f"✅ Loans Closed ({month})"):
            st.dataframe(df_closed, use_container_width=True)

        with st.expander(f"⏳ Loans to Close ({next_month})"):
            st.dataframe(df_to_close, use_container_width=True)



    else:
        st.subheader(f"💸 Loans Disbursed ({month})")
        st.dataframe(df_disbursed, use_container_width=True)

        st.subheader(f"✅ Loans Closed ({month})")
        st.dataframe(df_closed, use_container_width=True)

        st.subheader(f"⏳ Loans to Close ({next_month})")
        st.dataframe(df_to_close, use_container_width=True)

    st.divider()
    st.caption('Powered by ROSCA Automation | © 2026')


# -------------------------------
# ▶️ RUN
# -------------------------------
if __name__ == "__main__":
    main()
