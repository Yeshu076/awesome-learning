from fastapi import APIRouter

from app.api.api_v1.endpoints import auth, users, jobs, applications, search_profiles, resumes, tasks

api_router = APIRouter()

# Include all endpoint routers
api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
api_router.include_router(applications.router, prefix="/applications", tags=["applications"])
api_router.include_router(search_profiles.router, prefix="/search-profiles", tags=["search-profiles"])
api_router.include_router(resumes.router, prefix="/resumes", tags=["resumes"])
api_router.include_router(tasks.router, prefix="/tasks", tags=["tasks"])