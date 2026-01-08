"""AuthMethod domain entity"""
from dataclasses import dataclass
from typing import Optional, Dict
from datetime import datetime


@dataclass
class AuthMethod:
    """Authentication method for a user"""
    auth_method_id: str
    user_id: str  # FK to User
    provider: str  # 'password', 'discord', 'google'
    provider_user_id: str  # Username, Discord ID, etc.
    credentials: Dict  # Provider-specific credentials
    metadata: Dict  # Provider-specific metadata
    is_primary: bool
    is_verified: bool
    created_at: datetime
    last_used_at: Optional[datetime] = None
