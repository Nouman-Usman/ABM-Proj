"""
Chat Message Model for PostgreSQL
Lưu trữ lịch sử chat của users
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from ..db.base import Base


class ChatMessage(Base):
    """
    Model for storing chat messages
    
    Attributes:
        id: Primary key
        user_id: Foreign key to User
        message: Message content
        is_user: True if message from user, False if from AI
        images: JSON array containing image URLs (if any)
        created_at: Creation time
        extra_data: JSON field for additional information (traffic data, context, etc.)
    """
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    # Message content
    message = Column(Text, nullable=False)
    is_user = Column(Boolean, default=True, nullable=False)  # True = user, False = AI
    
    # Attached images (JSON array of URLs)
    images = Column(JSON, nullable=True)
    # Example: ["http://localhost:8000/api/v1/roads/road1/frames/latest", ...]
    
    # Additional extra data (avoid 'metadata' - reserved by SQLAlchemy)
    extra_data = Column(JSON, nullable=True)
    # Example: {"traffic_data": {...}, "intent": "traffic_query", "response_time_ms": 250}
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Relationships
    user = relationship("User", back_populates="chat_messages")

    def __repr__(self):
        return f"<ChatMessage(id={self.id}, user_id={self.user_id}, is_user={self.is_user})>"

    def to_dict(self):
        """Convert to dict for API response"""
        return {
            "id": str(self.id),
            "text": self.message,
            "user": self.is_user,
            "time": self.created_at.strftime("%H:%M:%S"),
            "image": self.images if self.images else None,
            "created_at": self.created_at.isoformat(),
        }
