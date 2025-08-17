from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, JSON, Float, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.core.database import Base


class Job(Base):
    """Job model for storing LinkedIn job listings"""
    
    __tablename__ = "jobs"
    
    id = Column(Integer, primary_key=True, index=True)
    linkedin_job_id = Column(String, unique=True, index=True, nullable=False)
    
    # Job details
    title = Column(String, nullable=False, index=True)
    company = Column(String, nullable=False, index=True)
    location = Column(String, nullable=True, index=True)
    description = Column(Text, nullable=True)
    requirements = Column(Text, nullable=True)
    
    # Job metadata
    employment_type = Column(String, nullable=True)  # Full-time, Part-time, Contract, etc.
    experience_level = Column(String, nullable=True)  # Entry, Mid, Senior, etc.
    industry = Column(String, nullable=True)
    company_size = Column(String, nullable=True)
    
    # Salary information
    salary_min = Column(Float, nullable=True)
    salary_max = Column(Float, nullable=True)
    salary_currency = Column(String, nullable=True)
    
    # Remote work options
    is_remote = Column(Boolean, default=False)
    is_hybrid = Column(Boolean, default=False)
    
    # LinkedIn specific
    linkedin_url = Column(String, nullable=False)
    apply_url = Column(String, nullable=True)
    easy_apply = Column(Boolean, default=False)
    
    # Status and metadata
    is_active = Column(Boolean, default=True)
    posted_date = Column(DateTime(timezone=True), nullable=True)
    scraped_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Additional data as JSON
    additional_data = Column(JSON, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    job_applications = relationship("JobApplication", back_populates="job")


class SearchProfile(Base):
    """Search profile model for user job search preferences"""
    
    __tablename__ = "search_profiles"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Search criteria
    name = Column(String, nullable=False)
    keywords = Column(String, nullable=False)
    location = Column(String, nullable=True)
    distance = Column(Integer, default=25)  # miles
    
    # Job preferences
    employment_types = Column(JSON, nullable=True)  # ["Full-time", "Contract"]
    experience_levels = Column(JSON, nullable=True)  # ["Mid", "Senior"]
    industries = Column(JSON, nullable=True)
    company_sizes = Column(JSON, nullable=True)
    
    # Salary preferences
    salary_min = Column(Float, nullable=True)
    salary_max = Column(Float, nullable=True)
    
    # Remote preferences
    include_remote = Column(Boolean, default=True)
    include_hybrid = Column(Boolean, default=True)
    include_onsite = Column(Boolean, default=True)
    
    # Search settings
    is_active = Column(Boolean, default=True)
    auto_apply = Column(Boolean, default=False)
    max_applications_per_day = Column(Integer, default=10)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="search_profiles")
    job_applications = relationship("JobApplication", back_populates="search_profile")