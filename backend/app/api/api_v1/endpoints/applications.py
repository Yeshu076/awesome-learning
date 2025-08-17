from fastapi import APIRouter, Depends
from app.core.security import get_current_user
from app.models.user import User

router = APIRouter()

@router.get("/")
def get_applications(current_user: User = Depends(get_current_user)):
    return {"message": "Applications endpoint - to be implemented"}