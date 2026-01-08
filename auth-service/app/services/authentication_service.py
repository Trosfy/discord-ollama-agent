"""Authentication service (business logic)"""
from typing import Optional, Dict
from datetime import datetime
import uuid

from app.interfaces.auth_provider import IAuthProvider
from app.interfaces.user_repository import IUserRepository
from app.interfaces.auth_method_repository import IAuthMethodRepository
from app.domain.user import User
from app.domain.auth_method import AuthMethod
from app.utils.jwt import create_token_pair


class AuthenticationService:
    """Handles authentication business logic (DIP - depends on interfaces)"""

    def __init__(
        self,
        auth_providers: Dict[str, IAuthProvider],
        user_repo: IUserRepository,
        auth_method_repo: IAuthMethodRepository
    ):
        self.auth_providers = auth_providers
        self.user_repo = user_repo
        self.auth_method_repo = auth_method_repo

    async def login(
        self,
        provider: str,
        identifier: str,
        credentials: str
    ) -> Optional[Dict]:
        """
        Authenticate user with any provider.

        Returns JWT token + user info if successful.
        """

        # Get auth provider (OCP - extensible)
        auth_provider = self.auth_providers.get(provider)
        if not auth_provider:
            raise ValueError(f"Unknown provider: {provider}")

        # Authenticate (LSP - all providers substitutable)
        auth_method = await auth_provider.authenticate(identifier, credentials)
        if not auth_method:
            return None

        # Get user
        user = await self.user_repo.get_by_id(auth_method.user_id)
        if not user:
            return None

        # Create JWT tokens (access + refresh)
        token_data = {
            "user_id": user.user_id,
            "display_name": user.display_name,
            "role": user.role
        }
        access_token, refresh_token = create_token_pair(token_data)

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "user": user,
            "auth_method": auth_method
        }

    async def register(
        self,
        provider: str,
        identifier: str,
        credentials: str,
        display_name: str,
        email: Optional[str] = None
    ) -> Dict:
        """
        Register new user with auth method.
        """

        # Get auth provider
        auth_provider = self.auth_providers.get(provider)
        if not auth_provider:
            raise ValueError(f"Unknown provider: {provider}")

        # Check if auth method already exists
        existing_auth = await self.auth_method_repo.get_by_provider_and_identifier(
            provider=provider,
            provider_user_id=identifier
        )
        if existing_auth:
            raise ValueError(f"Auth method already exists for {provider}:{identifier}")

        # Create user
        user = User(
            user_id=f"user_{uuid.uuid4().hex[:12]}",
            display_name=display_name,
            email=email,
            role='standard',
            user_tier='standard',
            preferences={},
            weekly_token_budget=100000,
            tokens_remaining=100000,
            tokens_used_this_week=0,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        user = await self.user_repo.create(user)

        # Create auth method
        auth_method = await auth_provider.create_auth_method(
            user_id=user.user_id,
            identifier=identifier,
            credentials=credentials
        )

        # Create JWT tokens (access + refresh)
        token_data = {
            "user_id": user.user_id,
            "display_name": user.display_name,
            "role": user.role
        }
        access_token, refresh_token = create_token_pair(token_data)

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "user": user,
            "auth_method": auth_method
        }

    async def link_auth_method(
        self,
        user_id: str,
        provider: str,
        identifier: str,
        credentials: str
    ) -> AuthMethod:
        """
        Link new auth method to existing user (account linking).
        """

        # Verify user exists
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise ValueError("User not found")

        # Check if this auth method is already linked to ANOTHER user
        existing_auth = await self.auth_method_repo.get_by_provider_and_identifier(
            provider=provider,
            provider_user_id=identifier
        )
        if existing_auth and existing_auth.user_id != user_id:
            raise ValueError(f"This {provider} account is already linked to another user")

        if existing_auth and existing_auth.user_id == user_id:
            # Already linked to this user
            return existing_auth

        # Get auth provider
        auth_provider = self.auth_providers.get(provider)
        if not auth_provider:
            raise ValueError(f"Unknown provider: {provider}")

        # Create auth method
        auth_method = await auth_provider.create_auth_method(
            user_id=user_id,
            identifier=identifier,
            credentials=credentials
        )

        return auth_method
