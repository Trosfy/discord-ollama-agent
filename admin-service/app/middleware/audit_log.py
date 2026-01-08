"""Audit logging middleware for admin actions."""
from datetime import datetime
from typing import Dict
import logging_client

logger = logging_client.setup_logger('admin-audit')


async def log_admin_action(
    admin_user: str,
    action: str,
    parameters: Dict,
    result: str,
    auth_type: str = "jwt"
):
    """
    Log admin action to audit trail.

    In production, this would write to DynamoDB audit_logs table.
    For now, we log to the application logger.

    Args:
        admin_user: User ID performing the action
        action: Action performed (e.g., "model_load", "user_ban")
        parameters: Action parameters
        result: Action result ("success", "failure", error message)
        auth_type: Authentication type used ("jwt" or "discord")
    """
    audit_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "admin_user": admin_user,
        "action": action,
        "parameters": parameters,
        "result": result,
        "auth_type": auth_type
    }

    logger.info(f"📋 AUDIT: {admin_user} performed {action} → {result}")
    logger.debug(f"Audit details: {audit_entry}")

    # TODO: Write to DynamoDB admin_audit_logs table
    # table = dynamodb.Table(settings.ADMIN_AUDIT_LOG_TABLE)
    # await table.put_item(Item=audit_entry)
