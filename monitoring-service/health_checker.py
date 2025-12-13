"""Health checking logic for all services."""
import aiohttp
import asyncio
from datetime import datetime
from collections import defaultdict, deque
import sys
sys.path.insert(0, '/shared')

import logging_client

logger = logging_client.setup_logger('monitoring-service')


class HealthChecker:
    """Monitors health of all services."""

    SERVICES = {
        'logging-service': {
            'url': 'http://logging-service:9998/health',
            'timeout': 5,
            'critical': True
        },
        'dynamodb': {
            'url': 'http://dynamodb-local:8000',
            'timeout': 5,
            'critical': True,
            'expected_status': 400  # DynamoDB returns 400 on root
        },
        'fastapi': {
            'url': 'http://fastapi-service:8000/health',
            'timeout': 10,
            'critical': True
        },
        'discord-bot': {
            'url': 'http://discord-bot:9998/health',
            'timeout': 5,
            'critical': False  # Non-critical - checks WebSocket connection
        }
    }

    def __init__(self, database, alert_manager):
        self.db = database
        self.alert_manager = alert_manager
        self.status_history = defaultdict(lambda: deque(maxlen=100))
        self.current_status = {}
        self.consecutive_failures = defaultdict(int)
        self.alert_threshold = 3

    async def check_service(self, name: str, config: dict) -> dict:
        """Check health of a single service."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    config['url'],
                    timeout=aiohttp.ClientTimeout(total=config['timeout'])
                ) as resp:
                    expected = config.get('expected_status', 200)
                    healthy = resp.status == expected

                    # Try to parse JSON response
                    try:
                        data = await resp.json()
                    except:
                        data = None

                    result = {
                        'service': name,
                        'timestamp': datetime.utcnow(),
                        'healthy': healthy,
                        'status_code': resp.status,
                        'response_time_ms': None,
                        'details': data
                    }

                    return result

        except asyncio.TimeoutError:
            return {
                'service': name,
                'timestamp': datetime.utcnow(),
                'healthy': False,
                'error': 'Timeout',
                'timeout_seconds': config['timeout']
            }
        except Exception as e:
            return {
                'service': name,
                'timestamp': datetime.utcnow(),
                'healthy': False,
                'error': str(e)
            }

    async def monitor_loop(self):
        """Main monitoring loop."""
        logger.info("Health monitoring loop started")

        while True:
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

                    # Update status
                    self.current_status[service] = result
                    self.status_history[service].append(result)

                    # Store in database
                    self.db.add_health_check(result)

                    # Track consecutive failures
                    if healthy:
                        if self.consecutive_failures[service] > 0:
                            logger.info(f"✅ {service} recovered")
                        self.consecutive_failures[service] = 0
                    else:
                        self.consecutive_failures[service] += 1
                        logger.warning(f"❌ {service} unhealthy ({self.consecutive_failures[service]}/{self.alert_threshold})")

                        # Trigger alert on threshold
                        if self.consecutive_failures[service] == self.alert_threshold:
                            config = self.SERVICES[service]
                            await self.alert_manager.send_alert(
                                service=service,
                                message=f"{service} has failed {self.alert_threshold} consecutive health checks",
                                severity="critical" if config.get('critical') else "warning",
                                details=result
                            )

                # Overall system health
                all_critical_healthy = all(
                    self.current_status.get(name, {}).get('healthy', False)
                    for name, config in self.SERVICES.items()
                    if config.get('critical', True)
                )

                if not all_critical_healthy:
                    logger.warning("⚠️ System degraded - critical services unhealthy")

            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")

            # Sleep before next check
            await asyncio.sleep(30)

    def get_current_status(self) -> dict:
        """Get current status of all services."""
        return {
            name: {
                'current': self.current_status.get(name),
                'history': list(self.status_history[name]),
                'uptime_24h': self.calculate_uptime(name, hours=24),
                'consecutive_failures': self.consecutive_failures[name]
            }
            for name in self.SERVICES
        }

    def calculate_uptime(self, service: str, hours: int = 24) -> float:
        """Calculate uptime percentage."""
        history = self.status_history[service]
        if not history:
            return 0.0

        healthy_count = sum(1 for h in history if h['healthy'])
        return (healthy_count / len(history)) * 100
