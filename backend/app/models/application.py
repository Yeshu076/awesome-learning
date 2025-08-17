from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, JSON, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.core.database import Base


class JobApplication(Base):
    """Job application model for tracking applications"""
    
    __tablename__ = "job_applications"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False)
    search_profile_id = Column(Integer, ForeignKey("search_profiles.id"), nullable=True)
    resume_id = Column(Integer, ForeignKey("resumes.id"), nullable=True)
    
    # Application status
    status = Column(String, default="pending")  # pending, applied, viewed, rejected, interview, offer
    
    # Application details
    cover_letter = Column(Text, nullable=True)
    custom_answers = Column(JSON, nullable=True)  # Store form answers as JSON
    
    # LinkedIn specific
    linkedin_application_id = Column(String, nullable=True)
    application_method = Column(String, nullable=True)  # easy_apply, external, etc.
    
    # Automation details
    applied_automatically = Column(Boolean, default=False)
    automation_log = Column(JSON, nullable=True)  # Store automation steps/errors
    
    # Timestamps
    applied_at = Column(DateTime(timezone=True), nullable=True)
    status_updated_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="job_applications")
    job = relationship("Job", back_populates="job_applications")
    search_profile = relationship("SearchProfile", back_populates="job_applications")
    resume = relationship("Resume", back_populates="job_applications")


class Resume(Base):
    """Resume model for storing user resumes"""
    
    __tablename__ = "resumes"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Resume details
    name = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    file_type = Column(String, nullable=False)  # pdf, doc, docx, txt
    
    # Parsed content
    parsed_text = Column(Text, nullable=True)
    skills = Column(JSON, nullable=True)  # Extracted skills as JSON array
    experience = Column(JSON, nullable=True)  # Work experience as JSON
    education = Column(JSON, nullable=True)  # Education as JSON
    
    # Resume metadata
    is_default = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="resumes")
    job_applications = relationship("JobApplication", back_populates="resume")


class LinkedInSession(Base):
    """LinkedIn session model for tracking login sessions"""
    
    __tablename__ = "linkedin_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Session details
    session_id = Column(String, nullable=False, index=True)
    cookies = Column(JSON, nullable=True)  # Store session cookies
    user_agent = Column(String, nullable=True)
    
    # Session status
    is_active = Column(Boolean, default=True)
    last_activity = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=True)
    
    # Automation metrics
    requests_count = Column(Integer, default=0)
    last_request_at = Column(DateTime(timezone=True), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="linkedin_sessions")