"""Profile Manager - Handles circuit breaker profile switching."""
import sys
sys.path.insert(0, '/shared')

import asyncio
import httpx
from typing import Optional
import logging_client

logger = logging_client.setup_logger('fastapi')


class ProfileManager:
    """
    Manages profile fallback and recovery based on external service health.

    Responsibilities (SRP):
    - Monitor fallback state
    - Check external service health
    - Trigger profile switches
    - Coordinate with circuit breaker

    Dependencies (DIP):
    - Injected via constructor, not hard-coded
    """

    def __init__(
        self,
        sglang_endpoint: str,
        health_check_timeout: float = 2.0
    ):
        """
        Initialize ProfileManager.

        Args:
            sglang_endpoint: SGLang server endpoint for health checks
            health_check_timeout: Timeout for health check requests (seconds)
        """
        self.sglang_endpoint = sglang_endpoint
        self.health_check_timeout = health_check_timeout

        # State management
        self._fallback_active = False
        self._original_profile_name: Optional[str] = None
        self._switch_lock = asyncio.Lock()  # Prevent race conditions

        logger.info(
            f"✅ ProfileManager initialized "
            f"(sglang_endpoint={sglang_endpoint}, timeout={health_check_timeout}s, "
            f"fallback_active={self._fallback_active})"
        )

    async def on_circuit_breaker_triggered(
        self,
        model_id: str,
        crash_count: int
    ) -> None:
        """
        Callback when circuit breaker triggers for critical models.

        Switches from performance profile to conservative when CRITICAL-priority models crash.
        This is the observer pattern hook for CrashTracker.

        Args:
            model_id: Model that triggered circuit breaker
            crash_count: Number of crashes
        """
        async with self._switch_lock:
            # Import here to avoid circular dependency
            from app.config import get_active_profile, get_model_capabilities, switch_profile

            current_profile = get_active_profile()

            # Only switch if in performance profile and not already in fallback
            if current_profile.profile_name != "performance" or self._fallback_active:
                logger.debug(
                    f"Ignoring circuit breaker: already in fallback or not performance profile"
                )
                return

            # Check if crashed model is a CRITICAL model in current profile
            model_caps = get_model_capabilities(model_id)
            if not model_caps or model_caps.priority != "CRITICAL":
                logger.debug(
                    f"Ignoring circuit breaker for non-critical model: {model_id} (priority={model_caps.priority if model_caps else 'unknown'})"
                )
                return

            logger.critical(
                f"🚨 Critical model circuit breaker triggered! "
                f"Switching to conservative profile (model: {model_id}, crashes: {crash_count})"
            )

            self._original_profile_name = current_profile.profile_name
            self._fallback_active = True

            try:
                switch_profile("conservative")
                logger.info("✅ Successfully switched to conservative profile")
            except Exception as e:
                logger.error(f"❌ Profile switch failed: {e}")
                # Rollback state on failure
                self._fallback_active = False
                self._original_profile_name = None

    async def check_and_recover(self) -> None:
        """
        Check if external services are healthy and recover to original profile.

        Called before each request to check if we can recover from fallback.

        This implements the health check + recovery logic.
        """
        # DEBUG: Log entry with internal state
        logger.debug(
            f"🔍 ProfileManager.check_and_recover() called "
            f"(fallback_active={self._fallback_active}, "
            f"original_profile={self._original_profile_name})"
        )

        if not self._fallback_active or not self._original_profile_name:
            logger.debug("⏭️  Not in fallback mode, skipping recovery check")
            return  # Not in fallback mode

        logger.info(f"🔍 Checking SGLang health for recovery to {self._original_profile_name} profile...")

        # Check SGLang health
        is_healthy = await self._check_sglang_health()
        logger.info(f"🩺 SGLang health check result: {'✅ HEALTHY' if is_healthy else '❌ UNHEALTHY'}")

        if not is_healthy:
            logger.debug("SGLang still unhealthy, staying in fallback mode")
            return

        # SGLang is healthy - recover to original profile
        async with self._switch_lock:
            # Import here to avoid circular dependency
            from app.config import switch_profile

            # Double-check state (might have changed since first check)
            if not self._fallback_active:
                return

            logger.info(
                f"✅ SGLang is healthy again! "
                f"Recovering to {self._original_profile_name} profile"
            )

            try:
                switch_profile(self._original_profile_name)
                logger.info(f"✅ Successfully recovered to {self._original_profile_name} profile")

                # Clear fallback state
                self._fallback_active = False
                self._original_profile_name = None

            except Exception as e:
                logger.error(f"❌ Profile recovery failed: {e}")
                # Stay in fallback mode on error (safe default)

    async def _check_sglang_health(self) -> bool:
        """
        Check if SGLang server is healthy.

        Returns:
            True if SGLang is healthy and responsive
        """
        health_url = f"{self.sglang_endpoint}/health"
        logger.debug(f"🩺 Attempting SGLang health check: {health_url} (timeout={self.health_check_timeout}s)")

        try:
            async with httpx.AsyncClient(timeout=self.health_check_timeout) as client:
                response = await client.get(health_url)
                is_healthy = response.status_code == 200

                if is_healthy:
                    logger.debug(f"✅ SGLang health check SUCCESS: {health_url} returned {response.status_code}")
                else:
                    logger.warning(f"⚠️  SGLang health check returned non-200: {response.status_code}")

                return is_healthy

        except Exception as e:
            logger.warning(f"❌ SGLang health check failed: {health_url} - {type(e).__name__}: {e}")
            return False

    def is_in_fallback(self) -> bool:
        """Check if currently in fallback mode."""
        return self._fallback_active

    def get_original_profile(self) -> Optional[str]:
        """Get original profile name before fallback."""
        return self._original_profile_name
