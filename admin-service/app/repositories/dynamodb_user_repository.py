"""
DynamoDB User Repository

Implementation of IUserRepository using DynamoDB for persistence.
Follows Repository pattern and Dependency Inversion Principle.
"""

import boto3
from typing import Dict, Optional, List
from datetime import datetime, timezone
import logging

from app.config import settings

logger = logging.getLogger(__name__)


class DynamoDBUserRepository:
    """
    DynamoDB implementation of user repository.

    Implements IUserRepository protocol for user data persistence.
    Uses DynamoDB as the underlying storage mechanism.
    """

    def __init__(self):
        """Initialize DynamoDB user repository."""
        self.table_name = settings.USERS_TABLE_NAME
        self.dynamodb = boto3.resource(
            'dynamodb',
            endpoint_url=settings.DYNAMODB_ENDPOINT,
            region_name=settings.AWS_REGION
        )
        self.table = self.dynamodb.Table(self.table_name)

    async def get_user(self, user_id: str) -> Optional[Dict]:
        """
        Get user by ID.

        Args:
            user_id: User ID to retrieve

        Returns:
            dict: User data or None if not found

        Example:
            user = await repo.get_user("12345")
            # {"user_id": "12345", "banned": False, ...}
        """
        try:
            response = self.table.get_item(Key={"user_id": user_id})
            return response.get("Item")
        except Exception as e:
            logger.error(f"Failed to get user {user_id}: {e}")
            return None

    async def create_user(self, user_id: str, user_data: Dict) -> bool:
        """
        Create new user.

        Args:
            user_id: User ID
            user_data: User data dictionary

        Returns:
            bool: True if created successfully

        Example:
            await repo.create_user("12345", {
                "username": "alice",
                "created_at": "2024-01-01T00:00:00Z"
            })
        """
        try:
            item = {
                "user_id": user_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
                **user_data
            }
            self.table.put_item(Item=item)
            logger.info(f"Created user: {user_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to create user {user_id}: {e}")
            return False

    async def update_user(self, user_id: str, updates: Dict) -> bool:
        """
        Update user data.

        Args:
            user_id: User ID to update
            updates: Dictionary of fields to update

        Returns:
            bool: True if updated successfully

        Example:
            await repo.update_user("12345", {"token_balance": 5000})
        """
        try:
            # Build update expression
            update_expr = "SET " + ", ".join(f"#{k} = :{k}" for k in updates.keys())
            expr_attr_names = {f"#{k}": k for k in updates.keys()}
            expr_attr_values = {f":{k}": v for k, v in updates.items()}

            # Add last_updated timestamp
            update_expr += ", #last_updated = :last_updated"
            expr_attr_names["#last_updated"] = "last_updated"
            expr_attr_values[":last_updated"] = datetime.now(timezone.utc).isoformat()

            self.table.update_item(
                Key={"user_id": user_id},
                UpdateExpression=update_expr,
                ExpressionAttributeNames=expr_attr_names,
                ExpressionAttributeValues=expr_attr_values
            )
            logger.info(f"Updated user: {user_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to update user {user_id}: {e}")
            return False

    async def delete_user(self, user_id: str) -> bool:
        """
        Delete user.

        Args:
            user_id: User ID to delete

        Returns:
            bool: True if deleted successfully

        Example:
            await repo.delete_user("12345")
        """
        try:
            self.table.delete_item(Key={"user_id": user_id})
            logger.info(f"Deleted user: {user_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete user {user_id}: {e}")
            return False

    async def ban_user(self, user_id: str, reason: str, admin_user: str) -> bool:
        """
        Ban a user.

        Args:
            user_id: User ID to ban
            reason: Reason for ban
            admin_user: Admin who performed the ban

        Returns:
            bool: True if banned successfully

        Example:
            await repo.ban_user("12345", "Abuse", "admin_user_id")
        """
        try:
            self.table.update_item(
                Key={"user_id": user_id},
                UpdateExpression=(
                    "SET banned = :banned, ban_reason = :reason, "
                    "banned_by = :admin, banned_at = :timestamp"
                ),
                ExpressionAttributeValues={
                    ":banned": True,
                    ":reason": reason,
                    ":admin": admin_user,
                    ":timestamp": datetime.now(timezone.utc).isoformat()
                }
            )
            logger.warning(f"User {user_id} banned by {admin_user}: {reason}")
            return True
        except Exception as e:
            logger.error(f"Failed to ban user {user_id}: {e}")
            return False

    async def unban_user(self, user_id: str, admin_user: str) -> bool:
        """
        Unban a user.

        Args:
            user_id: User ID to unban
            admin_user: Admin who performed the unban

        Returns:
            bool: True if unbanned successfully

        Example:
            await repo.unban_user("12345", "admin_user_id")
        """
        try:
            self.table.update_item(
                Key={"user_id": user_id},
                UpdateExpression=(
                    "SET banned = :banned, unbanned_by = :admin, "
                    "unbanned_at = :timestamp "
                    "REMOVE ban_reason, banned_by, banned_at"
                ),
                ExpressionAttributeValues={
                    ":banned": False,
                    ":admin": admin_user,
                    ":timestamp": datetime.now(timezone.utc).isoformat()
                }
            )
            logger.info(f"User {user_id} unbanned by {admin_user}")
            return True
        except Exception as e:
            logger.error(f"Failed to unban user {user_id}: {e}")
            return False

    async def grant_tokens(
        self,
        user_id: str,
        amount: int,
        reason: str,
        admin_user: str
    ) -> bool:
        """
        Grant bonus tokens to user.

        Args:
            user_id: User ID
            amount: Number of tokens to grant
            reason: Reason for grant
            admin_user: Admin who granted tokens

        Returns:
            bool: True if granted successfully

        Example:
            await repo.grant_tokens("12345", 10000, "Contest winner", "admin_id")
        """
        try:
            self.table.update_item(
                Key={"user_id": user_id},
                UpdateExpression=(
                    "ADD token_balance :amount "
                    "SET last_token_grant = :grant_info"
                ),
                ExpressionAttributeValues={
                    ":amount": amount,
                    ":grant_info": {
                        "amount": amount,
                        "reason": reason,
                        "granted_by": admin_user,
                        "granted_at": datetime.now(timezone.utc).isoformat()
                    }
                }
            )
            logger.info(
                f"Granted {amount} tokens to user {user_id} by {admin_user}: {reason}"
            )
            return True
        except Exception as e:
            logger.error(f"Failed to grant tokens to user {user_id}: {e}")
            return False

    async def list_users(
        self,
        limit: int = 100,
        last_key: Optional[str] = None
    ) -> Dict:
        """
        List users with pagination.

        Args:
            limit: Maximum number of users to return
            last_key: Last evaluated key for pagination

        Returns:
            dict: {
                "users": List of user dictionaries,
                "last_key": Last evaluated key for next page (or None)
            }

        Example:
            result = await repo.list_users(limit=50)
            users = result["users"]
            next_key = result["last_key"]
        """
        try:
            scan_kwargs = {"Limit": limit}

            if last_key:
                scan_kwargs["ExclusiveStartKey"] = {"user_id": last_key}

            response = self.table.scan(**scan_kwargs)

            users = response.get("Items", [])
            last_evaluated_key = response.get("LastEvaluatedKey")

            return {
                "users": users,
                "last_key": last_evaluated_key.get("user_id") if last_evaluated_key else None
            }
        except Exception as e:
            logger.error(f"Failed to list users: {e}")
            return {"users": [], "last_key": None}
