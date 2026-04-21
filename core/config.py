"""
Configuration and settings management
"""

from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict
from typing import List
import os


class Settings(BaseSettings):
    """Application settings from environment variables"""

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )
    
    # App
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    PORT: int = int(os.getenv("PORT", "8000"))
    
    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours
    
    # CORS
    CORS_ORIGINS: str = os.getenv(
        "CORS_ORIGINS",
        "http://localhost:3000,http://localhost:8080,http://localhost:8081,*"
    )

    def get_cors_origins(self) -> List[str]:
        text = str(self.CORS_ORIGINS).strip()
        if not text:
            return []
        return [origin.strip() for origin in text.split(",") if origin.strip()]
    
    # Google Sheets
    CREDENTIALS_FILE: str = os.getenv("CREDENTIALS_FILE", "credentials.json")
    SHEET_NAME: str = os.getenv("SHEET_NAME", "RJ_ROSCA_General_July23")
    
    # Database/Cache
    CACHE_TTL_SECONDS: int = 3600  # 1 hour
    
    # Sheets configuration
    USER_CREDENTIALS_SHEET: str = "user_credentails"
    MAIN_SHEET: str = "Main_Calculations"
    LOAN_SHEET: str = "loan_waterfall_c2"
    LOAN_REQUIREMENTS_SHEET: str = "loan_requirements"
    MISCELLANEOUS_SHEET: str = "miscellaneous"
    
    # Ranges
    MAIN_RANGE: str = "A1:Q100"
    LOAN_RANGE: str = "A1:H100000"
    LOAN_REQUIREMENTS_RANGE: str = "A1:F10000"
    MISCELLANEOUS_RANGE: str = "A1:Z10000"
    
    # EMI settings
    EMI_CUTOFF_DAY: int = 5
    
settings = Settings()
