import hmac

import pandas as pd
import streamlit as st

from config import USER_CREDENTIALS_SHEET


def _find_column(df, candidates):
    normalized = {str(col).strip().lower(): col for col in df.columns}
    for name in candidates:
        key = name.strip().lower()
        if key in normalized:
            return normalized[key]
    return None


def load_user_credentials(sheet):
    try:
        ws = sheet.worksheet(USER_CREDENTIALS_SHEET)
        records = ws.get_all_records()
    except Exception:
        return {}

    if not records:
        return {}

    df_users = pd.DataFrame(records)
    if df_users.empty:
        return {}

    login_col = _find_column(df_users, ["login_id", "login id", "username", "user_id", "userid", "id"])
    password_col = _find_column(df_users, ["password", "pass", "pwd"])
    member_name_col = _find_column(df_users, ["member_name", "member name", "name", "full_name", "full name"])
    role_col = _find_column(df_users, ["role", "user_role", "user role"])

    if not login_col or not password_col:
        return {}

    creds = {}
    for _, row in df_users.iterrows():
        login_id = str(row.get(login_col, "")).strip()
        password = str(row.get(password_col, "")).strip()
        member_name = str(row.get(member_name_col, "")).strip() if member_name_col else ""
        role = str(row.get(role_col, "")).strip() if role_col else ""
        if login_id and password:
            creds[login_id] = {
                "password": password,
                "member_name": member_name or login_id,
                "role": role,
            }
    return creds


def render_login_page(sheet):
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
        st.session_state.user_id = ""
        st.session_state.user_name = ""
        st.session_state.user_role = ""

    if st.session_state.authenticated:
        if "user_name" not in st.session_state or not st.session_state.user_name:
            st.session_state.user_name = st.session_state.user_id
        return True

    st.markdown(
        """
        <style>
        section.main > div.block-container {
            padding-top: 0.35rem;
        }

        div[data-testid="stForm"] {
            max-width: 420px;
            margin: 0 auto;
            margin-top: 0.2rem;
            padding: 0.75rem 1rem;
            border-radius: 12px;
            background: rgba(255, 255, 255, 0.7);
        }

        div[data-testid="stImage"] {
            margin-bottom: 0.15rem;
        }

        @media (max-width: 768px) {
            section.main > div.block-container {
                padding-top: 0.5rem;
            }

            div[data-testid="stForm"] {
                max-width: 100%;
                padding: 0;
                background: transparent;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("<h2 style='text-align:center; margin: 0.1rem 0 0.2rem 0;'>Welcome to RJ ROSCA!</h2>", unsafe_allow_html=True)
    st.markdown("<h3 style='text-align:center; margin: 0.1rem 0;'>Login</h3>", unsafe_allow_html=True)
    st.markdown("<p style='text-align:center; margin: 0 0 0.35rem 0;'>Use your Login ID and password.</p>", unsafe_allow_html=True)

    with st.form("login_form"):
        login_id = st.text_input("Login ID")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Sign In")

    if submitted:
        credentials = load_user_credentials(sheet)
        user_record = credentials.get(login_id.strip(), {})
        stored_password = user_record.get("password", "")

        if stored_password and hmac.compare_digest(stored_password, password.strip()):
            st.session_state.authenticated = True
            st.session_state.user_id = login_id.strip()
            st.session_state.user_name = user_record.get("member_name", login_id.strip())
            st.session_state.user_role = user_record.get("role", "")
            st.rerun()
        else:
            st.error("Invalid Login ID or password")

    return False
