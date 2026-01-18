import json
from langchain_core.tools import tool
from typing import Annotated
from ...core.config import settings_network
from ...api.v1 import state
BASE_URL = f"{settings_network.BASE_URL_API}/api/v1"

@tool
def get_roads() -> str:
    """Get list of available roads from the system.
    Returns a JSON string containing the list of road names.
    """
    if state.analyzer is None:
        return json.dumps({"error": "Analyzer has not been initialized"}, ensure_ascii=False)
    
    road_names = state.analyzer.names
    if not road_names:
        return json.dumps({"roads": [], "message": "No roads available."}, ensure_ascii=False)
    
    return json.dumps({"roads": road_names}, ensure_ascii=False)
    
@tool
def get_frame_road(road_name: Annotated[str, "Road name"]) -> str:
    """Get the bytecode URL for the current frame (image) of the road by name (road_name).
    Returns the URL of the JPEG image.
    """
    try:
        url = f"{BASE_URL}/frames_no_auth/{road_name}"
        return url
    except Exception as e:
        return f"Undefined error: {str(e)}"

@tool
def get_info_road(road_name: Annotated[str, "Road name"]) -> str:
    """Get current information (info) of the road by name (road_name).
    Returns a JSON string containing number of vehicles, speed, etc.
    """
    if state.analyzer is None:
        return json.dumps({"error": "Analyzer has not been initialized"}, ensure_ascii=False)
    
    data = state.analyzer.get_info_road(road_name)
    if not data:
        return json.dumps({"error": f"No data available for road '{road_name}'"}, ensure_ascii=False)
    
    return json.dumps(data, ensure_ascii=False)
    