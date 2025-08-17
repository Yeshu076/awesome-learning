from typing import Optional, Dict, Any
from pydantic import BaseModel, EmailStr


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    current_position: Optional[str] = None
    location: Optional[str] = None
    phone: Optional[str] = None
    job_preferences: Optional[Dict[str, Any]] = None


class LinkedInCredentials(BaseModel):
    linkedin_email: EmailStr
    linkedin_password: str