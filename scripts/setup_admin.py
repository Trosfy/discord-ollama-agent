"""Setup admin user for Trollama Web UI (SOLID Architecture)

This creates a web-only admin user using the new unified user model.
"""
import asyncio
import sys
sys.path.insert(0, 'auth-service')

from datetime import datetime
import uuid

from app.domain.user import User
from app.repositories.user_repository import DynamoDBUserRepository
from app.repositories.auth_method_repository import DynamoDBAuthMethodRepository
from app.providers.password_provider import PasswordAuthProvider


async def setup_admin():
    """Create admin user with password auth method"""

    print("=== Trollama Admin Setup (SOLID Architecture) ===")
    print("This creates a web-only admin account with the unified user model\n")

    username = input("Enter username (for web login): ")
    password = input("Enter password: ")
    display_name = input("Enter display name: ")
    email = input("Enter email (optional, press Enter to skip): ").strip() or None

    try:
        # Initialize repositories
        user_repo = DynamoDBUserRepository()
        auth_method_repo = DynamoDBAuthMethodRepository()
        password_provider = PasswordAuthProvider(auth_method_repo)

        # Check if username already exists
        print(f"\nChecking if username '{username}' is available...")
        existing_auth = await auth_method_repo.get_by_provider_and_identifier(
            provider='password',
            provider_user_id=username
        )

        if existing_auth:
            print(f"❌ Username '{username}' is already taken!")
            return

        # Create user (profile)
        user_id = f"user_{uuid.uuid4().hex[:12]}"
        print(f"\nCreating user profile with ID: {user_id}")

        user = User(
            user_id=user_id,
            display_name=display_name,
            email=email,
            role='admin',
            user_tier='admin',
            preferences={},
            weekly_token_budget=1000000,
            tokens_remaining=1000000,
            tokens_used_this_week=0,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )

        user = await user_repo.create(user)
        print(f"✅ User profile created")

        # Create password auth method
        print(f"Creating password authentication method...")
        auth_method = await password_provider.create_auth_method(
            user_id=user.user_id,
            identifier=username,
            credentials=password
        )
        print(f"✅ Password auth method created")

        print(f"\n{'='*50}")
        print(f"✅ Admin user setup complete!")
        print(f"{'='*50}")
        print(f"   User ID: {user.user_id}")
        print(f"   Username: {username}")
        print(f"   Display Name: {display_name}")
        print(f"   Email: {email or 'Not provided'}")
        print(f"   Role: admin")
        print(f"   Auth Method ID: {auth_method.auth_method_id}")
        print(f"\nYou can now login to Streamlit with:")
        print(f"   Username: {username}")
        print(f"   Password: ********")

    except Exception as e:
        print(f"\n❌ Error during setup: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(setup_admin())
