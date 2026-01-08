"""User domain entity"""
from dataclasses import dataclass
from typing import Optional, Dict
from datetime import datetime


@dataclass
class User:
    """Core user entity (auth-method agnostic)"""
    user_id: str
    display_name: str
    role: str  # 'admin' | 'standard'
    user_tier: str  # 'admin' | 'premium' | 'standard'
    preferences: Dict
    weekly_token_budget: int
    tokens_remaining: int
    tokens_used_this_week: int
    created_at: datetime
    updated_at: datetime
    email: Optional[str] = None

    def is_admin(self) -> bool:
        return self.role == 'admin'
