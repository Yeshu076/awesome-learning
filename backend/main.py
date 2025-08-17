from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import os
from loguru import logger

from app.core.config import settings
from app.core.database import engine, Base
from app.api.api_v1.api import api_router
from app.core.security import get_current_user


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    logger.info("Starting LinkedIn Automation System")
    
    # Create database tables
    Base.metadata.create_all(bind=engine)
    
    # Create directories if they don't exist
    os.makedirs("uploads", exist_ok=True)
    os.makedirs("logs", exist_ok=True)
    
    yield
    
    # Shutdown
    logger.info("Shutting down LinkedIn Automation System")


# Create FastAPI application
app = FastAPI(
    title="LinkedIn Job Application Automation System",
    description="Automated LinkedIn job application system with real-time scraping and intelligent matching",
    version="1.0.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan
)

# Set up CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# Include API router
app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "LinkedIn Job Application Automation System",
        "version": "1.0.0",
        "status": "active"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "linkedin-automation"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )