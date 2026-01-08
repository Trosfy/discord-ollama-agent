"""Admin slash commands for Discord bot."""
import sys
sys.path.insert(0, '/shared')

import discord
from discord import app_commands
import httpx
from typing import Literal
import logging_client

from bot.config import settings
from bot.utils import has_admin_role, generate_admin_token

logger = logging_client.setup_logger('discord-bot-admin')

# Create admin command group
admin = app_commands.Group(name="admin", description="Admin commands for system management")


# Helper function to check admin role
async def check_admin(interaction: discord.Interaction) -> bool:
    """
    Check if user has admin role and respond with error if not.

    Returns:
        bool: True if user has admin role, False otherwise
    """
    has_role, _ = has_admin_role(interaction)
    if not has_role:
        await interaction.response.send_message(
            "❌ You don't have permission to use admin commands.\n"
            "Admin role is required.",
            ephemeral=True
        )
        return False
    return True


# Helper function to make API calls with admin token
async def call_admin_api(
    interaction: discord.Interaction,
    method: str,
    endpoint: str,
    json: dict = None
) -> dict:
    """
    Make authenticated API call to admin-service.

    Args:
        interaction: Discord interaction
        method: HTTP method (GET, POST, etc.)
        endpoint: API endpoint path
        json: Optional JSON body

    Returns:
        dict: Response JSON

    Raises:
        Exception: If API call fails
    """
    # Generate admin token
    has_role, role_id = has_admin_role(interaction)
    if not has_role:
        raise ValueError("User does not have admin role")

    token = generate_admin_token(str(interaction.user.id), role_id)

    # Make API call
    url = f"{settings.ADMIN_SERVICE_URL}{endpoint}"
    headers = {"Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient() as client:
        if method == "GET":
            response = await client.get(url, headers=headers, timeout=30.0)
        elif method == "POST":
            response = await client.post(url, headers=headers, json=json, timeout=30.0)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")

        response.raise_for_status()
        return response.json()


# ============================================================================
# MODEL MANAGEMENT COMMANDS
# ============================================================================

model_group = app_commands.Group(name="model", description="Model management commands", parent=admin)


@model_group.command(name="list", description="List all available models")
async def model_list(interaction: discord.Interaction):
    """List all models from profile configuration."""
    if not await check_admin(interaction):
        return

    await interaction.response.defer(ephemeral=True)

    try:
        data = await call_admin_api(interaction, "GET", "/admin/models/list")
        models = data.get("models", [])

        if not models:
            await interaction.followup.send("No models available.", ephemeral=True)
            return

        # Create embed
        embed = discord.Embed(
            title="📋 Available Models",
            description=f"Total: {len(models)} models",
            color=discord.Color.blue()
        )

        for model in models[:25]:  # Discord limit: 25 fields
            model_name = model.get("name", "unknown")
            vram_size = model.get("vram_size_gb", 0)
            priority = model.get("priority", "NORMAL")
            capabilities = ", ".join(model.get("capabilities", []))

            embed.add_field(
                name=f"**{model_name}**",
                value=f"VRAM: {vram_size}GB | Priority: {priority}\nCapabilities: {capabilities or 'N/A'}",
                inline=False
            )

        await interaction.followup.send(embed=embed, ephemeral=True)

    except Exception as e:
        logger.error(f"Failed to list models: {e}")
        await interaction.followup.send(
            f"❌ Failed to list models: {str(e)}",
            ephemeral=True
        )


@model_group.command(name="loaded", description="Show currently loaded models")
async def model_loaded(interaction: discord.Interaction):
    """Show models currently loaded in VRAM."""
    if not await check_admin(interaction):
        return

    await interaction.response.defer(ephemeral=True)

    try:
        data = await call_admin_api(interaction, "GET", "/admin/models/loaded")
        models = data.get("models", [])

        # Get VRAM status
        vram_data = await call_admin_api(interaction, "GET", "/admin/vram/status")
        vram_used = vram_data.get("usage_pct", 0)
        vram_available = vram_data.get("available_gb", 0)

        # Create embed
        embed = discord.Embed(
            title="🎯 Loaded Models",
            description=f"VRAM Usage: {vram_used:.1f}% | Available: {vram_available:.1f}GB",
            color=discord.Color.green() if vram_used < 80 else discord.Color.orange()
        )

        if not models:
            embed.add_field(name="Status", value="No models currently loaded", inline=False)
        else:
            for model in models[:25]:
                model_id = model.get("model_id", "unknown")
                vram_gb = model.get("vram_size_gb", 0)
                priority = model.get("priority", "NORMAL")
                backend = model.get("backend", "unknown")

                embed.add_field(
                    name=f"**{model_id}**",
                    value=f"VRAM: {vram_gb}GB | Priority: {priority} | Backend: {backend}",
                    inline=False
                )

        await interaction.followup.send(embed=embed, ephemeral=True)

    except Exception as e:
        logger.error(f"Failed to get loaded models: {e}")
        await interaction.followup.send(
            f"❌ Failed to get loaded models: {str(e)}",
            ephemeral=True
        )


@model_group.command(name="load", description="Load a specific model")
@app_commands.describe(
    model_name="Name of the model to load",
    priority="Model priority level (default: NORMAL)"
)
async def model_load(
    interaction: discord.Interaction,
    model_name: str,
    priority: Literal["LOW", "NORMAL", "HIGH", "CRITICAL"] = "NORMAL"
):
    """Load a model into VRAM."""
    if not await check_admin(interaction):
        return

    await interaction.response.defer(ephemeral=True)

    try:
        data = await call_admin_api(
            interaction,
            "POST",
            "/admin/models/load",
            json={"model_id": model_name, "priority": priority}
        )

        # Success message
        embed = discord.Embed(
            title="✅ Model Loaded",
            description=f"Model **{model_name}** loaded successfully",
            color=discord.Color.green()
        )
        embed.add_field(name="Priority", value=priority, inline=True)
        embed.add_field(name="Status", value=data.get("status", "success"), inline=True)

        await interaction.followup.send(embed=embed, ephemeral=True)

    except httpx.HTTPStatusError as e:
        error_detail = e.response.json().get("detail", str(e)) if e.response else str(e)
        logger.error(f"Failed to load model {model_name}: {error_detail}")
        await interaction.followup.send(
            f"❌ Failed to load model: {error_detail}",
            ephemeral=True
        )
    except Exception as e:
        logger.error(f"Failed to load model {model_name}: {e}")
        await interaction.followup.send(
            f"❌ Failed to load model: {str(e)}",
            ephemeral=True
        )


@model_group.command(name="unload", description="Unload a model from VRAM")
@app_commands.describe(model_name="Name of the model to unload")
async def model_unload(interaction: discord.Interaction, model_name: str):
    """Unload a model from VRAM."""
    if not await check_admin(interaction):
        return

    await interaction.response.defer(ephemeral=True)

    try:
        data = await call_admin_api(
            interaction,
            "POST",
            "/admin/models/unload",
            json={"model_id": model_name}
        )

        # Success message
        embed = discord.Embed(
            title="🔄 Model Unloaded",
            description=f"Model **{model_name}** unloaded successfully",
            color=discord.Color.blue()
        )

        await interaction.followup.send(embed=embed, ephemeral=True)

    except httpx.HTTPStatusError as e:
        error_detail = e.response.json().get("detail", str(e)) if e.response else str(e)
        logger.error(f"Failed to unload model {model_name}: {error_detail}")
        await interaction.followup.send(
            f"❌ Failed to unload model: {error_detail}",
            ephemeral=True
        )
    except Exception as e:
        logger.error(f"Failed to unload model {model_name}: {e}")
        await interaction.followup.send(
            f"❌ Failed to unload model: {str(e)}",
            ephemeral=True
        )


@model_group.command(name="evict", description="Emergency eviction of models by priority")
@app_commands.describe(priority="Priority level to evict (default: NORMAL)")
async def model_evict(
    interaction: discord.Interaction,
    priority: Literal["LOW", "NORMAL", "HIGH"] = "NORMAL"
):
    """Trigger emergency eviction of models."""
    if not await check_admin(interaction):
        return

    # Confirmation button view
    class ConfirmView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=30.0)
            self.value = None

        @discord.ui.button(label="Confirm Eviction", style=discord.ButtonStyle.danger)
        async def confirm(self, button_interaction: discord.Interaction, button: discord.ui.Button):
            self.value = True
            self.stop()

        @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
        async def cancel(self, button_interaction: discord.Interaction, button: discord.ui.Button):
            self.value = False
            self.stop()

    # Ask for confirmation
    view = ConfirmView()
    await interaction.response.send_message(
        f"⚠️ **Emergency Eviction**\n"
        f"This will evict models at priority **{priority}** or lower.\n"
        f"Are you sure?",
        view=view,
        ephemeral=True
    )

    await view.wait()

    if view.value is None:
        await interaction.edit_original_response(
            content="❌ Eviction cancelled (timeout)",
            view=None
        )
        return

    if not view.value:
        await interaction.edit_original_response(
            content="❌ Eviction cancelled",
            view=None
        )
        return

    # Perform eviction
    try:
        data = await call_admin_api(
            interaction,
            "POST",
            "/admin/models/evict",
            json={"priority": priority}
        )

        evicted = data.get("evicted", False)

        if evicted:
            embed = discord.Embed(
                title="🚨 Emergency Eviction",
                description=f"Model **{data.get('model_id')}** evicted",
                color=discord.Color.red()
            )
            embed.add_field(name="Freed VRAM", value=f"{data.get('size_gb', 0):.1f}GB", inline=True)
            embed.add_field(name="Priority", value=priority, inline=True)
        else:
            embed = discord.Embed(
                title="⚠️ Eviction Result",
                description="No models available for eviction at this priority level",
                color=discord.Color.orange()
            )

        await interaction.edit_original_response(content=None, embed=embed, view=None)

    except Exception as e:
        logger.error(f"Failed to evict models: {e}")
        await interaction.edit_original_response(
            content=f"❌ Failed to evict models: {str(e)}",
            view=None
        )


