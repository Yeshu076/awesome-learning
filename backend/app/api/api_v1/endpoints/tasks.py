from fastapi import APIRouter, Depends
from app.core.security import get_current_user
from app.models.user import User

router = APIRouter()

@router.get("/{task_id}")
def get_task_status(task_id: str, current_user: User = Depends(get_current_user)):
    return {"message": f"Task {task_id} status - to be implemented"}