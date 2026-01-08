"""User management service for admin operations."""

from typing import Dict, List, Optional
from datetime import datetime, timezone
import logging

from app.interfaces.protocols import IUserRepository, INotificationService
from app.middleware.audit_log import log_admin_action

logger = logging.getLogger(__name__)


class UserService:
    """
    Business logic for user management operations.

    Handles:
    - Granting bonus tokens
    - Banning/unbanning users
    - Viewing user stats
    - Listing all users
    - Discord webhook notifications

    Now follows Dependency Inversion Principle:
    - Depends on IUserRepository interface (not direct DynamoDB access)
    - Depends on INotificationService interface (not concrete WebhookService)
    - Can be tested with mock implementations
    - Repository handles all data persistence logic
    """

    def __init__(self, user_repository: IUserRepository, webhook: Optional[INotificationService] = None):
        """
        Initialize user service with dependencies.

        Args:
            user_repository: Repository interface for user data operations
            webhook: Optional notification service for event alerts
        """
        self.user_repository = user_repository
        self.webhook = webhook

    async def grant_tokens(
        self,
        user_id: str,
        amount: int,
        admin_user: str,
        reason: Optional[str] = None
    ) -> Dict:
        """
        Grant bonus tokens to a user.

        Args:
            user_id: User to grant tokens to
            amount: Number of tokens to grant
            admin_user: Admin performing the action
            reason: Optional reason for granting tokens

        Returns:
            dict: Operation result with new token balance
        """
        logger.info(f"Admin {admin_user} granting {amount} tokens to {user_id}")

        try:
            # Use repository to grant tokens
            success = await self.user_repository.grant_tokens(
                user_id=user_id,
                amount=amount,
                reason=reason or "Admin grant",
                admin_user=admin_user
            )

            if not success:
                raise ValueError(f"Failed to grant tokens to user {user_id}")

            # Get updated user data to return new balance
            user = await self.user_repository.get_user(user_id)
            if not user:
                raise ValueError(f"User {user_id} not found after grant")

            new_bonus = int(user.get('bonus_tokens', 0))

            # Audit log
            await log_admin_action(
                admin_user=admin_user,
                action="grant_tokens",
                parameters={
                    "user_id": user_id,
                    "amount": amount,
                    "reason": reason
                },
                result="success"
            )

            logger.info(
                f"Granted {amount} tokens to {user_id} by {admin_user}. "
                f"New bonus balance: {new_bonus}"
            )

            # Send webhook notification (only for large grants)
            if self.webhook and amount >= 10000:
                await self.webhook.send_event("tokens_granted", {
                    "user_id": user_id,
                    "amount": amount,
                    "reason": reason,
                    "admin_user": admin_user
                })

            return {
                "status": "success",
                "user_id": user_id,
                "tokens_granted": amount,
                "new_bonus_balance": new_bonus,
                "message": f"Granted {amount} tokens to {user_id}"
            }

        except ValueError as e:
            logger.warning(f"Failed to grant tokens: {e}")

            await log_admin_action(
                admin_user=admin_user,
                action="grant_tokens",
                parameters={"user_id": user_id, "amount": amount},
                result=f"failure: {str(e)}"
            )

            raise

        except Exception as e:
            logger.error(f"Failed to grant tokens: {e}")

            await log_admin_action(
                admin_user=admin_user,
                action="grant_tokens",
                parameters={"user_id": user_id, "amount": amount},
                result=f"error: {str(e)}"
            )

            raise

    async def ban_user(
        self,
        user_id: str,
        admin_user: str,
        reason: str
    ) -> Dict:
        """
        Ban a user from using the service.

        Args:
            user_id: User to ban
            admin_user: Admin performing the action
            reason: Reason for ban

        Returns:
            dict: Operation result
        """
        logger.warning(f"Admin {admin_user} banning user {user_id}: {reason}")

        try:
            # Use repository to ban user
            success = await self.user_repository.ban_user(
                user_id=user_id,
                reason=reason,
                admin_user=admin_user
            )

            if not success:
                raise ValueError(f"Failed to ban user {user_id}")

            # Audit log
            await log_admin_action(
                admin_user=admin_user,
                action="ban_user",
                parameters={"user_id": user_id, "reason": reason},
                result="success"
            )

            logger.warning(f"User {user_id} banned by {admin_user}")

            # Send webhook notification
            if self.webhook:
                await self.webhook.send_event("user_banned", {
                    "user_id": user_id,
                    "reason": reason,
                    "admin_user": admin_user
                })

            return {
                "status": "success",
                "user_id": user_id,
                "message": f"User {user_id} has been banned",
                "reason": reason
            }

        except ValueError as e:
            logger.warning(f"Failed to ban user: {e}")

            await log_admin_action(
                admin_user=admin_user,
                action="ban_user",
                parameters={"user_id": user_id, "reason": reason},
                result=f"failure: {str(e)}"
            )

            raise

        except Exception as e:
            logger.error(f"Failed to ban user: {e}")

            await log_admin_action(
                admin_user=admin_user,
                action="ban_user",
                parameters={"user_id": user_id, "reason": reason},
                result=f"error: {str(e)}"
            )

            raise

    async def unban_user(
        self,
        user_id: str,
        admin_user: str
    ) -> Dict:
        """
        Unban a user.

        Args:
            user_id: User to unban
            admin_user: Admin performing the action

        Returns:
            dict: Operation result
        """
        logger.info(f"Admin {admin_user} unbanning user {user_id}")

        try:
            # Use repository to unban user
            success = await self.user_repository.unban_user(
                user_id=user_id,
                admin_user=admin_user
            )

            if not success:
                raise ValueError(f"Failed to unban user {user_id}")

            # Audit log
            await log_admin_action(
                admin_user=admin_user,
                action="unban_user",
                parameters={"user_id": user_id},
                result="success"
            )

            logger.info(f"User {user_id} unbanned by {admin_user}")

            # Send webhook notification
            if self.webhook:
                await self.webhook.send_event("user_unbanned", {
                    "user_id": user_id,
                    "admin_user": admin_user
                })

            return {
                "status": "success",
                "user_id": user_id,
                "message": f"User {user_id} has been unbanned"
            }

        except ValueError as e:
            logger.warning(f"Failed to unban user: {e}")

            await log_admin_action(
                admin_user=admin_user,
                action="unban_user",
                parameters={"user_id": user_id},
                result=f"failure: {str(e)}"
            )

            raise

        except Exception as e:
            logger.error(f"Failed to unban user: {e}")

            await log_admin_action(
                admin_user=admin_user,
                action="unban_user",
                parameters={"user_id": user_id},
                result=f"error: {str(e)}"
            )

            raise

    async def get_user_stats(self, user_id: str) -> Dict:
        """
        Get detailed stats for a specific user.

        Args:
            user_id: User to get stats for

        Returns:
            dict: User stats including tokens, tier, preferences, ban status
        """
        try:
            # Use repository to get user data
            user = await self.user_repository.get_user(user_id)

            if not user:
                raise ValueError(f"User {user_id} not found")

            # Return comprehensive user stats
            return {
                "user_id": user_id,
                "discord_username": user.get('discord_username'),
                "user_tier": user.get('user_tier', 'free'),
                "tokens": {
                    "weekly_budget": int(user.get('weekly_token_budget', 0)),
                    "bonus_tokens": int(user.get('bonus_tokens', 0)),
                    "used_this_week": int(user.get('tokens_used_this_week', 0)),
                    "remaining": int(user.get('tokens_remaining', 0))
                },
                "preferences": {
                    "preferred_model": user.get('preferred_model'),
                    "temperature": user.get('temperature'),
                    "thinking_enabled": user.get('thinking_enabled')
                },
                "ban_status": {
                    "is_banned": user.get('is_banned', False),
                    "ban_reason": user.get('ban_reason'),
                    "banned_at": user.get('banned_at'),
                    "banned_by": user.get('banned_by')
                },
                "metadata": {
                    "created_at": user.get('created_at'),
                    "last_active": user.get('last_active'),
                    "week_start_date": user.get('week_start_date')
                }
            }

        except ValueError as e:
            logger.warning(f"Failed to get user stats: {e}")
            raise

        except Exception as e:
            logger.error(f"Failed to get user stats: {e}")
            raise

    async def list_all_users(
        self,
        limit: int = 100,
        offset: int = 0
    ) -> Dict:
        """
        List all users with pagination.

        Args:
            limit: Maximum number of users to return
            offset: Number of users to skip (for pagination)

        Returns:
            dict: List of users with pagination info
        """
        try:
            # Use repository to list users
            # Note: Repository list_users uses last_key for pagination,
            # but this method uses offset-based pagination for backwards compatibility
            result = await self.user_repository.list_users(limit=limit * 2)  # Get more to handle offset
            all_users = result.get('users', [])

            # Sort by created_at (descending)
            all_users.sort(
                key=lambda u: u.get('created_at', ''),
                reverse=True
            )

            # Apply offset-based pagination
            paginated_users = all_users[offset:offset + limit]

            # Format user data for response
            users = [
                {
                    "user_id": u['user_id'],
                    "discord_username": u.get('discord_username'),
                    "user_tier": u.get('user_tier', 'free'),
                    "tokens_remaining": int(u.get('tokens_remaining', 0)),
                    "is_banned": u.get('is_banned', False),
                    "last_active": u.get('last_active'),
                    "created_at": u.get('created_at')
                }
                for u in paginated_users
            ]

            return {
                "users": users,
                "total": len(all_users),
                "limit": limit,
                "offset": offset,
                "has_more": offset + limit < len(all_users)
            }

        except Exception as e:
            logger.error(f"Failed to list users: {e}")
            raise
