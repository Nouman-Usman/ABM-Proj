from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ...core.security import hash_password, verify_password
from ...db.base import get_db
from ...models.user import User
from ...utils.jwt_handler import get_current_user
from typing import Optional
from pydantic import BaseModel

router = APIRouter()

class PasswordUpdateRequest(BaseModel):
    old_password: str
    new_password: str

@router.put(
    "/password",
    summary="Change password",
    description="API to update user password. Requires old password verification and JWT authentication."
)
async def update_password(
    request: PasswordUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update user password. Requires:
    - Old password verification
    - JWT authentication
    """
    # Verify old password
    if not verify_password(request.old_password, current_user.password):
        raise HTTPException(
            status_code=400,
            detail="Current password is incorrect!"
        )
    
    # Hash new password
    hashed_password = hash_password(request.new_password)
    
    # Update password in database
    try:
        db_user = db.query(User).filter(User.id == current_user.id).first()
        db_user.password = hashed_password
        db.commit()
        return {"message": "Password updated successfully!"}
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="An error occurred while updating password. Please try again later."
        )

class ProfileUpdateRequest(BaseModel):
    username: Optional[str] = None
    email: Optional[str] = None
    phone_number: Optional[str] = None

@router.put(
    "/profile",
    summary="Update personal information",
    description="API to update user profile (username, email, phone_number). Username, email and phone number must be unique. Requires JWT authentication."
)
async def update_profile(
    request: ProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update user profile information. Requires JWT authentication.
    """
    try:
        db_user = db.query(User).filter(User.id == current_user.id).first()
        
        # Check for unique constraints
        if request.username and request.username != db_user.username:
            if db.query(User).filter(User.username == request.username).first():
                raise HTTPException(status_code=400, detail="Username already exists!")
            db_user.username = request.username
            
        if request.email and request.email != db_user.email:
            if db.query(User).filter(User.email == request.email).first():
                raise HTTPException(status_code=400, detail="Email already in use!")
            db_user.email = request.email
            
        if request.phone_number and request.phone_number != db_user.phone_number:
            if db.query(User).filter(User.phone_number == request.phone_number).first():
                raise HTTPException(status_code=400, detail="Phone number already in use!")
            db_user.phone_number = request.phone_number

        db.commit()
        return {"message": "Profile updated successfully!"}
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500, 
            detail="An error occurred while updating information. Please try again later."
        )