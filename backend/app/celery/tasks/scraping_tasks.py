from celery import current_task
from datetime import datetime, timedelta
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from loguru import logger

from app.celery.celery_app import celery_app
from app.core.database import SessionLocal
from app.models.user import User
from app.models.job import Job, SearchProfile
from app.linkedin.scraper import scrape_linkedin_jobs


@celery_app.task(bind=True)
def scrape_jobs_for_user(self, user_id: int, search_params: Dict[str, Any]) -> Dict[str, Any]:
    """Scrape LinkedIn jobs for a specific user"""
    try:
        logger.info(f"Starting job scraping task for user {user_id}")
        
        # Update task status
        self.update_state(
            state="PROGRESS",
            meta={"status": "Starting job scraping", "progress": 0}
        )
        
        # Run scraping
        jobs = scrape_linkedin_jobs(user_id, search_params)
        
        # Update task status
        self.update_state(
            state="PROGRESS",
            meta={"status": f"Found {len(jobs)} jobs", "progress": 100}
        )
        
        logger.info(f"Completed job scraping for user {user_id}: {len(jobs)} jobs found")
        
        return {
            "status": "completed",
            "jobs_found": len(jobs),
            "user_id": user_id,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in scraping task for user {user_id}: {e}")
        self.update_state(
            state="FAILURE",
            meta={"status": f"Error: {str(e)}", "progress": 0}
        )
        raise


@celery_app.task(bind=True)
def scheduled_job_scraping(self) -> Dict[str, Any]:
    """Scheduled task to scrape jobs for all active search profiles"""
    try:
        logger.info("Starting scheduled job scraping")
        
        db = SessionLocal()
        
        # Get all active search profiles
        active_profiles = db.query(SearchProfile).filter(
            SearchProfile.is_active == True
        ).all()
        
        results = {
            "total_profiles": len(active_profiles),
            "successful_scrapes": 0,
            "failed_scrapes": 0,
            "total_jobs_found": 0,
            "profiles_processed": []
        }
        
        for i, profile in enumerate(active_profiles):
            try:
                # Update task progress
                progress = int((i / len(active_profiles)) * 100)
                self.update_state(
                    state="PROGRESS",
                    meta={
                        "status": f"Processing profile {i+1}/{len(active_profiles)}",
                        "progress": progress
                    }
                )
                
                # Prepare search parameters
                search_params = {
                    "keywords": profile.keywords,
                    "location": profile.location or "",
                    "experience_level": profile.experience_levels,
                    "employment_type": profile.employment_types,
                    "remote": profile.include_remote,
                    "easy_apply": True,  # Focus on easy apply jobs for automation
                    "limit": 50
                }
                
                # Run scraping for this profile
                jobs = scrape_linkedin_jobs(profile.user_id, search_params)
                
                results["successful_scrapes"] += 1
                results["total_jobs_found"] += len(jobs)
                results["profiles_processed"].append({
                    "profile_id": profile.id,
                    "user_id": profile.user_id,
                    "jobs_found": len(jobs),
                    "status": "success"
                })
                
                logger.info(f"Scraped {len(jobs)} jobs for profile {profile.id}")
                
            except Exception as e:
                results["failed_scrapes"] += 1
                results["profiles_processed"].append({
                    "profile_id": profile.id,
                    "user_id": profile.user_id,
                    "jobs_found": 0,
                    "status": "failed",
                    "error": str(e)
                })
                
                logger.error(f"Error scraping for profile {profile.id}: {e}")
                continue
        
        db.close()
        
        logger.info(f"Scheduled scraping completed: {results['total_jobs_found']} total jobs found")
        
        return results
        
    except Exception as e:
        logger.error(f"Error in scheduled scraping task: {e}")
        raise


@celery_app.task(bind=True)
def scrape_jobs_by_search_profile(self, search_profile_id: int) -> Dict[str, Any]:
    """Scrape jobs for a specific search profile"""
    try:
        logger.info(f"Starting job scraping for search profile {search_profile_id}")
        
        db = SessionLocal()
        
        # Get search profile
        profile = db.query(SearchProfile).filter(
            SearchProfile.id == search_profile_id,
            SearchProfile.is_active == True
        ).first()
        
        if not profile:
            db.close()
            raise ValueError(f"Search profile {search_profile_id} not found or inactive")
        
        # Update task status
        self.update_state(
            state="PROGRESS",
            meta={"status": "Preparing search parameters", "progress": 10}
        )
        
        # Prepare search parameters
        search_params = {
            "keywords": profile.keywords,
            "location": profile.location or "",
            "experience_level": profile.experience_levels,
            "employment_type": profile.employment_types,
            "remote": profile.include_remote,
            "easy_apply": True,
            "limit": 100
        }
        
        # Update task status
        self.update_state(
            state="PROGRESS",
            meta={"status": "Scraping LinkedIn jobs", "progress": 30}
        )
        
        # Run scraping
        jobs = scrape_linkedin_jobs(profile.user_id, search_params)
        
        db.close()
        
        # Update task status
        self.update_state(
            state="PROGRESS",
            meta={"status": f"Completed: {len(jobs)} jobs found", "progress": 100}
        )
        
        logger.info(f"Completed scraping for profile {search_profile_id}: {len(jobs)} jobs found")
        
        return {
            "status": "completed",
            "search_profile_id": search_profile_id,
            "jobs_found": len(jobs),
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error scraping for search profile {search_profile_id}: {e}")
        self.update_state(
            state="FAILURE",
            meta={"status": f"Error: {str(e)}", "progress": 0}
        )
        raise


@celery_app.task(bind=True)
def cleanup_old_jobs(self, days_old: int = 30) -> Dict[str, Any]:
    """Clean up old job listings from database"""
    try:
        logger.info(f"Starting cleanup of jobs older than {days_old} days")
        
        db = SessionLocal()
        
        # Calculate cutoff date
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)
        
        # Find old jobs
        old_jobs = db.query(Job).filter(
            Job.scraped_at < cutoff_date,
            Job.is_active == False
        ).all()
        
        # Delete old jobs
        deleted_count = 0
        for job in old_jobs:
            # Check if job has any applications
            if not job.job_applications:
                db.delete(job)
                deleted_count += 1
        
        db.commit()
        db.close()
        
        logger.info(f"Cleaned up {deleted_count} old job listings")
        
        return {
            "status": "completed",
            "deleted_jobs": deleted_count,
            "cutoff_date": cutoff_date.isoformat(),
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in cleanup task: {e}")
        raise