# ============================================================================
# VRAM MONITORING COMMANDS
# ============================================================================

vram_group = app_commands.Group(name="vram", description="VRAM monitoring commands", parent=admin)


@vram_group.command(name="status", description="Show VRAM usage status")
async def vram_status(interaction: discord.Interaction):
    """Show current VRAM usage and pressure metrics."""
    if not await check_admin(interaction):
        return

    await interaction.response.defer(ephemeral=True)

    try:
        data = await call_admin_api(interaction, "GET", "/admin/vram/status")

        used_gb = data.get("used_gb", 0)
        total_gb = data.get("total_gb", 0)
        available_gb = data.get("available_gb", 0)
        usage_pct = data.get("usage_pct", 0)
        psi_some = data.get("psi_some_avg10", 0)
        psi_full = data.get("psi_full_avg10", 0)
        healthy = data.get("healthy", False)
        loaded_models = data.get("loaded_models", 0)

        # Determine color based on health
        if healthy:
            color = discord.Color.green()
            status_icon = "✅"
        elif usage_pct > 80 or psi_some > 20:
            color = discord.Color.orange()
            status_icon = "⚠️"
        else:
            color = discord.Color.red()
            status_icon = "🚨"

        # Create embed
        embed = discord.Embed(
            title=f"{status_icon} VRAM Status",
            description=f"**{usage_pct:.1f}%** used ({used_gb:.1f}GB / {total_gb:.1f}GB)",
            color=color
        )

        # VRAM bar chart (using block characters)
        bar_length = 20
        filled = int(usage_pct / 100 * bar_length)
        bar = "█" * filled + "░" * (bar_length - filled)
        embed.add_field(name="Usage", value=f"`{bar}` {usage_pct:.1f}%", inline=False)

        embed.add_field(name="Available", value=f"{available_gb:.1f}GB", inline=True)
        embed.add_field(name="Loaded Models", value=str(loaded_models), inline=True)
        embed.add_field(name="Health", value="Healthy" if healthy else "Warning", inline=True)

        # PSI metrics
        embed.add_field(name="PSI Some (10s avg)", value=f"{psi_some:.1f}%", inline=True)
        embed.add_field(name="PSI Full (10s avg)", value=f"{psi_full:.1f}%", inline=True)

        await interaction.followup.send(embed=embed, ephemeral=True)

    except Exception as e:
        logger.error(f"Failed to get VRAM status: {e}")
        await interaction.followup.send(
            f"❌ Failed to get VRAM status: {str(e)}",
            ephemeral=True
        )


