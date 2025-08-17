from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import desc, and_, or_

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.job import Job, SearchProfile
from app.models.application import JobApplication
from app.schemas.job import JobResponse, JobSearch, JobCreate
from app.celery.tasks.scraping_tasks import scrape_jobs_for_user
from app.celery.tasks.application_tasks import apply_to_job_task

router = APIRouter()


@router.get("/", response_model=List[JobResponse])
def get_jobs(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    skip: int = 0,
    limit: int = 50,
    keywords: Optional[str] = Query(None, description="Search keywords"),
    location: Optional[str] = Query(None, description="Job location"),
    employment_type: Optional[str] = Query(None, description="Employment type"),
    experience_level: Optional[str] = Query(None, description="Experience level"),
    remote: Optional[bool] = Query(None, description="Remote jobs only"),
    easy_apply: Optional[bool] = Query(None, description="Easy apply jobs only"),
) -> Any:
    """Get jobs with optional filtering"""
    
    query = db.query(Job).filter(Job.is_active == True)
    
    # Apply filters
    if keywords:
        query = query.filter(
            or_(
                Job.title.ilike(f"%{keywords}%"),
                Job.description.ilike(f"%{keywords}%"),
                Job.company.ilike(f"%{keywords}%")
            )
        )
    
    if location:
        query = query.filter(Job.location.ilike(f"%{location}%"))
    
    if employment_type:
        query = query.filter(Job.employment_type == employment_type)
    
    if experience_level:
        query = query.filter(Job.experience_level == experience_level)
    
    if remote is not None:
        query = query.filter(Job.is_remote == remote)
    
    if easy_apply is not None:
        query = query.filter(Job.easy_apply == easy_apply)
    
    # Order by most recent
    jobs = query.order_by(desc(Job.scraped_at)).offset(skip).limit(limit).all()
    
    return jobs


@router.get("/{job_id}", response_model=JobResponse)
def get_job(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    job_id: int,
) -> Any:
    """Get specific job by ID"""
    
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return job


@router.post("/search")
def search_jobs(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    background_tasks: BackgroundTasks,
    search_params: JobSearch,
) -> Any:
    """Trigger LinkedIn job search"""
    
    # Convert search params to dict
    search_dict = search_params.dict(exclude_unset=True)
    
    # Start background scraping task
    task = scrape_jobs_for_user.delay(current_user.id, search_dict)
    
    return {
        "message": "Job search started",
        "task_id": task.id,
        "status": "started"
    }


@router.post("/{job_id}/apply")
def apply_to_job(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    background_tasks: BackgroundTasks,
    job_id: int,
    resume_id: Optional[int] = None,
    cover_letter: Optional[str] = None,
) -> Any:
    """Apply to a specific job"""
    
    # Check if job exists
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Check if user already applied
    existing_application = db.query(JobApplication).filter(
        and_(
            JobApplication.user_id == current_user.id,
            JobApplication.job_id == job_id
        )
    ).first()
    
    if existing_application:
        raise HTTPException(status_code=400, detail="You have already applied to this job")
    
    # Start background application task
    task = apply_to_job_task.delay(current_user.id, job_id, resume_id, cover_letter)
    
    return {
        "message": "Application started",
        "task_id": task.id,
        "job_title": job.title,
        "company": job.company,
        "status": "started"
    }


@router.get("/{job_id}/similar", response_model=List[JobResponse])
def get_similar_jobs(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    job_id: int,
    limit: int = 10,
) -> Any:
    """Get similar jobs based on title and company"""
    
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Find similar jobs by title keywords and company
    title_words = job.title.split()[:3]  # Use first 3 words of title
    
    similar_jobs = db.query(Job).filter(
        and_(
            Job.id != job_id,
            Job.is_active == True,
            or_(
                Job.company == job.company,
                *[Job.title.ilike(f"%{word}%") for word in title_words if len(word) > 3]
            )
        )
    ).order_by(desc(Job.scraped_at)).limit(limit).all()
    
    return similar_jobs


@router.get("/{job_id}/application-status")
def get_application_status(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    job_id: int,
) -> Any:
    """Get application status for a specific job"""
    
    application = db.query(JobApplication).filter(
        and_(
            JobApplication.user_id == current_user.id,
            JobApplication.job_id == job_id
        )
    ).first()
    
    if not application:
        return {"status": "not_applied", "applied": False}
    
    return {
        "status": application.status,
        "applied": True,
        "applied_at": application.applied_at,
        "application_id": application.id,
        "applied_automatically": application.applied_automatically
    }