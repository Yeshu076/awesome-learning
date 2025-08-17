from celery import current_task
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple
from sqlalchemy.orm import Session
from loguru import logger

from app.celery.celery_app import celery_app
from app.core.database import SessionLocal
from app.models.user import User
from app.models.job import Job, SearchProfile
from app.models.application import JobApplication, Resume
from app.linkedin.applicator import apply_to_linkedin_job


@celery_app.task(bind=True)
def apply_to_job_task(self, user_id: int, job_id: int, resume_id: int = None, cover_letter: str = None) -> Dict[str, Any]:
    """Apply to a LinkedIn job as a background task"""
    try:
        logger.info(f"Starting job application task for user {user_id}, job {job_id}")
        
        # Update task status
        self.update_state(
            state="PROGRESS",
            meta={"status": "Initializing application process", "progress": 10}
        )
        
        # Update task status
        self.update_state(
            state="PROGRESS",
            meta={"status": "Logging into LinkedIn", "progress": 30}
        )
        
        # Apply to job
        success, result = apply_to_linkedin_job(user_id, job_id, resume_id, cover_letter)
        
        # Update task status
        self.update_state(
            state="PROGRESS",
            meta={"status": "Application completed", "progress": 100}
        )
        
        logger.info(f"Application task completed for user {user_id}, job {job_id}: {'Success' if success else 'Failed'}")
        
        return {
            "status": "completed",
            "success": success,
            "user_id": user_id,
            "job_id": job_id,
            "application_result": result,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in application task for user {user_id}, job {job_id}: {e}")
        self.update_state(
            state="FAILURE",
            meta={"status": f"Error: {str(e)}", "progress": 0}
        )
        raise


@celery_app.task(bind=True)
def process_auto_applications(self) -> Dict[str, Any]:
    """Process automatic job applications for users with auto-apply enabled"""
    try:
        logger.info("Starting automatic application processing")
        
        db = SessionLocal()
        
        # Get search profiles with auto-apply enabled
        auto_apply_profiles = db.query(SearchProfile).filter(
            SearchProfile.is_active == True,
            SearchProfile.auto_apply == True
        ).all()
        
        results = {
            "total_profiles": len(auto_apply_profiles),
            "applications_attempted": 0,
            "applications_successful": 0,
            "applications_failed": 0,
            "profiles_processed": []
        }
        
        for i, profile in enumerate(auto_apply_profiles):
            try:
                # Update task progress
                progress = int((i / len(auto_apply_profiles)) * 100)
                self.update_state(
                    state="PROGRESS",
                    meta={
                        "status": f"Processing profile {i+1}/{len(auto_apply_profiles)}",
                        "progress": progress
                    }
                )
                
                # Check daily application limit
                today = datetime.utcnow().date()
                applications_today = db.query(JobApplication).filter(
                    JobApplication.user_id == profile.user_id,
                    JobApplication.applied_at >= today,
                    JobApplication.applied_automatically == True
                ).count()
                
                max_applications = min(profile.max_applications_per_day, 50)  # Hard limit of 50 per day
                
                if applications_today >= max_applications:
                    logger.info(f"User {profile.user_id} has reached daily application limit ({applications_today}/{max_applications})")
                    results["profiles_processed"].append({
                        "profile_id": profile.id,
                        "user_id": profile.user_id,
                        "status": "skipped_limit_reached",
                        "applications_today": applications_today,
                        "max_applications": max_applications
                    })
                    continue
                
                # Find suitable jobs for this profile
                suitable_jobs = self.find_suitable_jobs_for_profile(db, profile)
                
                profile_results = {
                    "profile_id": profile.id,
                    "user_id": profile.user_id,
                    "suitable_jobs_found": len(suitable_jobs),
                    "applications_attempted": 0,
                    "applications_successful": 0,
                    "applications_failed": 0,
                    "status": "processed"
                }
                
                # Apply to jobs up to daily limit
                remaining_applications = max_applications - applications_today
                jobs_to_apply = suitable_jobs[:remaining_applications]
                
                for job in jobs_to_apply:
                    try:
                        # Get user's default resume
                        default_resume = db.query(Resume).filter(
                            Resume.user_id == profile.user_id,
                            Resume.is_default == True,
                            Resume.is_active == True
                        ).first()
                        
                        # Apply to job
                        success, application_result = apply_to_linkedin_job(
                            profile.user_id, 
                            job.id, 
                            default_resume.id if default_resume else None,
                            None  # No custom cover letter for auto-apply
                        )
                        
                        profile_results["applications_attempted"] += 1
                        results["applications_attempted"] += 1
                        
                        if success:
                            profile_results["applications_successful"] += 1
                            results["applications_successful"] += 1
                            logger.info(f"Successfully applied to job {job.id} for user {profile.user_id}")
                        else:
                            profile_results["applications_failed"] += 1
                            results["applications_failed"] += 1
                            logger.warning(f"Failed to apply to job {job.id} for user {profile.user_id}")
                        
                        # Add delay between applications to avoid rate limiting
                        import time
                        import random
                        time.sleep(random.uniform(30, 60))  # 30-60 second delay
                        
                    except Exception as e:
                        profile_results["applications_failed"] += 1
                        results["applications_failed"] += 1
                        logger.error(f"Error applying to job {job.id} for user {profile.user_id}: {e}")
                        continue
                
                results["profiles_processed"].append(profile_results)
                logger.info(f"Processed profile {profile.id}: {profile_results['applications_successful']} successful applications")
                
            except Exception as e:
                results["profiles_processed"].append({
                    "profile_id": profile.id,
                    "user_id": profile.user_id,
                    "status": "error",
                    "error": str(e)
                })
                logger.error(f"Error processing profile {profile.id}: {e}")
                continue
        
        db.close()
        
        logger.info(f"Auto-application processing completed: {results['applications_successful']}/{results['applications_attempted']} successful")
        
        return results
        
    except Exception as e:
        logger.error(f"Error in auto-application processing: {e}")
        raise
    
    def find_suitable_jobs_for_profile(self, db: Session, profile: SearchProfile) -> List[Job]:
        """Find jobs suitable for automatic application based on search profile"""
        try:
            # Base query for jobs
            query = db.query(Job).filter(
                Job.is_active == True,
                Job.easy_apply == True,  # Only easy apply jobs for automation
                Job.scraped_at >= datetime.utcnow() - timedelta(days=7)  # Recent jobs only
            )
            
            # Filter by keywords (basic text search)
            if profile.keywords:
                keywords = profile.keywords.split()
                for keyword in keywords:
                    query = query.filter(
                        Job.title.ilike(f"%{keyword}%") | 
                        Job.description.ilike(f"%{keyword}%")
                    )
            
            # Filter by location if specified
            if profile.location:
                query = query.filter(Job.location.ilike(f"%{profile.location}%"))
            
            # Filter by employment type
            if profile.employment_types:
                query = query.filter(Job.employment_type.in_(profile.employment_types))
            
            # Filter by experience level
            if profile.experience_levels:
                query = query.filter(Job.experience_level.in_(profile.experience_levels))
            
            # Filter by remote preference
            if profile.include_remote and not profile.include_onsite:
                query = query.filter(Job.is_remote == True)
            elif not profile.include_remote and profile.include_onsite:
                query = query.filter(Job.is_remote == False)
            
            # Exclude jobs already applied to
            applied_job_ids = db.query(JobApplication.job_id).filter(
                JobApplication.user_id == profile.user_id
            ).subquery()
            query = query.filter(~Job.id.in_(applied_job_ids))
            
            # Order by posted date (newest first) and limit results
            jobs = query.order_by(Job.posted_date.desc()).limit(20).all()
            
            return jobs
            
        except Exception as e:
            logger.error(f"Error finding suitable jobs for profile {profile.id}: {e}")
            return []


@celery_app.task(bind=True)
def update_application_statuses(self) -> Dict[str, Any]:
    """Update application statuses by checking LinkedIn"""
    try:
        logger.info("Starting application status update")
        
        db = SessionLocal()
        
        # Get recent applications that might have status updates
        recent_applications = db.query(JobApplication).filter(
            JobApplication.status.in_(["applied", "pending"]),
            JobApplication.applied_at >= datetime.utcnow() - timedelta(days=30)
        ).limit(100).all()  # Limit to avoid overwhelming LinkedIn
        
        results = {
            "total_applications": len(recent_applications),
            "status_updates": 0,
            "errors": 0
        }
        
        # Note: This would require additional LinkedIn scraping to check application status
        # For now, we'll just log the applications that could be checked
        for application in recent_applications:
            try:
                # Placeholder for status checking logic
                # In a full implementation, this would scrape LinkedIn to check status
                logger.info(f"Would check status for application {application.id}")
                
            except Exception as e:
                results["errors"] += 1
                logger.error(f"Error checking status for application {application.id}: {e}")
        
        db.close()
        
        logger.info(f"Application status update completed: {results['status_updates']} updates")
        
        return results
        
    except Exception as e:
        logger.error(f"Error in application status update: {e}")
        raise


@celery_app.task(bind=True)
def bulk_apply_to_jobs(self, user_id: int, job_ids: List[int], resume_id: int = None) -> Dict[str, Any]:
    """Apply to multiple jobs in bulk"""
    try:
        logger.info(f"Starting bulk application for user {user_id} to {len(job_ids)} jobs")
        
        results = {
            "total_jobs": len(job_ids),
            "successful_applications": 0,
            "failed_applications": 0,
            "applications": []
        }
        
        for i, job_id in enumerate(job_ids):
            try:
                # Update task progress
                progress = int((i / len(job_ids)) * 100)
                self.update_state(
                    state="PROGRESS",
                    meta={
                        "status": f"Applying to job {i+1}/{len(job_ids)}",
                        "progress": progress
                    }
                )
                
                # Apply to job
                success, result = apply_to_linkedin_job(user_id, job_id, resume_id)
                
                if success:
                    results["successful_applications"] += 1
                else:
                    results["failed_applications"] += 1
                
                results["applications"].append({
                    "job_id": job_id,
                    "success": success,
                    "result": result
                })
                
                # Add delay between applications
                import time
                import random
                time.sleep(random.uniform(30, 90))  # 30-90 second delay
                
            except Exception as e:
                results["failed_applications"] += 1
                results["applications"].append({
                    "job_id": job_id,
                    "success": False,
                    "error": str(e)
                })
                logger.error(f"Error applying to job {job_id}: {e}")
        
        logger.info(f"Bulk application completed: {results['successful_applications']}/{results['total_jobs']} successful")
        
        return results
        
    except Exception as e:
        logger.error(f"Error in bulk application task: {e}")
        raise