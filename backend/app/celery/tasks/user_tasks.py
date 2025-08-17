from celery import current_task
from datetime import datetime, timedelta
from typing import Dict, Any
from sqlalchemy.orm import Session
from loguru import logger

from app.celery.celery_app import celery_app
from app.core.database import SessionLocal
from app.models.user import User
from app.models.application import LinkedInSession, Resume
from app.utils.file_utils import parse_resume_file


@celery_app.task(bind=True)
def cleanup_old_sessions(self) -> Dict[str, Any]:
    """Clean up old LinkedIn sessions"""
    try:
        logger.info("Starting LinkedIn session cleanup")
        
        db = SessionLocal()
        
        # Calculate cutoff date (sessions older than 24 hours)
        cutoff_date = datetime.utcnow() - timedelta(hours=24)
        
        # Find old or inactive sessions
        old_sessions = db.query(LinkedInSession).filter(
            (LinkedInSession.last_activity < cutoff_date) |
            (LinkedInSession.expires_at < datetime.utcnow()) |
            (LinkedInSession.is_active == False)
        ).all()
        
        deleted_count = 0
        for session in old_sessions:
            db.delete(session)
            deleted_count += 1
        
        db.commit()
        db.close()
        
        logger.info(f"Cleaned up {deleted_count} old LinkedIn sessions")
        
        return {
            "status": "completed",
            "deleted_sessions": deleted_count,
            "cutoff_date": cutoff_date.isoformat(),
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in session cleanup task: {e}")
        raise


@celery_app.task(bind=True)
def process_resume_upload(self, resume_id: int) -> Dict[str, Any]:
    """Process uploaded resume file and extract information"""
    try:
        logger.info(f"Starting resume processing for resume {resume_id}")
        
        db = SessionLocal()
        
        # Get resume record
        resume = db.query(Resume).filter(Resume.id == resume_id).first()
        if not resume:
            db.close()
            raise ValueError(f"Resume {resume_id} not found")
        
        # Update task status
        self.update_state(
            state="PROGRESS",
            meta={"status": "Parsing resume file", "progress": 30}
        )
        
        # Parse resume file
        try:
            parsed_data = parse_resume_file(resume.file_path, resume.file_type)
            
            # Update resume with parsed data
            resume.parsed_text = parsed_data.get("text", "")
            resume.skills = parsed_data.get("skills", [])
            resume.experience = parsed_data.get("experience", [])
            resume.education = parsed_data.get("education", [])
            
            db.commit()
            
            # Update task status
            self.update_state(
                state="PROGRESS",
                meta={"status": "Resume processing completed", "progress": 100}
            )
            
            logger.info(f"Successfully processed resume {resume_id}")
            
            db.close()
            
            return {
                "status": "completed",
                "resume_id": resume_id,
                "parsed_data": parsed_data,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            # Update resume with error status
            resume.parsed_text = f"Error parsing resume: {str(e)}"
            db.commit()
            db.close()
            
            logger.error(f"Error parsing resume {resume_id}: {e}")
            raise
        
    except Exception as e:
        logger.error(f"Error in resume processing task for resume {resume_id}: {e}")
        self.update_state(
            state="FAILURE",
            meta={"status": f"Error: {str(e)}", "progress": 0}
        )
        raise


@celery_app.task(bind=True)
def update_user_statistics(self, user_id: int) -> Dict[str, Any]:
    """Update user statistics and metrics"""
    try:
        logger.info(f"Updating statistics for user {user_id}")
        
        db = SessionLocal()
        
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            db.close()
            raise ValueError(f"User {user_id} not found")
        
        # Calculate statistics
        from app.models.application import JobApplication
        from app.models.job import Job
        
        # Application statistics
        total_applications = db.query(JobApplication).filter(
            JobApplication.user_id == user_id
        ).count()
        
        successful_applications = db.query(JobApplication).filter(
            JobApplication.user_id == user_id,
            JobApplication.status == "applied"
        ).count()
        
        # Recent activity (last 30 days)
        recent_date = datetime.utcnow() - timedelta(days=30)
        recent_applications = db.query(JobApplication).filter(
            JobApplication.user_id == user_id,
            JobApplication.applied_at >= recent_date
        ).count()
        
        # Success rate
        success_rate = (successful_applications / total_applications * 100) if total_applications > 0 else 0
        
        statistics = {
            "total_applications": total_applications,
            "successful_applications": successful_applications,
            "recent_applications": recent_applications,
            "success_rate": round(success_rate, 2),
            "last_updated": datetime.utcnow().isoformat()
        }
        
        # Store statistics (you could add a UserStatistics model for this)
        # For now, we'll just return the calculated statistics
        
        db.close()
        
        logger.info(f"Updated statistics for user {user_id}")
        
        return {
            "status": "completed",
            "user_id": user_id,
            "statistics": statistics,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error updating statistics for user {user_id}: {e}")
        raise


@celery_app.task(bind=True)
def send_user_notifications(self, user_id: int, notification_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Send notifications to users about their applications"""
    try:
        logger.info(f"Sending {notification_type} notification to user {user_id}")
        
        db = SessionLocal()
        
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            db.close()
            raise ValueError(f"User {user_id} not found")
        
        # Notification logic would go here
        # This could integrate with email services, push notifications, etc.
        
        notification_sent = True  # Placeholder
        
        db.close()
        
        logger.info(f"Sent {notification_type} notification to user {user_id}")
        
        return {
            "status": "completed",
            "user_id": user_id,
            "notification_type": notification_type,
            "sent": notification_sent,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error sending notification to user {user_id}: {e}")
        raise


@celery_app.task(bind=True)
def cleanup_user_data(self, user_id: int, data_type: str = "all") -> Dict[str, Any]:
    """Clean up user data (for GDPR compliance, user deletion, etc.)"""
    try:
        logger.info(f"Starting data cleanup for user {user_id}, type: {data_type}")
        
        db = SessionLocal()
        
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            db.close()
            raise ValueError(f"User {user_id} not found")
        
        cleanup_results = {
            "user_id": user_id,
            "data_type": data_type,
            "items_cleaned": {}
        }
        
        if data_type in ["all", "sessions"]:
            # Clean up LinkedIn sessions
            sessions_deleted = db.query(LinkedInSession).filter(
                LinkedInSession.user_id == user_id
            ).delete()
            cleanup_results["items_cleaned"]["sessions"] = sessions_deleted
        
        if data_type in ["all", "old_applications"]:
            # Clean up old applications (older than 1 year)
            old_date = datetime.utcnow() - timedelta(days=365)
            from app.models.application import JobApplication
            
            old_applications = db.query(JobApplication).filter(
                JobApplication.user_id == user_id,
                JobApplication.applied_at < old_date
            ).delete()
            cleanup_results["items_cleaned"]["old_applications"] = old_applications
        
        db.commit()
        db.close()
        
        logger.info(f"Completed data cleanup for user {user_id}")
        
        return {
            "status": "completed",
            "cleanup_results": cleanup_results,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in data cleanup for user {user_id}: {e}")
        raise