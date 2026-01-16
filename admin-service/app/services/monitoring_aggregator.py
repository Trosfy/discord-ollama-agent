"""
Monitoring Aggregator Service

Aggregates monitoring data from multiple sources:
- VRAM stats from fastapi-service
- Service health checks (DynamoDB, Ollama, SGLang, FastAPI)
- Queue stats from fastapi-service
- PSI metrics from host system
"""

import asyncio
import httpx
import logging
import subprocess
from datetime import datetime
from typing import Dict, Optional
import os

from app.config import settings

logger = logging.getLogger(__name__)


class MonitoringAggregator:
    """Aggregates monitoring data from multiple sources for SSE stream."""

    def __init__(self):
        self.http_client = httpx.AsyncClient(timeout=5.0)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.http_client.aclose()

    async def get_monitoring_snapshot(self) -> dict:
        """
        Get current monitoring data from all sources.

        Returns aggregated data for:
        - VRAM metrics
        - Service health
        - Queue size
        - PSI metrics
        - Maintenance mode
        """
        try:
            # Fetch all data in parallel for performance
            vram_data, health_data, queue_data, psi_data = await asyncio.gather(
                self.fetch_vram_stats(),
                self.fetch_service_health(),
                self.fetch_queue_stats(),
                self.fetch_psi_metrics(),
                return_exceptions=True
            )

            # Handle potential errors from parallel tasks
            if isinstance(vram_data, Exception):
                logger.error(f"VRAM fetch failed: {vram_data}")
                vram_data = self._get_empty_vram()

            if isinstance(health_data, Exception):
                logger.error(f"Health check failed: {health_data}")
                health_data = self._get_empty_health()

            if isinstance(queue_data, Exception):
                logger.error(f"Queue fetch failed: {queue_data}")
                queue_data = {"size": 0}

            if isinstance(psi_data, Exception):
                logger.error(f"PSI fetch failed: {psi_data}")
                psi_data = {"cpu": 0, "memory": 0, "io": 0}

            return {
                "timestamp": datetime.utcnow().isoformat(),
                "vram": vram_data,
                "services": health_data,
                "queue_size": queue_data.get("size", 0),
                "psi": psi_data,
                "maintenance_mode": False,  # TODO: Fetch from settings
            }

        except Exception as e:
            logger.error(f"Error getting monitoring snapshot: {e}", exc_info=True)
            return self._get_empty_snapshot()

    async def fetch_vram_stats(self) -> dict:
        """
        Fetch system memory stats from host using free -h.

        Returns dict with:
        - total_gb: float
        - used_gb: float
        - available_gb: float
        - usage_percentage: float
        """
        try:
            # Execute free -m on host to get memory in MB
            result = subprocess.run(
                ["free", "-m"],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                # Parse second line (Mem:)
                mem_line = lines[1].split()
                total_mb = float(mem_line[1])
                used_mb = float(mem_line[2])
                available_mb = float(mem_line[6])  # Available column

                total_gb = total_mb / 1024.0
                used_gb = used_mb / 1024.0
                available_gb = available_mb / 1024.0
                usage_pct = (used_gb / total_gb * 100.0) if total_gb > 0 else 0.0

                return {
                    "total_gb": total_gb,
                    "used_gb": used_gb,
                    "available_gb": available_gb,
                    "usage_percentage": usage_pct,
                }
            else:
                logger.warning(f"free command failed: {result.stderr}")
                return self._get_empty_vram()
        except Exception as e:
            logger.warning(f"Failed to fetch memory stats: {e}")
            return self._get_empty_vram()

    async def fetch_service_health(self) -> dict:
        """
        Check health of all services.

        Returns dict with:
        - dynamodb: "healthy" | "unhealthy"
        - ollama: "healthy" | "unhealthy"
        - sglang: "healthy" | "unhealthy" | "stopped"
        - fastapi: "healthy" | "unhealthy"
        - auth: "healthy" | "unhealthy"
        - discord-bot: "healthy" | "unhealthy"
        - logging: "healthy" | "unhealthy"
        """
        # Check all services in parallel
        dynamodb, ollama, sglang, fastapi, auth, discord_bot, logging_svc = await asyncio.gather(
            self.check_dynamodb(),
            self.check_ollama(),
            self.check_sglang(),
            self.check_fastapi(),
            self.check_auth(),
            self.check_discord_bot(),
            self.check_logging(),
            return_exceptions=True
        )

        return {
            "dynamodb": "healthy" if dynamodb is True else "unhealthy",
            "ollama": "healthy" if ollama is True else "unhealthy",
            "sglang": "healthy" if sglang is True else ("stopped" if isinstance(sglang, Exception) else "unhealthy"),
            "fastapi": "healthy" if fastapi is True else "unhealthy",
            "auth": "healthy" if auth is True else "unhealthy",
            "discord-bot": "healthy" if discord_bot is True else "unhealthy",
            "logging": "healthy" if logging_svc is True else "unhealthy",
        }

    async def check_dynamodb(self) -> bool:
        """Check DynamoDB connectivity."""
        try:
            # TODO: Import boto3 and check actual connection
            # For now, assume healthy
            return True
        except Exception as e:
            logger.warning(f"DynamoDB check failed: {e}")
            return False

    async def check_ollama(self) -> bool:
        """Check Ollama service."""
        try:
            response = await self.http_client.get("http://host.docker.internal:11434/api/tags")
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"Ollama check failed: {e}")
            return False

    async def check_sglang(self) -> bool:
        """Check SGLang service."""
        try:
            response = await self.http_client.get("http://trollama-sglang:30000/health")
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"SGLang check failed: {e}")
            return False

    async def check_auth(self) -> bool:
        """Check auth service."""
        try:
            response = await self.http_client.get("http://trollama-auth:8002/health")
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"Auth check failed: {e}")
            return False

    async def check_discord_bot(self) -> bool:
        """Check Discord bot service."""
        try:
            response = await self.http_client.get("http://trollama-discord-bot:9998/health")
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"Discord bot check failed: {e}")
            return False

    async def check_logging(self) -> bool:
        """Check logging service."""
        try:
            response = await self.http_client.get("http://trollama-logging:9998/health")
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"Logging check failed: {e}")
            return False

    async def check_troise_ai(self) -> bool:
        """Check TROISE AI service."""
        try:
            response = await self.http_client.get(f"{settings.TROISE_AI_URL}/health")
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"TROISE AI check failed: {e}")
            return False

    async def fetch_queue_stats(self) -> dict:
        """
        Fetch queue statistics from TROISE AI.

        Returns dict with:
        - size: int
        """
        try:
            response = await self.http_client.get(
                f"{settings.TROISE_AI_URL}/health"
            )
            response.raise_for_status()
            health_data = response.json()
            return {"size": health_data.get("queue_size", 0)}
        except Exception as e:
            logger.warning(f"Failed to fetch queue stats: {e}")
            return {"size": 0}

    async def fetch_psi_metrics(self) -> dict:
        """
        Read PSI metrics from host system.

        Requires host /proc mount at /host/proc/pressure/

        Returns dict with:
        - cpu: float (avg10 some pressure)
        - memory: float (avg10 some pressure)
        - io: float (avg10 some pressure)
        """
        try:
            cpu = self.read_psi_file("/host/proc/pressure/cpu")
            memory = self.read_psi_file("/host/proc/pressure/memory")
            io = self.read_psi_file("/host/proc/pressure/io")

            return {
                "cpu": cpu,
                "memory": memory,
                "io": io,
            }
        except Exception as e:
            logger.warning(f"Failed to fetch PSI metrics: {e}")
            return {"cpu": 0, "memory": 0, "io": 0}

    def read_psi_file(self, path: str) -> float:
        """
        Read PSI file and extract avg10 "some" value.

        Format:
        some avg10=1.23 avg60=4.56 avg300=7.89 total=123456
        full avg10=0.12 avg60=0.34 avg300=0.56 total=12345

        Returns avg10 value from "some" line.
        """
        try:
            if not os.path.exists(path):
                return 0.0

            with open(path, 'r') as f:
                for line in f:
                    if line.startswith("some"):
                        # Parse "some avg10=1.23 ..."
                        parts = line.split()
                        for part in parts:
                            if part.startswith("avg10="):
                                return float(part.split("=")[1])
            return 0.0
        except Exception as e:
            logger.warning(f"Failed to read PSI file {path}: {e}")
            return 0.0

    def _get_empty_vram(self) -> dict:
        """Return empty VRAM data structure."""
        return {
            "total_gb": 0.0,
            "used_gb": 0.0,
            "available_gb": 0.0,
            "usage_percentage": 0.0,
            "loaded_models": []
        }

    def _get_empty_health(self) -> dict:
        """Return empty health data structure."""
        return {
            "dynamodb": "unknown",
            "ollama": "unknown",
            "sglang": "unknown",
            "fastapi": "unknown",
            "auth": "unknown",
            "discord-bot": "unknown",
            "logging": "unknown",
        }

    def _get_empty_snapshot(self) -> dict:
        """Return empty monitoring snapshot."""
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "vram": self._get_empty_vram(),
            "services": self._get_empty_health(),
            "queue_size": 0,
            "psi": {"cpu": 0, "memory": 0, "io": 0},
            "maintenance_mode": False,
        }
