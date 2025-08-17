from fastapi import APIRouter, Depends
from app.core.security import get_current_user
from app.models.user import User

router = APIRouter()

@router.get("/me")
def get_current_user_info(current_user: User = Depends(get_current_user)):
    return current_user