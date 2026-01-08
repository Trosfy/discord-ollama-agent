"""API response models"""
from pydantic import BaseModel
from typing import Optional
from app.domain.user import User


class UserResponse(BaseModel):
    user_id: str
    display_name: str
    role: str
    email: Optional[str]

    @classmethod
    def from_domain(cls, user: User):
        return cls(
            user_id=user.user_id,
            display_name=user.display_name,
            role=user.role,
            email=user.email
        )


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    user: UserResponse


class RefreshResponse(BaseModel):
    access_token: str
    token_type: str
