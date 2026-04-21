"""
ROSCA Financial Dashboard - FastAPI Backend
Modern API-first backend for Flutter frontend and Render deployment
"""

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
from datetime import datetime
import os

from core.security import create_access_token
from core.cache import init_cache
from api.routes import auth, dashboard, loans, collections, users
from core.config import settings
from core.database import init_gsheet_client

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global state
gsheet_client = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown"""
    logger.info("Starting ROSCA Financial Dashboard API")
    
    try:
        # Initialize cache
        init_cache()
        logger.info("✓ Cache initialized")
        
        # Initialize Google Sheets client
        global gsheet_client
        gsheet_client = init_gsheet_client()
        logger.info("✓ Google Sheets client initialized")
        
        # Set client reference for all route modules
        auth.set_client(gsheet_client)
        dashboard.set_client(gsheet_client)
        loans.set_client(gsheet_client)
        collections.set_client(gsheet_client)
        users.set_client(gsheet_client)
        logger.info("✓ Client references set for all routes")
        
        logger.info("✓ Application startup complete")
    except Exception as e:
        logger.error(f"✗ Startup failed: {str(e)}")
        raise
    
    yield
    
    logger.info("Shutting down ROSCA Financial Dashboard API")


# Create FastAPI app
app = FastAPI(
    title="ROSCA Financial Dashboard API",
    description="Backend API for ROSCA financial management system",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware - configure for Flutter app
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["Dashboard"])
app.include_router(loans.router, prefix="/api/loans", tags=["Loans"])
app.include_router(collections.router, prefix="/api/collections", tags=["Collections"])
app.include_router(users.router, prefix="/api/users", tags=["Users"])


@app.get("/", tags=["Health"])
async def root():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "ROSCA Financial Dashboard API",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """Detailed health check"""
    return {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat(),
        "uptime_seconds": 0
    }


if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=settings.DEBUG,
        log_level="info"
    )
