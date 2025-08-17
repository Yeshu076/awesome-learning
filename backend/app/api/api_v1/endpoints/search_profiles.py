from fastapi import APIRouter, Depends
from app.core.security import get_current_user
from app.models.user import User

router = APIRouter()

@router.get("/")
def get_search_profiles(current_user: User = Depends(get_current_user)):
    return {"message": "Search profiles endpoint - to be implemented"}