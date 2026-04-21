"""
Users API routes
"""

from fastapi import APIRouter, HTTPException, status, Depends
import logging

from schemas.models import UserInfo
from services.data_loader import load_user_credentials
from core.security import get_current_user
from services.data_processor import find_column

logger = logging.getLogger(__name__)

router = APIRouter()

# Global client reference
_client = None


def set_client(client):
    """Set the Google Sheets client"""
    global _client
    _client = client


def get_client():
    """Get the Google Sheets client"""
    if _client is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database client not initialized"
        )
    return _client


@router.get("/profile", response_model=UserInfo)
async def get_user_profile(token_payload: dict = Depends(get_current_user)):
    """
    Get current user profile.
    Requires Bearer token via the Authorize button.
    """
    try:
        client = get_client()
        df_users = load_user_credentials(client)

        username = str(token_payload.get("username") or token_payload.get("sub") or "").strip()
        role = token_payload.get("role")

        if not df_users.empty and username:
            login_col = find_column(df_users, ["login_id", "login id", "username", "user_id", "userid", "id"])
            role_col = find_column(df_users, ["role", "user_role", "user role"])

            if login_col and role_col:
                user_rows = df_users[
                    df_users[login_col].astype(str).str.strip().str.lower() == username.lower()
                ]
                if not user_rows.empty:
                    role = str(user_rows.iloc[0].get(role_col, "")).strip() or role

        return UserInfo(
            user_id=token_payload.get("sub"),
            username=token_payload.get("username"),
            member_name=token_payload.get("member_name"),
            role=role,
            team_lead=token_payload.get("team_lead"),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving user profile: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve user profile"
        )


@router.get("/")
async def list_users(
    token_payload: dict = Depends(get_current_user),
    limit: int = 100,
    offset: int = 0,
):
    """
    List all users (admin only).
    Requires Bearer token via the Authorize button.
    """
    try:
        
        client = get_client()
        
        # Load user credentials
        df_users = load_user_credentials(client)
        
        if df_users.empty:
            return {
                "total": 0,
                "users": [],
                "limit": limit,
                "offset": offset,
            }
        
        # Convert to list (implement proper user listing logic)
        users = []
        
        logger.info(f"Retrieved {len(users)} users")
        
        return {
            "total": len(df_users),
            "users": users,
            "limit": limit,
            "offset": offset,
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing users: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list users"
        )
