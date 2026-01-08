"""Setup admin user for Trollama Web UI - with graceful error handling"""
import asyncio
from datetime import datetime
import uuid
import sys
import os
from dotenv import load_dotenv

from app.domain.user import User
from app.repositories.user_repository import DynamoDBUserRepository
from app.repositories.auth_method_repository import DynamoDBAuthMethodRepository
from app.providers.password_provider import PasswordAuthProvider
import init_dynamodb


async def setup_admin(username: str, password: str, display_name: str, email: str = None):
    """Create admin user with password auth method"""

    # Initialize DynamoDB tables first
    print("Initializing DynamoDB tables...")
    tables_created = await init_dynamodb.initialize_all_tables()
    if tables_created:
        print(f"Created tables: {', '.join(tables_created)}")
    else:
        print("All tables already exist")
    print()

    user_repo = DynamoDBUserRepository()
    auth_method_repo = DynamoDBAuthMethodRepository()
    password_provider = PasswordAuthProvider(auth_method_repo)

    try:
        # Check if username already exists
        existing_auth = await auth_method_repo.get_by_provider_and_identifier(
            provider="password",
            provider_user_id=username
        )

        if existing_auth:
            print(f"✅ Username '{username}' already exists with user_id: {existing_auth.user_id}")
            print(f"   Skipping creation - admin user is already set up.")
            return existing_auth.user_id

        # Create user
        user = User(
            user_id=f"user_{uuid.uuid4().hex[:12]}",
            display_name=display_name,
            email=email,
            role="admin",
            user_tier="admin",
            preferences={},
            weekly_token_budget=1000000,
            tokens_remaining=1000000,
            tokens_used_this_week=0,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        user = await user_repo.create(user)

        # Create password auth method
        auth_method = await password_provider.create_auth_method(
            user_id=user.user_id,
            identifier=username,
            credentials=password
        )

        print(f"\n{'='*50}")
        print(f"✅ Admin user setup complete!")
        print(f"{'='*50}")
        print(f"   User ID: {user.user_id}")
        print(f"   Username: {username}")
        print(f"   Display Name: {display_name}")
        print(f"   Email: {email or 'Not provided'}")
        print(f"   Role: {user.role}")
        print(f"\nYou can now login with:")
        print(f"   Username: {username}")
        print(f"   Password: ********")

        return user.user_id

    except Exception as e:
        print(f"\n❌ Error during setup: {e}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    print("=== Trollama Admin Setup ===\n")

    if len(sys.argv) == 5:
        # Non-interactive mode with command line args
        username = sys.argv[1]
        password = sys.argv[2]
        display_name = sys.argv[3]
        email = sys.argv[4] if sys.argv[4] else None
    elif os.path.exists('.env.admin'):
        # Load from .env.admin file
        print("Loading credentials from .env.admin file...")
        load_dotenv('.env.admin')
        username = os.getenv('ADMIN_USERNAME', 'admin')
        password = os.getenv('ADMIN_PASSWORD', 'admin123')
        display_name = os.getenv('ADMIN_DISPLAY_NAME', 'Admin')
        email = os.getenv('ADMIN_EMAIL') or None
        print(f"Username: {username}")
        print(f"Display Name: {display_name}")
        print(f"Email: {email or 'Not provided'}\n")
    else:
        # Interactive mode
        username = input("Enter username (for web login): ")
        password = input("Enter password: ")
        display_name = input("Enter display name: ")
        email = input("Enter email (optional, press Enter to skip): ").strip() or None

    user_id = asyncio.run(setup_admin(username, password, display_name, email))
    if user_id:
        print(f"\n✅ Setup successful!")
    else:
        print(f"\n✅ Admin user already exists - no changes made")
