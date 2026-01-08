"""User storage implementation for preferences and token tracking."""
import aioboto3
from datetime import datetime, timezone
from typing import Optional, Dict
from app.config import settings


class UserStorage:
    """
    Manages user data in DynamoDB (preferences + token tracking).

    Single Responsibility: User data management
    Implements: IUserStorage, ITokenTrackingStorage
    """

    def __init__(self):
        self.session = aioboto3.Session()
        self._resource_config = {
            'endpoint_url': settings.DYNAMODB_ENDPOINT,
            'region_name': settings.DYNAMODB_REGION,
            'aws_access_key_id': settings.DYNAMODB_ACCESS_KEY,
            'aws_secret_access_key': settings.DYNAMODB_SECRET_KEY
        }

    async def get_user_preferences(self, user_id: str) -> Optional[Dict]:
        """
        Get user preferences including model, temperature, thinking_enabled.

        Returns:
            Dict with keys: preferred_model, temperature, thinking_enabled, base_prompt
            None if user doesn't exist
        """
        async with self.session.resource('dynamodb', **self._resource_config) as dynamodb:
            table = await dynamodb.Table('users')
            response = await table.get_item(Key={'user_id': user_id})
            user = response.get('Item')

            if not user:
                return None

            # Extract only preference-related fields
            return {
                'preferred_model': user.get('preferred_model'),
                'temperature': user.get('temperature'),
                'thinking_enabled': user.get('thinking_enabled'),  # None, True, or False
                'base_prompt': user.get('base_prompt'),
                'user_tier': user.get('user_tier'),
                'discord_username': user.get('discord_username'),
                'auto_summarize_threshold': user.get('auto_summarize_threshold'),
                'notify_on_summarization': user.get('notify_on_summarization', True)
            }

    async def create_user(
        self,
        user_id: str,
        discord_username: str,
        user_tier: str = 'free'
    ) -> None:
        """Create a new user with default settings."""
        weekly_budget = (
            settings.ADMIN_TIER_WEEKLY_BUDGET
            if user_tier == 'admin'
            else settings.FREE_TIER_WEEKLY_BUDGET
        )

        async with self.session.resource('dynamodb', **self._resource_config) as dynamodb:
            table = await dynamodb.Table('users')
            await table.put_item(Item={
                'user_id': user_id,
                'discord_username': discord_username,
                'user_tier': user_tier,

                # User Preferences (defaults to system settings)
                'preferred_model': None,  # None = use router
                'temperature': None,  # None = use DEFAULT_TEMPERATURE (0.2)
                'thinking_enabled': None,  # None = auto (route-based)
                'base_prompt': None,
                'auto_summarize_threshold': settings.DEFAULT_SUMMARIZATION_THRESHOLD,
                'notify_on_summarization': True,

                # Token Tracking
                'weekly_token_budget': weekly_budget,
                'bonus_tokens': 0,
                'tokens_used_this_week': 0,
                'tokens_remaining': weekly_budget,
                'week_start_date': self._get_week_start(),

                # Metadata
                'created_at': datetime.now(timezone.utc).isoformat(),
                'last_active': datetime.now(timezone.utc).isoformat()
            })

    async def update_temperature(
        self,
        user_id: str,
        temperature: Optional[float]
    ) -> None:
        """
        Update user's preferred temperature.

        Args:
            temperature: None for system default, or float value
        """
        async with self.session.resource('dynamodb', **self._resource_config) as dynamodb:
            table = await dynamodb.Table('users')

            # Store as string for DynamoDB Decimal compatibility
            temp_value = str(temperature) if temperature is not None else None

            await table.update_item(
                Key={'user_id': user_id},
                UpdateExpression='SET temperature = :temp, last_active = :now',
                ExpressionAttributeValues={
                    ':temp': temp_value,
                    ':now': datetime.now(timezone.utc).isoformat()
                }
            )

    async def update_thinking(
        self,
        user_id: str,
        enabled: Optional[bool]
    ) -> None:
        """
        Update user's thinking mode preference.

        Args:
            enabled: None for auto (route-based), True to force on, False to force off
        """
        async with self.session.resource('dynamodb', **self._resource_config) as dynamodb:
            table = await dynamodb.Table('users')
            await table.update_item(
                Key={'user_id': user_id},
                UpdateExpression='SET thinking_enabled = :enabled, last_active = :now',
                ExpressionAttributeValues={
                    ':enabled': enabled,
                    ':now': datetime.now(timezone.utc).isoformat()
                }
            )

    async def update_model(
        self,
        user_id: str,
        model: Optional[str]
    ) -> None:
        """
        Update user's preferred model.

        Args:
            model: Model name, 'trollama' for router, or None for default
        """
        async with self.session.resource('dynamodb', **self._resource_config) as dynamodb:
            table = await dynamodb.Table('users')
            await table.update_item(
                Key={'user_id': user_id},
                UpdateExpression='SET preferred_model = :model, last_active = :now',
                ExpressionAttributeValues={
                    ':model': model,
                    ':now': datetime.now(timezone.utc).isoformat()
                }
            )

    async def reset_preferences(self, user_id: str) -> None:
        """
        Reset all user preferences to system defaults.

        Resets:
        - temperature → None (use system default)
        - thinking_enabled → None (auto-detect)
        - preferred_model → None (use router)
        - base_prompt → None (no custom prompt)
        """
        async with self.session.resource('dynamodb', **self._resource_config) as dynamodb:
            table = await dynamodb.Table('users')
            await table.update_item(
                Key={'user_id': user_id},
                UpdateExpression='SET temperature = :null_val, '
                               'thinking_enabled = :null_val, '
                               'preferred_model = :null_val, '
                               'base_prompt = :null_val, '
                               'last_active = :now',
                ExpressionAttributeValues={
                    ':null_val': None,
                    ':now': datetime.now(timezone.utc).isoformat()
                }
            )

    # ============================================================================
    # Token Tracking Methods (ITokenTrackingStorage)
    # ============================================================================

    async def get_user_tokens(self, user_id: str) -> Optional[Dict]:
        """
        Get user's token budget and usage.

        Returns:
            Dict with keys: weekly_token_budget, tokens_used_this_week,
                           tokens_remaining, bonus_tokens
            None if user doesn't exist
        """
        async with self.session.resource('dynamodb', **self._resource_config) as dynamodb:
            table = await dynamodb.Table('users')
            response = await table.get_item(Key={'user_id': user_id})
            user = response.get('Item')

            if not user:
                return None

            # Return only token-related fields
            return {
                'weekly_token_budget': int(user.get('weekly_token_budget', 0)),
                'tokens_used_this_week': int(user.get('tokens_used_this_week', 0)),
                'tokens_remaining': int(user.get('tokens_remaining', 0)),
                'bonus_tokens': int(user.get('bonus_tokens', 0))
            }

    async def update_user_tokens(self, user_id: str, tokens_used: int) -> None:
        """Update user's token usage."""
        tokens = await self.get_user_tokens(user_id)
        if not tokens:
            return

        new_used = tokens['tokens_used_this_week'] + tokens_used
        new_remaining = (
            tokens['weekly_token_budget'] +
            tokens['bonus_tokens'] -
            new_used
        )

        async with self.session.resource('dynamodb', **self._resource_config) as dynamodb:
            table = await dynamodb.Table('users')
            await table.update_item(
                Key={'user_id': user_id},
                UpdateExpression='SET tokens_used_this_week = :used, '
                               'tokens_remaining = :remaining, '
                               'last_active = :now',
                ExpressionAttributeValues={
                    ':used': new_used,
                    ':remaining': max(0, new_remaining),
                    ':now': datetime.now(timezone.utc).isoformat()
                }
            )

    async def grant_bonus_tokens(self, user_id: str, amount: int) -> None:
        """Grant bonus tokens to a user."""
        async with self.session.resource('dynamodb', **self._resource_config) as dynamodb:
            table = await dynamodb.Table('users')
            await table.update_item(
                Key={'user_id': user_id},
                UpdateExpression='SET bonus_tokens = bonus_tokens + :amount',
                ExpressionAttributeValues={':amount': amount}
            )

    async def reset_weekly_tokens(self) -> None:
        """Reset weekly token counters for all users."""
        async with self.session.resource('dynamodb', **self._resource_config) as dynamodb:
            table = await dynamodb.Table('users')

            # Scan all users
            response = await table.scan()
            users = response.get('Items', [])

            # Update each user's weekly tokens
            for user in users:
                user_id = user['user_id']
                weekly_budget = int(user.get('weekly_token_budget', 0))

                await table.update_item(
                    Key={'user_id': user_id},
                    UpdateExpression='SET tokens_used_this_week = :zero, '
                                   'tokens_remaining = :budget, '
                                   'week_start_date = :week_start',
                    ExpressionAttributeValues={
                        ':zero': 0,
                        ':budget': weekly_budget + int(user.get('bonus_tokens', 0)),
                        ':week_start': self._get_week_start()
                    }
                )

    def _get_week_start(self) -> str:
        """Get Monday of current week (for token tracking initialization)."""
        from datetime import timedelta
        today = datetime.now(timezone.utc).date()
        monday = today - timedelta(days=today.weekday())
        return monday.isoformat()