@vram_group.command(name="health", description="Show VRAM orchestrator health")
async def vram_health(interaction: discord.Interaction):
    """Show VRAM orchestrator health status."""
    if not await check_admin(interaction):
        return

    await interaction.response.defer(ephemeral=True)

    try:
        data = await call_admin_api(interaction, "GET", "/admin/vram/health")

        healthy = data.get("healthy", False)

        embed = discord.Embed(
            title="🏥 VRAM Orchestrator Health",
            color=discord.Color.green() if healthy else discord.Color.red()
        )

        embed.add_field(name="Status", value="Healthy" if healthy else "Unhealthy", inline=True)

        # Add details if available
        if "message" in data:
            embed.add_field(name="Message", value=data["message"], inline=False)

        await interaction.followup.send(embed=embed, ephemeral=True)

    except Exception as e:
        logger.error(f"Failed to get VRAM health: {e}")
        await interaction.followup.send(
            f"❌ Failed to get VRAM health: {str(e)}",
            ephemeral=True
        )


# ============================================================================
# USER MANAGEMENT COMMANDS
# ============================================================================

user_group = app_commands.Group(name="user", description="User management commands", parent=admin)


@user_group.command(name="grant", description="Grant bonus tokens to a user")
@app_commands.describe(
    user="User to grant tokens to",
    amount="Number of tokens to grant",
    reason="Reason for granting tokens"
)
async def user_grant(
    interaction: discord.Interaction,
    user: discord.User,
    amount: int,
    reason: str = "Admin grant"
):
    """Grant bonus tokens to a user."""
    if not await check_admin(interaction):
        return

    if amount <= 0:
        await interaction.response.send_message(
            "❌ Amount must be positive",
            ephemeral=True
        )
        return

    await interaction.response.defer(ephemeral=True)

    try:
        data = await call_admin_api(
            interaction,
            "POST",
            f"/admin/users/{user.id}/grant-tokens",
            json={"amount": amount, "reason": reason}
        )

        embed = discord.Embed(
            title="💰 Tokens Granted",
            description=f"Granted **{amount:,}** tokens to {user.mention}",
            color=discord.Color.blue()
        )
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.add_field(
            name="New Balance",
            value=f"{data.get('new_bonus_balance', 0):,} bonus tokens",
            inline=True
        )

        await interaction.followup.send(embed=embed, ephemeral=True)

    except Exception as e:
        logger.error(f"Failed to grant tokens: {e}")
        await interaction.followup.send(
            f"❌ Failed to grant tokens: {str(e)}",
            ephemeral=True
        )


