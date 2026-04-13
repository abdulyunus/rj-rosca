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

    _, logo_col, _ = st.columns([1, 1, 1])
    with logo_col:
        st.image("ROSCA.png", width=110)

    st.markdown("<h2 style='text-align:center;'>Welcome to RJ ROSCA!</h2>", unsafe_allow_html=True)
    st.title("Login")
    st.caption("Use your Login ID and password.")

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
            st.success("Login successful")
            st.rerun()

        st.error("Invalid Login ID or password")

    return False
