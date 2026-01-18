from datetime import datetime, timedelta
from jose import jwt
from ..core.config import settings_server
from fastapi import Depends, HTTPException, status, Request, WebSocket
from fastapi.security import OAuth2PasswordBearer
from ..models.user import User
from ..db.base import get_db, get_db_for_ws
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, Union


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login")

def extract_token(source: Union[Request, WebSocket]) -> Optional[str]:
    """
    Extract token from Request or WebSocket.
    Supports: Authorization header, Cookie, Query params
    
    Args:
        source: Request or WebSocket object
        
    Returns:
        Token string if found, None otherwise
    """
    if not source:
        return None
    
    token = None
    
    # 1. Try to get from Authorization header
    auth_header = source.headers.get("authorization")
    if auth_header and auth_header.lower().startswith("bearer "):
        token = auth_header.split(" ", 1)[1]
    
    # 2. Try to get from cookie
    if not token:
        token = source.cookies.get("access_token")
    
    # 3. Try to get from query params
    if not token:
        token = source.query_params.get("token")
    
    return token

def create_access_token(data: dict):
    """ Create JWT access token from input data.

    Args:
        data (dict): Input data to create token.

    Returns:
        str: JWT access token.
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=settings_server.ACCESS_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings_server.JWT_SECRET, algorithm=settings_server.JWT_ALGORITHM)

def decode_access_token(token: str) -> dict|None:
    """Decode JWT token.

    Args:
        token (str): token to decode.

    Returns:
        dict|None: token information if valid, otherwise returns None.
    """
    try:
        payload = jwt.decode(token, settings_server.JWT_SECRET, algorithms=[settings_server.JWT_ALGORITHM])
        return payload
    except Exception:
        return None

async def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    HTTP-only dependency: authenticate via OAuth2 Bearer token in Authorization header.
    - No fallback to cookie or query params for HTTP endpoints.
    - Returns 401 if missing or token is invalid.
    """
    # Require Bearer token in Authorization header
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user = await get_user_by_token(token, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token or user does not exist.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user

# async def get_current_user(
#     request: Request,
#     db: AsyncSession = Depends(get_db)
# ) -> User:
#     """
#     HTTP dependency flexible: accept token from multiple sources.
    
#     Priority order:
#     1. Authorization header (Bearer token)
#     2. Cookie (access_token)
#     3. Query parameter (?token=...)
    
#     ⚠️ SECURITY WARNING:
#     - Query params can be logged in server/proxy logs → token leakage risk
#     - Cookies require proper CORS/SameSite configuration
#     - Authorization header is the safest method for APIs
    
#     Use when:
#     - Need to support multiple client types (browser, mobile, desktop)
#     - Frontend cannot easily set Authorization header
#     - Need backward compatibility with legacy systems
    
#     Example usage:
#     ```python
#     @router.get("/profile")
#     async def get_profile(user: User = Depends(get_current_user_flexible)):
#         return {"email": user.email, "username": user.username}
#     ```
    
#     Args:
#         request: FastAPI Request object
#         db: Database session
        
#     Returns:
#         User: Authenticated user object
        
#     Raises:
#         HTTPException: 401 if token does not exist or is invalid
#     """
#     token = extract_token(request)
    
#     if not token:
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail="Invalid or missing token. Please provide token via Authorization header, cookie, or query parameter.",
#             headers={"WWW-Authenticate": "Bearer"},
#         )
    
#     user = await get_user_by_token(token, db)
#     if not user:
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail="Invalid token or user does not exist.",
#             headers={"WWW-Authenticate": "Bearer"},
#         )
#     return user

async def get_current_user_ws(
    websocket: WebSocket,
    db: AsyncSession = Depends(get_db_for_ws)
) -> User:
    """
    WebSocket-only dependency: get token flexibly from header/cookie/query params.
    - For browser WebSocket that cannot set Authorization header.
    - Accept from multiple sources: Authorization header (Bearer), cookie access_token, query param ?token=...
    - Uses dedicated WebSocket session for better connection pool management
    - Returns 401 if missing or token is invalid.
    """
    token = extract_token(websocket)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = await get_user_by_token(token, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token or user does not exist.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user

async def get_user_by_token(token: str, db: AsyncSession) -> Optional[User]:
    """Function for WebSocket or cases requiring direct token/db transfer

    Args:
        token (str): JWT token to authenticate
        db (AsyncSession): database session

    Returns:
        Optional[User]: user corresponding to the token if valid, otherwise returns None
    """
    payload = decode_access_token(token)
    if payload is None:
        return None
    email = payload.get("sub")
    if email is None:
        return None
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar()
    return user