@user_group.command(name="ban", description="Ban a user from using the bot")
@app_commands.describe(
    user="User to ban",
    reason="Reason for ban"
)
async def user_ban(
    interaction: discord.Interaction,
    user: discord.User,
    reason: str
):
    """Ban a user from using the bot."""
    if not await check_admin(interaction):
        return

    await interaction.response.defer(ephemeral=True)

    try:
        data = await call_admin_api(
            interaction,
            "POST",
            f"/admin/users/{user.id}/ban",
            json={"reason": reason}
        )

        embed = discord.Embed(
            title="🔨 User Banned",
            description=f"{user.mention} has been banned",
            color=discord.Color.red()
        )
        embed.add_field(name="Reason", value=reason, inline=False)

        await interaction.followup.send(embed=embed, ephemeral=True)

    except Exception as e:
        logger.error(f"Failed to ban user: {e}")
        await interaction.followup.send(
            f"❌ Failed to ban user: {str(e)}",
            ephemeral=True
        )


@user_group.command(name="unban", description="Unban a previously banned user")
@app_commands.describe(user_id="Discord user ID to unban")
async def user_unban(interaction: discord.Interaction, user_id: str):
    """Unban a user."""
    if not await check_admin(interaction):
        return

    await interaction.response.defer(ephemeral=True)

    try:
        data = await call_admin_api(
            interaction,
            "POST",
            f"/admin/users/{user_id}/unban"
        )

        embed = discord.Embed(
            title="✅ User Unbanned",
            description=f"User ID **{user_id}** has been unbanned",
            color=discord.Color.green()
        )

        await interaction.followup.send(embed=embed, ephemeral=True)

    except Exception as e:
        logger.error(f"Failed to unban user: {e}")
        await interaction.followup.send(
            f"❌ Failed to unban user: {str(e)}",
            ephemeral=True
        )


@user_group.command(name="info", description="Get user statistics")
@app_commands.describe(user="User to get info for")
async def user_info(interaction: discord.Interaction, user: discord.User):
    """Get detailed stats for a user."""
    if not await check_admin(interaction):
        return

    await interaction.response.defer(ephemeral=True)

    try:
        data = await call_admin_api(
            interaction,
            "GET",
            f"/admin/users/{user.id}"
        )

        embed = discord.Embed(
            title=f"📊 User Stats: {user.display_name}",
            color=discord.Color.blue()
        )

        embed.add_field(name="User ID", value=str(user.id), inline=True)
        embed.add_field(name="Bonus Tokens", value=f"{data.get('bonus_tokens', 0):,}", inline=True)
        embed.add_field(name="Banned", value="Yes" if data.get('is_banned', False) else "No", inline=True)

        if data.get('tier'):
            embed.add_field(name="Tier", value=data['tier'], inline=True)

        await interaction.followup.send(embed=embed, ephemeral=True)

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            await interaction.followup.send(
                f"❌ User not found in database",
                ephemeral=True
            )
        else:
            await interaction.followup.send(
                f"❌ Failed to get user info: {e.response.json().get('detail', str(e))}",
                ephemeral=True
            )
    except Exception as e:
        logger.error(f"Failed to get user info: {e}")
        await interaction.followup.send(
            f"❌ Failed to get user info: {str(e)}",
            ephemeral=True
        )


