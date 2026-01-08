"""Health checking service for all Trollama services."""
import asyncio
import httpx
import sys
from datetime import datetime, timezone
from collections import defaultdict, deque
from typing import Dict, Optional

sys.path.insert(0, '/shared')
import logging_client

from app.services.webhook_service import WebhookService
from app.config import settings

logger = logging_client.setup_logger('admin-service')


class HealthCheckerService:
    """
    Monitors health of all Trollama services.

    Runs on configured interval, tracks consecutive failures, and sends alerts
    via Discord webhook when threshold is reached.
    """

    SERVICES = {
        'logging': {
            'url': 'http://trollama-logging:9998/health',
            'timeout': 5,
            'critical': True
        },
        'dynamodb': {
            'url': 'http://trollama-dynamodb:8000',
            'timeout': 5,
            'critical': True,
            'expected_status': 400  # DynamoDB returns 400 on root
        },
        'ollama': {
            'url': 'http://host.docker.internal:11434/api/tags',
            'timeout': 5,
            'critical': True
        },
        'fastapi': {
            'url': 'http://trollama-fastapi:8000/health',
            'timeout': 10,
            'critical': True
        },
        'discord-bot': {
            'url': 'http://trollama-discord-bot:9998/health',
            'timeout': 5,
            'critical': False  # Non-critical - checks WebSocket connection
        },
        'auth': {
            'url': 'http://trollama-auth:8002/health',
            'timeout': 5,
            'critical': True
        },
        'sglang': {
            'url': 'http://trollama-sglang:30000/health',
            'timeout': 10,
            'critical': False,  # Non-critical - only used in performance profile
            'optional': True  # May not be running
        }
    }

    def __init__(self, webhook_service: Optional[WebhookService] = None):
        """
        Initialize health checker.

        Args:
            webhook_service: Optional webhook service for alerts (creates default if None)
        """
        self.webhook_service = webhook_service or WebhookService()
        self.status_history = defaultdict(lambda: deque(maxlen=100))
        self.current_status = {}
        self.consecutive_failures = defaultdict(int)
        self.alert_threshold = settings.HEALTH_CHECK_ALERT_THRESHOLD
        self.alert_cooldown = settings.HEALTH_CHECK_ALERT_COOLDOWN_SECONDS
        self.check_interval = settings.HEALTH_CHECK_INTERVAL_SECONDS
        self.last_alert_time = {}

        self._task: Optional[asyncio.Task] = None
        self._running = False

    async def check_service(self, name: str, config: dict) -> dict:
        """
        Check health of a single service.

        Args:
            name: Service name
            config: Service configuration (url, timeout, expected_status, etc.)

        Returns:
            dict: Health check result with timestamp, healthy status, etc.
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    config['url'],
                    timeout=config['timeout']
                )

                expected = config.get('expected_status', 200)
                healthy = response.status_code == expected

                # Try to parse JSON response
                try:
                    data = response.json()
                except:
                    data = None

                result = {
                    'service': name,
                    'timestamp': datetime.now(timezone.utc),
                    'healthy': healthy,
                    'status_code': response.status_code,
                    'details': data
                }

                return result

        except httpx.TimeoutException:
            return {
                'service': name,
                'timestamp': datetime.now(timezone.utc),
                'healthy': False,
                'error': 'Timeout',
                'timeout_seconds': config['timeout']
            }
        except httpx.ConnectError as e:
            # For optional services, connection errors are expected
            if config.get('optional', False):
                return {
                    'service': name,
                    'timestamp': datetime.now(timezone.utc),
                    'healthy': None,  # None = optional service not running
                    'error': 'Service not running (optional)',
                    'skipped': True
                }
            return {
                'service': name,
                'timestamp': datetime.now(timezone.utc),
                'healthy': False,
                'error': f'Connection failed: {str(e)}'
            }
        except Exception as e:
            return {
                'service': name,
                'timestamp': datetime.now(timezone.utc),
                'healthy': False,
                'error': str(e)
            }

    async def _monitor_loop(self):
        """Main monitoring loop."""
        logger.info(
            f"Health checker started "
            f"(interval={self.check_interval}s, threshold={self.alert_threshold})"
        )

        while self._running:
            try:
                # Check all services concurrently
                tasks = [
                    self.check_service(name, config)
                    for name, config in self.SERVICES.items()
                ]
                results = await asyncio.gather(*tasks)

                # Process results
                for result in results:
                    service = result['service']
                    healthy = result['healthy']

                    # Update status (including skipped optional services)
                    self.current_status[service] = result
                    self.status_history[service].append(result)

                    # Skip consecutive failure tracking for optional services that aren't running
                    if result.get('skipped', False):
                        # Reset failure counter for stopped optional services
                        self.consecutive_failures[service] = 0
                        continue

                    # Track consecutive failures
                    if healthy:
                        if self.consecutive_failures[service] > 0:
                            logger.info(f"✅ {service} recovered")
                        self.consecutive_failures[service] = 0
                    else:
                        self.consecutive_failures[service] += 1
                        logger.warning(
                            f"❌ {service} unhealthy "
                            f"({self.consecutive_failures[service]}/{self.alert_threshold}) "
                            f"- {result.get('error', 'Unknown error')}"
                        )

                        # Trigger alert on threshold (with cooldown)
                        if self.consecutive_failures[service] == self.alert_threshold:
                            await self._send_alert(service, result)

                # Overall system health
                all_critical_healthy = all(
                    self.current_status.get(name, {}).get('healthy', False)
                    for name, config in self.SERVICES.items()
                    if config.get('critical', True) and not config.get('optional', False)
                )

                if not all_critical_healthy:
                    logger.warning("⚠️ System degraded - critical services unhealthy")

            except Exception as e:
                logger.error(f"Error in health monitoring loop: {e}", exc_info=True)

            # Sleep before next check
            await asyncio.sleep(self.check_interval)

    async def _send_alert(self, service: str, result: dict):
        """
        Send alert for service failure.

        Args:
            service: Service name
            result: Health check result
        """
        # Check cooldown
        last_alert = self.last_alert_time.get(service, 0)
        now = datetime.now(timezone.utc).timestamp()

        if now - last_alert < self.alert_cooldown:
            logger.debug(f"Skipping alert for {service} (cooldown active)")
            return

        # Determine severity
        config = self.SERVICES[service]
        severity = "critical" if config.get('critical') else "warning"

        # Send webhook
        color = 15158332 if severity == "critical" else 15105570  # Red or Orange

        await self.webhook_service.send_event(
            event_type="service_health_alert",
            data={
                "service": service,
                "message": f"{service} has failed {self.alert_threshold} consecutive health checks",
                "severity": severity,
                "error": result.get('error', 'Unknown error'),
                "status_code": result.get('status_code'),
                "consecutive_failures": self.consecutive_failures[service]
            },
            color=color
        )

        # Update cooldown
        self.last_alert_time[service] = now

        logger.info(f"🚨 Alert sent for {service} ({severity})")

    def get_health_snapshot(self) -> dict:
        """
        Get current health status snapshot for metrics collection.

        This is a lightweight method that returns just the current health status
        for all monitored services. Used by MetricsWriter to persist health data.

        Returns:
            dict: Current health status for each service
            {
                'logging': {'healthy': True, 'status_code': 200, 'timestamp': ...},
                'dynamodb': {'healthy': True, 'status_code': 400, 'timestamp': ...},
                'fastapi': {'healthy': True, 'status_code': 200, 'timestamp': ...},
                'discord-bot': {'healthy': True, 'status_code': 200, 'timestamp': ...},
                'auth': {'healthy': True, 'status_code': 200, 'timestamp': ...},
                'sglang': {'healthy': None, 'skipped': True}  # Optional service
            }
        """
        return self.current_status.copy()

    def get_current_status(self) -> dict:
        """
        Get current status of all services.

        Returns:
            dict: Status for each service with history and uptime
        """
        return {
            name: {
                'current': self.current_status.get(name),
                'history': list(self.status_history[name]),
                'uptime_last_100': self._calculate_uptime(name),
                'consecutive_failures': self.consecutive_failures[name]
            }
            for name in self.SERVICES
        }

    def _calculate_uptime(self, service: str) -> float:
        """
        Calculate uptime percentage from history.

        Args:
            service: Service name

        Returns:
            float: Uptime percentage (0-100)
        """
        history = self.status_history[service]
        if not history:
            return 0.0

        healthy_count = sum(1 for h in history if h.get('healthy'))
        return (healthy_count / len(history)) * 100

    async def start(self):
        """Start the health checker background task."""
        if self._running:
            logger.warning("Health checker already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())

    async def stop(self):
        """Stop the health checker background task."""
        if not self._running:
            return

        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        logger.info("Health checker service stopped")
