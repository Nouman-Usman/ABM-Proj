import os
import sys
import signal
from fastapi import FastAPI
from .api import v1
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import RedirectResponse
from .db.base import create_tables
from .core.config import settings_network

os.environ["OPENCV_VIDEOIO_PRIORITY_MSMF"] = "0"
os.environ["OPENCV_VIDEOIO_PRIORITY_DSHOW"] = "1"

os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"


app = FastAPI(
    title="Smart Transportation System API",
    description="""
    Real-time Traffic Monitoring & AI Assistant
    
    API provides:
    - Real-time video streaming and traffic analysis
    - AI Chatbot to assist with traffic information
    - Analytics and metrics about vehicle flow
    - User authentication and management
    - Admin tools and system monitoring
    
    """,
    version="1.0.0",
    docs_url="/docs",  
    redoc_url="/redoc", 
    contact={
        "name": "Lê Việt Anh",
        "email": "levietanhtrump@gmail.com",
    },
    
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def signal_handler(signum, frame):
    """
    Signal handler for graceful server shutdown.

    Handles interrupt signals (SIGINT, SIGTERM) by performing cleanup operations
    before terminating the application.

    Args:
        signum (int): The signal number that triggered the handler.
        frame (FrameType): The current stack frame at the time the signal was received.

    Returns:
        None

    Raises:
        SystemExit: Exits the process with status code 0 after cleanup.

    Note:
        This handler ensures that the analyzer's processes are properly cleaned up
        before the server shuts down to prevent resource leaks or orphaned processes.
    """
    if v1.state.analyzer:
        v1.state.analyzer.cleanup_processes()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


@app.on_event("startup")
async def startup_event():
    """Create database tables on startup"""
    print("Creating database tables...")
    try:
        await create_tables()
        print("Database tables created successfully.")
    except Exception as e:
        print(f"Database table creation error (non-fatal): {e}")
        print("Server will continue without database - some features may not work.")
        # Don't raise - allow server to start without DB for development

@app.on_event("shutdown")
def shutdown():
    print("Shutting down...")
    if v1.state.analyzer:
        v1.state.analyzer.cleanup_processes()

@app.get(
    path='/',
    tags=["Root"],
    summary="Redirect to Frontend",
    description="Redirect user to Frontend page"
)
def direct_home():
    return RedirectResponse(url= settings_network.URL_FRONTEND)

app.include_router(
    router= v1.api_auth.router, 
    prefix="/api/v1", 
    tags=["Authentication"],
)
app.include_router(
    router= v1.api_user.router, 
    prefix="/api/v1/users", 
    tags=["User Management"],
)
app.include_router(
    router= v1.api_vehicles_frames.router, 
    prefix="/api/v1", 
    tags=["Traffic Monitoring"],
)
app.include_router(
    router= v1.api_chatbot.router, 
    prefix="/api/v1", 
    tags=["AI Chatbot"],
)
app.include_router(
    router= v1.chat_history.router,
    prefix="/api/v1/chat",
    tags=["Chat History"],
)
app.include_router(
    router= v1.api_admin.router,
    prefix="/api/v1", 
    tags=["Admin Tools"],
)
