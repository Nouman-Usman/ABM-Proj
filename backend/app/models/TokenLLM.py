from sqlalchemy import Column, ForeignKey, Integer
from ..db.base import Base


class TokenLLM(Base):
    __tablename__ = "token_llm"
    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True, index=True)
    token = Column(Integer, nullable=False, default=5000)
