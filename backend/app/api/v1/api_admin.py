import asyncio
from fastapi import APIRouter, Depends, HTTPException, WebSocketDisconnect, status, WebSocket
from ...utils.jwt_handler import get_current_user, get_current_user_ws
from ...models.user import User
from ...utils.system_metrics import get_system_metrics


router = APIRouter(prefix="/admin")


@router.get(
    path= "/resources",
    summary="Get system resource information",
    description="API returns system metrics (CPU, RAM, Disk, Network). Only admins (role_id = 0) have access."
)
async def get_resources(current_user: User = Depends(get_current_user)):
    """Return basic system metrics. Admin only (role_id = 0)."""
    if current_user.role_id != 0:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chỉ admin mới được phép truy cập tài nguyên hệ thống.",
        )
    return get_system_metrics()

@router.websocket(
    path= "/ws/resources",
    name="WebSocket system notification for admin"
)
async def websocket_resources(websocket: WebSocket, current_user: User = Depends(get_current_user_ws)):
    """
    WebSocket endpoint to send system resource information in real-time to admin.
    
    Args:
        current_user: Authenticated user (auto-injected by FastAPI)
        
    Authentication:
        Requires JWT token in Authorization header (Bearer ...)
    """
    if current_user.role_id != 0:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins are allowed to access system resources.",
        )
        
    await websocket.accept()
    
    try:
        while True:
            metrics = get_system_metrics()
            await websocket.send_json(metrics)
            await asyncio.sleep(2) 
    except WebSocketDisconnect:
        pass