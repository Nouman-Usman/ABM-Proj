"""
Chat History API Endpoints
Lưu và lấy lịch sử chat của user
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import delete
from typing import List, Optional
from datetime import datetime

from ...utils.jwt_handler import get_current_user
from ...models.user import User
from ...models.chat_message import ChatMessage
from ...schemas.ChatMessage import (
    ChatMessageCreate,
    ChatMessageResponse,
    ChatMessageListResponse,
    ChatHistoryQuery,
)
from ...db.base import get_db

router = APIRouter()


@router.post(
    "/messages",
    response_model=ChatMessageResponse,
    status_code=201,
    summary="Save chat message",
    description="API to save a new chat message to database. Supports saving both user messages and AI responses with images and metadata. Requires JWT authentication."
)
async def create_chat_message(
    message_data: ChatMessageCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Save a new chat message
    
    - **message**: Message content
    - **is_user**: True if user message, False if AI response
    - **images**: Array of image URLs attached to message (optional)
    - **extra_data**: Additional information such as traffic data, intent, etc. (optional)
    """
    new_message = ChatMessage(
        user_id=current_user.id,
        message=message_data.message,
        is_user=message_data.is_user,
        images=message_data.images,
        extra_data=message_data.extra_data,
    )
    
    db.add(new_message)
    await db.commit()
    await db.refresh(new_message)
    
    return new_message


@router.get(
    "/messages",
    response_model=List[ChatMessageListResponse],
    summary="Get chat history",
    description="API to get current user's chat history with pagination and time-based filtering. Returns list of messages from old to new order. Requires JWT authentication."
)
async def get_chat_history(
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    since: Optional[datetime] = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get current user's chat history
    
    - **limit**: Maximum number of messages (default: 100, max: 1000)
    - **offset**: Skip how many initial messages (pagination)
    - **since**: Only get messages after this timestamp (ISO format)
    
    Returns list of messages in time order (old → new)
    """
    query = select(ChatMessage).where(ChatMessage.user_id == current_user.id)
    
    # Filter by timestamp if provided
    if since:
        query = query.where(ChatMessage.created_at > since)
    
    # Order by created_at ascending (oldest first)
    query = query.order_by(ChatMessage.created_at.asc()).offset(offset).limit(limit)
    
    result = await db.execute(query)
    messages = result.scalars().all()
    
    # Convert to frontend format
    return [
        ChatMessageListResponse(
            id=str(msg.id),
            text=msg.message,
            user=msg.is_user,
            time=msg.created_at.strftime("%H:%M:%S"),
            image=msg.images,
            created_at=msg.created_at.isoformat(),
        )
        for msg in messages
    ]


@router.delete(
    "/messages",
    status_code=204,
    summary="Clear entire chat history",
    description="API to delete all chat messages of the current user. Cannot be undone after deletion. Requires JWT authentication."
)
async def clear_chat_history(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Clear entire chat history of current user
    """
    await db.execute(
        delete(ChatMessage).where(ChatMessage.user_id == current_user.id)
    )
    await db.commit()
    
    return None


@router.delete(
    "/messages/{message_id}",
    status_code=204,
    summary="Delete specific message",
    description="API to delete a chat message by ID. User can only delete their own messages. Requires JWT authentication."
)
async def delete_chat_message(
    message_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Delete a specific message
    
    User can only delete their own messages
    """
    query = select(ChatMessage).where(
        ChatMessage.id == message_id,
        ChatMessage.user_id == current_user.id,
    )
    result = await db.execute(query)
    message = result.scalar_one_or_none()
    
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    
    await db.delete(message)
    await db.commit()
    
    return None


@router.get(
    "/messages/count",
    summary="Count number of messages",
    description="API returns total number of chat messages for current user. Requires JWT authentication."
)
async def get_message_count(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Count total messages for user
    """
    from sqlalchemy import func
    
    query = select(func.count(ChatMessage.id)).where(
        ChatMessage.user_id == current_user.id
    )
    result = await db.execute(query)
    count = result.scalar()
    
    return {"count": count}
