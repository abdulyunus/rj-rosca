"""
Pydantic models for data validation and API responses
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


# ============ Authentication Models ============

class LoginRequest(BaseModel):
    """Login request model"""
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class TokenResponse(BaseModel):
    """Token response model"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: Dict[str, Any]


class UserInfo(BaseModel):
    """User information model"""
    user_id: str
    username: str
    member_name: str
    role: Optional[str] = None
    team_lead: Optional[str] = None
    total_payment_till_date: float = 0.0
    total_number_of_months: int = 0
    registration_amount: float = 0.0
    your_money: float = 0.0
    upcoming_payment_share: float = 0.0
    upcoming_payment_emi: float = 0.0
    upcoming_payment_total: float = 0.0
    miscellaneous_total: float = 0.0
    miscellaneous_per_member: float = 0.0


# ============ Metrics Models ============

class MetricsResponse(BaseModel):
    """Dashboard metrics model"""
    total_collection: float = 0.0
    total_emi: float = 0.0
    total_share: float = 0.0
    total_loans: float = 0.0
    loan_processed: int = 0
    loan_cleared: int = 0
    balance_available: float = 0.0
    month: str
    year: int


class MetricsRequest(BaseModel):
    """Metrics request model"""
    year: int
    month: int


# ============ Loan Models ============

class LoanItem(BaseModel):
    """Individual loan item"""
    id: Optional[str] = None
    month: Optional[str] = None
    name: str
    team_lead: Optional[str] = None
    status: str
    loan_amount: float = 0.0
    emi_received: float = 0.0
    emi_remaining: int = 0
    amount_to_pay: float = 0.0
    emi_start_month: Optional[str] = None
    last_emi_month: Optional[str] = None
    total_months: Optional[int] = None


class LoansResponse(BaseModel):
    """Loans list response"""
    total_count: int
    loans: List[LoanItem]
    status: str = "disbursed"
    month: Optional[str] = None
    year: Optional[int] = None


# ============ Collection Models ============

class CollectionMember(BaseModel):
    """Team member collection item"""
    team_member: str
    monthly_share: float = 0.0
    monthly_emi: float = 0.0
    upcoming_payment: float = 0.0


class TeamCollection(BaseModel):
    """Team collection summary"""
    team_lead: str
    team_members: List[CollectionMember]
    total_share: float = 0.0
    total_emi: float = 0.0
    total_collection: float = 0.0


class CollectionsResponse(BaseModel):
    """Collections list response"""
    month: Optional[str] = None
    year: Optional[int] = None
    teams: List[TeamCollection]
    total_collection: float = 0.0


# ============ Dashboard Models ============

class DashboardResponse(BaseModel):
    """Complete dashboard response"""
    metrics: MetricsResponse
    user_loans: LoansResponse
    collection_summary: CollectionsResponse
    timestamp: datetime


# ============ Error Models ============

class ErrorResponse(BaseModel):
    """Error response model"""
    error: str
    detail: Optional[str] = None
    code: Optional[str] = None


# ============ Generic Response Models ============

class SuccessResponse(BaseModel):
    """Generic success response"""
    status: str = "success"
    data: Optional[Dict[str, Any]] = None
    message: Optional[str] = None
