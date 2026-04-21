"""
Authentication API routes
"""

from fastapi import APIRouter, HTTPException, status, Header, Depends
from datetime import timedelta
import logging

from schemas.models import LoginRequest, TokenResponse, UserInfo, ErrorResponse
from core.security import create_access_token, verify_token, get_current_user
from core.config import settings
from services.data_loader import load_user_credentials
from services.auth_service import authenticate_user

logger = logging.getLogger(__name__)

router = APIRouter()

# Global client reference (set by main app)
_client = None


def set_client(client):
    """Set the Google Sheets client (called from main.py)"""
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


@router.post(
    "/login",
    response_model=TokenResponse,
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    }
)
async def login(request: LoginRequest):
    """
    Login endpoint
    
    Returns JWT token and user information
    """
    try:
        client = get_client()
        
        # Load user credentials
        df_users = load_user_credentials(client)
        
        if df_users.empty:
            logger.warning("No user credentials found")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )
        
        # Authenticate user
        user_info = authenticate_user(df_users, request.username, request.password)
        
        if not user_info:
            logger.warning(f"Authentication failed for user: {request.username}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password"
            )
        
        # Create access token
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={
                "sub": user_info.get("user_id"),
                "username": user_info.get("username"),
                "member_name": user_info.get("member_name"),
                "team_lead": user_info.get("team_lead"),
            },
            expires_delta=access_token_expires
        )
        
        logger.info(f"User {request.username} logged in successfully")
        
        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user=UserInfo(
                user_id=user_info.get("user_id"),
                username=user_info.get("username"),
                member_name=user_info.get("member_name"),
                role=user_info.get("role"),
                team_lead=user_info.get("team_lead"),
            ).dict()
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed"
        )


@router.post("/logout", tags=["Authentication"])
async def logout():
    """
    Logout endpoint
    
    Note: JWT tokens are stateless, so logout on client side by discarding token
    """
    return {
        "status": "success",
        "message": "Logged out successfully. Please discard the token."
    }


@router.get("/me", response_model=UserInfo)
async def get_user_from_token(payload: dict = Depends(get_current_user)):
    """
    Get current user information from token.
    Click the lock icon in Swagger UI and enter your token to authorize.
    """
    return UserInfo(
        user_id=payload.get("sub"),
        username=payload.get("username"),
        member_name=payload.get("member_name"),
        team_lead=payload.get("team_lead"),
    )


@router.post("/verify-token")
async def verify_token_endpoint(token: str):
    """
    Verify if a token is valid
    """
    try:
        payload = verify_token(token)
        return {
            "valid": True,
            "user_id": payload.get("sub"),
            "username": payload.get("username"),
        }
    except HTTPException:
        return {"valid": False}
    except Exception:
        return {"valid": False}
