"""Password authentication provider (SRP - Single Responsibility)"""
from typing import Optional
from datetime import datetime
import uuid
from app.interfaces.auth_provider import IAuthProvider
from app.interfaces.auth_method_repository import IAuthMethodRepository
from app.domain.auth_method import AuthMethod
from app.utils.crypto import hash_password, verify_password


class PasswordAuthProvider(IAuthProvider):
    """Handles password-based authentication"""

    def __init__(self, auth_method_repo: IAuthMethodRepository):
        self.auth_method_repo = auth_method_repo

    async def authenticate(
        self,
        identifier: str,  # username
        credentials: str  # password
    ) -> Optional[AuthMethod]:
        """Authenticate with username/password"""

        # Get auth method from repository
        auth_method = await self.auth_method_repo.get_by_provider_and_identifier(
            provider='password',
            provider_user_id=identifier
        )

        if not auth_method:
            return None

        # Verify password
        password_hash = auth_method.credentials.get('password_hash')
        if not password_hash:
            return None

        if not verify_password(credentials, password_hash):
            return None

        # Update last used
        auth_method.last_used_at = datetime.utcnow()
        await self.auth_method_repo.update(auth_method)

        return auth_method

    async def create_auth_method(
        self,
        user_id: str,
        identifier: str,  # username
        credentials: str,  # plain password
        metadata: dict = None
    ) -> AuthMethod:
        """Create new password auth method"""

        # Hash password
        password_hash = hash_password(credentials)

        # Create auth method
        auth_method = AuthMethod(
            auth_method_id=f"auth_{uuid.uuid4().hex[:12]}",
            user_id=user_id,
            provider='password',
            provider_user_id=identifier,
            credentials={'password_hash': password_hash},
            metadata=metadata or {},
            is_primary=True,
            is_verified=True,
            created_at=datetime.utcnow(),
            last_used_at=None
        )

        return await self.auth_method_repo.create(auth_method)

    def get_provider_name(self) -> str:
        return 'password'
