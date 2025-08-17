from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.core.database import Base


class User(Base):
    """User model for authentication and profile management"""
    
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    
    # LinkedIn credentials (encrypted)
    linkedin_email = Column(String, nullable=True)
    linkedin_password = Column(String, nullable=True)  # Should be encrypted
    
    # Profile information
    current_position = Column(String, nullable=True)
    location = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    
    # Job preferences
    job_preferences = Column(JSON, nullable=True)  # Store as JSON
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    resumes = relationship("Resume", back_populates="user", cascade="all, delete-orphan")
    search_profiles = relationship("SearchProfile", back_populates="user", cascade="all, delete-orphan")
    job_applications = relationship("JobApplication", back_populates="user", cascade="all, delete-orphan")
    linkedin_sessions = relationship("LinkedInSession", back_populates="user", cascade="all, delete-orphan")