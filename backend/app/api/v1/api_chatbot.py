from . import state
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from ...schemas.ChatRequest import ChatRequest 
from ...schemas.ChatResponse import ChatResponse
from ...services.chat_services.ChatBotAgent import ChatBotAgent
from ...utils.jwt_handler import get_current_user, get_current_user_ws
from fastapi import Depends


router = APIRouter()

def get_agent():
    """Get or create ChatBotAgent lazily"""
    if not hasattr(state, 'agent') or state.agent is None:
        try:
            print("Initializing Chat Agent...")
            state.agent = ChatBotAgent()
            print("Chat Agent initialized successfully")
        except Exception as e:
            print(f"Could not initialize Chat Agent: {e}")
            import traceback
            traceback.print_exc()
            state.agent = None
    return state.agent

@router.post(
    path='/chat',
    response_model=ChatResponse,
    summary="Chat with AI Assistant",
    description="API to send message to AI Chatbot and receive response. AI can answer traffic questions, provide images and related information. Requires JWT authentication."
)
async def chat(request: ChatRequest, current_user = Depends(get_current_user)):
    agent = get_agent()
    if not agent:
        raise Exception("Chat Agent not available")
    data = await agent.get_response(request.message, id= current_user.id)
    return ChatResponse(
        message=data["message"],
        image=data["image"]
    )
@router.post(
    path='/chat_no_auth',
    response_model=ChatResponse,
    summary="Chat with AI (no authentication)",
    description="API to send message to AI Chatbot without authentication. For demo or public access. Uses default user_id = 1."
)
async def chat_no_auth(request: ChatRequest):
    agent = get_agent()
    if not agent:
        raise Exception("Chat Agent not available")
    data = await agent.get_response(request.message, id= 9999)
    return ChatResponse(
        message=data["message"],
        image=data["image"]
    )
    
@router.websocket(
    path = "/ws/chat",
    name="WebSocket Chat"
)
async def websocket_chat(
    websocket: WebSocket,
    current_user = Depends(get_current_user_ws)
):
    """
    WebSocket endpoint for AI ChatBot Agent.
    
    Args:
        current_user: Authenticated user (auto-injected by FastAPI)
    
    Flow:
    - Client sends JSON: {"message": "..."}
    - Server returns JSON: {"message": "...", "image": "..."}
    
    Authentication:
        Requires token via query params (?token=...), cookie (access_token), or header (Authorization: Bearer ...)
    """
    await websocket.accept()
    agent = get_agent()
    if not agent:
        await websocket.send_json({"message": "Chat Agent not available", "image": None})
        await websocket.close()
        return
    
    try:
        while True:
            data = await websocket.receive_json()
            user_message = data.get("message", "")
            if not user_message:
                await websocket.send_json({"message": "Please enter a message.", "image": None})
                continue

            response = await agent.get_response(user_message, id=current_user.id)
            await websocket.send_json({
                "message": response["message"],
                "image": response["image"]
            })

    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"WebSocket error: {e}")
        try:
            await websocket.send_json({
                "message": f"Error: {str(e)}",
                "image": None
            })
        except:
            pass
        await websocket.close()