# ============================================================================
# SYSTEM CONTROL COMMANDS
# ============================================================================

system_group = app_commands.Group(name="system", description="System control commands", parent=admin)


@system_group.command(name="queue", description="Show queue statistics")
async def system_queue(interaction: discord.Interaction):
    """Show current queue statistics."""
    if not await check_admin(interaction):
        return

    await interaction.response.defer(ephemeral=True)

    try:
        data = await call_admin_api(interaction, "GET", "/admin/system/queue/stats")

        queue_size = data.get("queue_size", 0)
        max_size = data.get("max_size", 0)
        is_full = data.get("is_full", False)

        embed = discord.Embed(
            title="📊 Queue Statistics",
            color=discord.Color.orange() if is_full else discord.Color.green()
        )

        embed.add_field(name="Current Size", value=str(queue_size), inline=True)
        embed.add_field(name="Max Size", value=str(max_size), inline=True)
        embed.add_field(name="Status", value="FULL" if is_full else "OK", inline=True)

        # Queue bar
        if max_size > 0:
            usage_pct = (queue_size / max_size) * 100
            bar_length = 20
            filled = int(usage_pct / 100 * bar_length)
            bar = "█" * filled + "░" * (bar_length - filled)
            embed.add_field(name="Usage", value=f"`{bar}` {usage_pct:.1f}%", inline=False)

        await interaction.followup.send(embed=embed, ephemeral=True)

    except Exception as e:
        logger.error(f"Failed to get queue stats: {e}")
        await interaction.followup.send(
            f"❌ Failed to get queue stats: {str(e)}",
            ephemeral=True
        )


@system_group.command(name="maintenance", description="Toggle maintenance mode")
@app_commands.describe(
    action="Enable or disable maintenance mode",
    mode="Maintenance mode type (soft or hard)"
)
async def system_maintenance(
    interaction: discord.Interaction,
    action: Literal["enable", "disable"],
    mode: Literal["soft", "hard"] = "soft"
):
    """Enable or disable maintenance mode."""
    if not await check_admin(interaction):
        return

    await interaction.response.defer(ephemeral=True)

    try:
        enabled = action == "enable"

        data = await call_admin_api(
            interaction,
            "POST",
            "/admin/system/maintenance",
            json={"enabled": enabled, "mode": mode}
        )

        if enabled:
            embed = discord.Embed(
                title="⚠️ Maintenance Mode Enabled",
                description=f"**{mode.upper()}** maintenance mode activated",
                color=discord.Color.orange()
            )
            embed.add_field(
                name="Mode",
                value="Soft: Queue still works\nHard: All requests rejected",
                inline=False
            )
        else:
            embed = discord.Embed(
                title="✅ Maintenance Mode Disabled",
                description="System returned to normal operation",
                color=discord.Color.green()
            )

        await interaction.followup.send(embed=embed, ephemeral=True)

    except Exception as e:
        logger.error(f"Failed to set maintenance mode: {e}")
        await interaction.followup.send(
            f"❌ Failed to set maintenance mode: {str(e)}",
            ephemeral=True
        )


@system_group.command(name="health", description="Check all services health")
async def system_health(interaction: discord.Interaction):
    """Check health of all services."""
    if not await check_admin(interaction):
        return

    await interaction.response.defer(ephemeral=True)

    try:
        data = await call_admin_api(interaction, "GET", "/admin/system/health")

        overall_healthy = data.get("overall_healthy", False)
        services = data.get("services", {})

        embed = discord.Embed(
            title="🏥 System Health",
            description="Overall: " + ("✅ Healthy" if overall_healthy else "❌ Unhealthy"),
            color=discord.Color.green() if overall_healthy else discord.Color.red()
        )

        for service_name, service_data in services.items():
            healthy = service_data.get("healthy", False)
            message = service_data.get("message", "N/A")
            icon = "✅" if healthy else "❌"

            embed.add_field(
                name=f"{icon} {service_name.title()}",
                value=message,
                inline=False
            )

        await interaction.followup.send(embed=embed, ephemeral=True)

    except Exception as e:
        logger.error(f"Failed to get system health: {e}")
        await interaction.followup.send(
            f"❌ Failed to get system health: {str(e)}",
            ephemeral=True
        )


# Export the admin group
__all__ = ["admin", "model_group", "vram_group", "user_group", "system_group"]
