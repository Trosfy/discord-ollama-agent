"""API request models"""
from pydantic import BaseModel
from typing import Optional


class LoginRequest(BaseModel):
    provider: str  # 'password', 'discord', etc.
    identifier: str  # username, email, discord_id
    credentials: str  # password, token, etc.


class RegisterRequest(BaseModel):
    provider: str
    identifier: str
    credentials: str
    display_name: str
    email: Optional[str] = None


class LinkAuthMethodRequest(BaseModel):
    user_id: str
    provider: str
    identifier: str
    credentials: str
