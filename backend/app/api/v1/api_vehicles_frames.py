from fastapi import APIRouter
from fastapi.responses import JSONResponse
from . import state
import asyncio
from ...services.road_services.AnalyzeOnRoadForMultiProcessing import AnalyzeOnRoadForMultiprocessing
from fastapi.responses import Response
from fastapi import WebSocket, WebSocketDisconnect
from ...utils.jwt_handler import get_current_user, get_current_user_ws
from fastapi import Depends
from ...utils.transport_utils import enrich_info_with_thresholds

router = APIRouter()

@router.on_event("startup")
def start_up():
    if state.analyzer is None:
        state.analyzer = AnalyzeOnRoadForMultiprocessing()
        state.analyzer.run_multiprocessing()

@router.get(
    path='/roads_name',
    summary="Get road name list",
    description="API returns list of road names being monitored in the system. This endpoint DOES NOT require JWT authentication."
)
async def get_road_names():
    """
    API returns list of road names (NO JWT authentication required).
    This endpoint is public so frontend can load road list before user login.
    """
    return JSONResponse(content={"road_names": state.analyzer.names})

@router.websocket(
    "/ws/frames/{road_name}",
    name="WebSocket returns road image frames with authentication via header, cookie, query params",
    )
async def websocket_frames(
    websocket: WebSocket, 
    road_name: str,
    current_user = Depends(get_current_user_ws)
):
    """
    WebSocket endpoint to stream video frames of road in real-time.
    
    Args:
        road_name: Name of road to view
        current_user: Authenticated user (auto-injected by FastAPI)
        
    Authentication:
        Requires token via query params (?token=...), cookie (access_token), or header (Authorization: Bearer ...)
    """
    await websocket.accept()
    
    try:
        while True:
            frame_bytes = await asyncio.to_thread(state.analyzer.get_frame_road, road_name)
            await websocket.send_bytes(frame_bytes)
            await asyncio.sleep(1/30)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(e)
        await websocket.close()
        
@router.websocket(
    "/ws/info/{road_name}",
    name="WebSocket returns road vehicle information with authentication via header, cookie, query params",
)
async def websocket_info(
    websocket: WebSocket, 
    road_name: str,
    current_user = Depends(get_current_user_ws)
):
    """
    WebSocket endpoint to receive vehicle information of road in real-time.
    
    Args:
        road_name: Name of road to view information
        current_user: Authenticated user (auto-injected by FastAPI)
        
    Authentication:
        Requires token via query params (?token=...), cookie (access_token), or header (Authorization: Bearer ...)
    
    Returns:
        JSON data containing vehicle information, updated every 5 seconds
    """
    await websocket.accept()
    
    try:
        while True:
            data = await asyncio.to_thread(state.analyzer.get_info_road, road_name)
            # Enrich with per-road thresholds classification when possible
            try:
                enriched = enrich_info_with_thresholds(data, road_name)
            except Exception:
                enriched = data

            await websocket.send_json(enriched)
            await asyncio.sleep(1/50)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        await websocket.send_json({"detail": f"Internal error: {str(e)}"})
        await websocket.close()

@router.get(
    path='/info/{road_name}',
    summary="Get vehicle information on road",
    description="API returns vehicle information of road (number of vehicles, average speed, etc.). This endpoint DOES NOT require JWT authentication."
)
async def get_info_road(road_name: str):
    """
    API returns vehicle info for the road (no JWT authentication).
    """
    data = await asyncio.to_thread(state.analyzer.get_info_road, road_name)
    if data is None:
        return JSONResponse(content={
            "Error: Data error, check road_services"
            }, status_code=500)
    # Enrich with per-road thresholds classification when possible
    try:
        enriched = enrich_info_with_thresholds(data, road_name)
    except Exception:
        enriched = data

    return JSONResponse(content=enriched)

@router.get(
    path='/frames/{road_name}',
    summary="Get road image frame (authenticated)",
    description="API returns current road image frame (JPEG). Requires JWT authentication via Authorization header, cookie, or query parameter (?token=...)."
)
async def get_frame_road(road_name: str, current_user=Depends(get_current_user)):
    """
    Get current road image frame (requires authentication).
    
    Args:
        road_name: Name of road
        current_user: Authenticated user (auto-injected by FastAPI)
    
    Authentication:
        Token can be sent via: OAUTH2
    
    Returns:
        Response: Image JPEG of the current frame
    """
    frame_bytes = await asyncio.to_thread(state.analyzer.get_frame_road, road_name)
    if frame_bytes is None:
        return JSONResponse(
            content={"error": "Error: Data error, check core"},
            status_code=500
        )
    return Response(content=frame_bytes, media_type="image/jpeg")


@router.get(
    path='/frames_no_auth/{road_name}',
    summary="Get image frame (no authentication)",
    description="API returns current road image frame (JPEG). This endpoint DOES NOT require JWT authentication - for demo or public use."
)   
async def get_frame_road_no_auth(road_name: str):
    frame_bytes = await asyncio.to_thread(state.analyzer.get_frame_road, road_name)
    if frame_bytes is None:
        return JSONResponse(
            content={"error": "Error: Data error, check core"},
            status_code=500
        )
    return Response(content=frame_bytes, media_type="image/jpeg")
