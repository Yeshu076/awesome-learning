from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel


class JobBase(BaseModel):
    title: str
    company: str
    location: Optional[str] = None
    description: Optional[str] = None
    employment_type: Optional[str] = None
    experience_level: Optional[str] = None
    is_remote: bool = False
    easy_apply: bool = False


class JobCreate(JobBase):
    linkedin_job_id: str
    linkedin_url: str


class JobResponse(JobBase):
    id: int
    linkedin_job_id: str
    linkedin_url: str
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
    salary_currency: Optional[str] = None
    is_active: bool
    posted_date: Optional[datetime] = None
    scraped_at: datetime
    
    class Config:
        from_attributes = True


class JobSearch(BaseModel):
    keywords: str
    location: Optional[str] = None
    experience_level: Optional[List[str]] = None
    employment_type: Optional[List[str]] = None
    remote: bool = False
    easy_apply: bool = True
    limit: int = 50