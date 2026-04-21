"""
Authentication service
"""

import pandas as pd
import logging
from typing import Optional, Dict, Any
from services.data_processor import find_column, normalize_member_name
from core.security import verify_password

logger = logging.getLogger(__name__)


def load_credentials_dict(df_users: pd.DataFrame) -> Dict[str, Dict[str, Any]]:
    """Load credentials from dataframe into dictionary"""
    creds = {}
    
    if df_users.empty:
        return creds
    
    login_col = find_column(df_users, ["login_id", "login id", "username", "user_id", "userid", "id"])
    password_col = find_column(df_users, ["password", "pass", "pwd"])
    member_name_col = find_column(df_users, ["member_name", "member name", "name", "full_name", "full name"])
    role_col = find_column(df_users, ["role", "user_role", "user role"])
    team_lead_col = find_column(df_users, ["team_lead", "team lead", "teamlead"])
    
    if not login_col or not password_col:
        logger.warning("Login or password column not found in credentials sheet")
        return creds
    
    try:
        for _, row in df_users.iterrows():
            login_id = str(row.get(login_col, "")).strip()
            password = str(row.get(password_col, "")).strip()
            
            if not login_id or not password:
                continue
            
            member_name = str(row.get(member_name_col, "")).strip() if member_name_col else ""
            role = str(row.get(role_col, "")).strip() if role_col else ""
            team_lead = str(row.get(team_lead_col, "")).strip() if team_lead_col else ""
            
            creds[login_id] = {
                "password": password,
                "member_name": member_name or login_id,
                "role": role,
                "team_lead": team_lead or member_name or login_id,
            }
        
        logger.info(f"Loaded {len(creds)} user credentials")
    except Exception as e:
        logger.error(f"Error loading credentials: {str(e)}")
    
    return creds


def authenticate_user(df_users: pd.DataFrame, username: str, password: str) -> Optional[Dict[str, Any]]:
    """Authenticate user and return user info"""
    if df_users.empty:
        logger.warning("Credentials dataframe is empty")
        return None
    
    try:
        creds = load_credentials_dict(df_users)
        
        if username not in creds:
            logger.warning(f"User {username} not found")
            return None
        
        user_creds = creds[username]
        
        # Verify password
        if not verify_password(password, user_creds.get("password", "")):
            logger.warning(f"Invalid password for user {username}")
            return None
        
        # Return user info
        return {
            "user_id": username,
            "username": username,
            "member_name": user_creds.get("member_name", username),
            "role": user_creds.get("role", "member"),
            "team_lead": user_creds.get("team_lead", user_creds.get("member_name", username)),
        }
    
    except Exception as e:
        logger.error(f"Error authenticating user: {str(e)}")
        return None


def get_all_team_leads(df_users: pd.DataFrame, df_loan: pd.DataFrame = None) -> list:
    """Get list of all team leads"""
    if df_users.empty:
        return []
    
    team_lead_col = find_column(df_users, ["team_lead", "team lead", "teamlead"])
    member_name_col = find_column(df_users, ["member_name", "member name", "name", "full_name", "full name"])
    role_col = find_column(df_users, ["role", "user_role", "user role"])
    
    team_leads = set()
    
    try:
        for _, row in df_users.iterrows():
            # Check if row is explicitly a team lead
            if role_col:
                role = str(row.get(role_col, "")).strip().lower()
                if role == "team lead":
                    member_name = str(row.get(member_name_col, "")).strip()
                    if member_name:
                        team_leads.add(member_name)
            
            # Also add from team_lead column
            if team_lead_col:
                team_lead = str(row.get(team_lead_col, "")).strip()
                if team_lead:
                    team_leads.add(team_lead)
        
        logger.info(f"Found {len(team_leads)} team leads")
        return sorted(list(team_leads))
    
    except Exception as e:
        logger.error(f"Error getting team leads: {str(e)}")
        return []


def get_team_members_from_credentials(df_users: pd.DataFrame, team_lead: str) -> list:
    """Get list of team members under a team lead"""
    if df_users.empty or not team_lead:
        return []
    
    team_lead_col = find_column(df_users, ["team_lead", "team lead", "teamlead"])
    member_name_col = find_column(df_users, ["member_name", "member name", "name", "full_name", "full name"])
    
    if not team_lead_col or not member_name_col:
        return []
    
    team_lead_key = normalize_member_name(team_lead)
    members = []
    
    try:
        for _, row in df_users.iterrows():
            row_team_lead = str(row.get(team_lead_col, "")).strip()
            if normalize_member_name(row_team_lead) != team_lead_key:
                continue
            
            member_name = str(row.get(member_name_col, "")).strip()
            if member_name and normalize_member_name(member_name) != team_lead_key:
                members.append(member_name)
        
        logger.info(f"Found {len(members)} team members for {team_lead}")
        return sorted(list(set(members)))  # Remove duplicates
    
    except Exception as e:
        logger.error(f"Error getting team members: {str(e)}")
        return []
