from pydantic_settings import BaseSettings
from typing import Optional, List
import os


class Settings(BaseSettings):
    """Application settings"""
    
    # API Settings
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "LinkedIn Automation System"
    
    # Database
    DATABASE_URL: str = "postgresql://linkedin_user:linkedin_pass@localhost:5432/linkedin_automation"
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # LinkedIn Credentials
    LINKEDIN_EMAIL: str
    LINKEDIN_PASSWORD: str
    
    # Security
    SECRET_KEY: str = "change-this-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # AI/ML
    GEMINI_API_KEY: Optional[str] = None
    
    # LinkedIn Automation Settings
    LINKEDIN_BASE_URL: str = "https://www.linkedin.com"
    MAX_APPLICATIONS_PER_DAY: int = 50
    SCRAPING_DELAY_MIN: int = 2
    SCRAPING_DELAY_MAX: int = 5
    SESSION_TIMEOUT: int = 3600
    
    # Browser Settings
    HEADLESS_BROWSER: bool = True
    BROWSER_TIMEOUT: int = 30000
    USER_AGENT_ROTATION: bool = True
    
    # Celery Configuration
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"
    
    # File Upload
    MAX_FILE_SIZE: int = 10485760  # 10MB
    ALLOWED_EXTENSIONS: List[str] = ["pdf", "doc", "docx", "txt"]
    
    # Environment
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    
    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "logs/linkedin_automation.log"
    
    class Config:
        env_file = ".env"
        case_sensitive = True


# Create settings instance
settings = Settings()