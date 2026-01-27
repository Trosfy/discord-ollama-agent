"""
System Metrics Service

Aggregates system-level monitoring data from multiple sources:
- VRAM stats (system memory via free -m)
- Queue stats from fastapi-service
- PSI metrics from host system
- Maintenance mode status

Note: Service health checks are handled by HealthCheckerService.
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


class SystemMetricsService:
    """Aggregates system-level metrics (VRAM, PSI, queue) for metrics collection."""

    def __init__(self):
        self.http_client = httpx.AsyncClient(timeout=5.0)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.http_client.aclose()

    async def start(self):
        """Start background tasks if needed (currently no background tasks)."""
        logger.info("System metrics service started")

    async def stop(self):
        """Stop background tasks and cleanup."""
        await self.http_client.aclose()
        logger.info("System metrics service stopped")

    async def get_system_snapshot(self) -> dict:
        """
        Get current system metrics from all sources.

        Returns aggregated data for:
        - VRAM metrics (system memory)
        - Queue size
        - PSI metrics
        - GPU metrics (temperature, power)
        - CPU utilization
        - Maintenance mode

        Note: Service health is handled by HealthCheckerService
        """
        try:
            # Fetch all data in parallel for performance
            vram_data, queue_data, psi_data, gpu_data, cpu_util = await asyncio.gather(
                self.fetch_vram_stats(),
                self.fetch_queue_stats(),
                self.fetch_psi_metrics(),
                self.fetch_gpu_metrics(),
                self.fetch_cpu_utilization(),
                return_exceptions=True
            )

            # Handle potential errors from parallel tasks
            if isinstance(vram_data, Exception):
                logger.error(f"VRAM fetch failed: {vram_data}")
                vram_data = self._get_empty_vram()

            if isinstance(queue_data, Exception):
                logger.error(f"Queue fetch failed: {queue_data}")
                queue_data = {"size": 0}

            if isinstance(psi_data, Exception):
                logger.error(f"PSI fetch failed: {psi_data}")
                psi_data = {"cpu": 0, "memory": 0, "io": 0}

            if isinstance(gpu_data, Exception):
                logger.error(f"GPU fetch failed: {gpu_data}")
                gpu_data = {"temperature_c": 0, "power_draw_w": 0, "utilization_pct": 0}

            if isinstance(cpu_util, Exception):
                logger.error(f"CPU utilization fetch failed: {cpu_util}")
                cpu_util = 0.0

            return {
                "timestamp": datetime.utcnow().isoformat(),
                "vram": vram_data,
                "queue_size": queue_data.get("size", 0),
                "psi": psi_data,
                "gpu": gpu_data,
                "cpu_utilization": cpu_util,
                "maintenance_mode": False,  # TODO: Fetch from settings
            }

        except Exception as e:
            logger.error(f"Error getting system snapshot: {e}", exc_info=True)
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

                # Fetch loaded models from backend registry
                loaded_models = await self.fetch_loaded_models()

                return {
                    "total_gb": total_gb,
                    "used_gb": used_gb,
                    "available_gb": available_gb,
                    "usage_percentage": usage_pct,
                    "loaded_models": loaded_models
                }
            else:
                logger.warning(f"free command failed: {result.stderr}")
                return self._get_empty_vram()
        except Exception as e:
            logger.warning(f"Failed to fetch memory stats: {e}")
            return self._get_empty_vram()

    async def fetch_loaded_models(self) -> list:
        """
        Fetch currently loaded models from all configured backends.

        For SGLang: Returns models actively loaded in VRAM and serving requests.
        For Ollama: Returns ONLY loaded models (from /api/ps), not all downloaded models.

        Uses the BackendRegistry to query SGLang, Ollama, etc.

        Returns:
            List of dicts with keys:
                - name: Model name
                - size_gb: Model size in GB
                - backend: Backend type
                - is_loaded: Whether model is currently in memory
                - can_toggle: Whether model can be loaded/unloaded via API
        """
        try:
            from app.backend_registry import BackendRegistry

            loaded_models = []
            logger.debug("🔍 Fetching loaded models from backends...")

            # Iterate over all enabled backends
            for backend in BackendRegistry.get_enabled_backends():
                try:
                    if backend.type == "ollama":
                        # For Ollama: Query /api/ps to get ONLY loaded models
                        ps_url = f"{backend.endpoint}/api/ps"
                        logger.debug(f"Querying Ollama loaded models at {ps_url}")
                        response = await self.http_client.get(ps_url)

                        if response.status_code == 200:
                            data = response.json()
                            models_data = data.get("models", [])

                            # Convert /api/ps format to our format
                            models = []
                            for model_info in models_data:
                                model_name = model_info.get("name", "")
                                model_size_bytes = model_info.get("size", 0)

                                if model_name:
                                    models.append({
                                        "name": model_name,
                                        "size_gb": round(model_size_bytes / (1024 ** 3), 1),
                                        "backend": "ollama",
                                        "is_loaded": True,  # /api/ps only returns loaded models
                                        "can_toggle": True
                                    })

                            loaded_models.extend(models)
                            logger.debug(f"✅ Found {len(models)} loaded models in Ollama: {[m['name'] for m in models]}")
                        else:
                            logger.warning(f"⚠️ Ollama /api/ps returned status {response.status_code}")

                    else:
                        # For other backends (SGLang): Use original logic
                        url = f"{backend.endpoint}{backend.models_endpoint}"
                        logger.debug(f"Querying {backend.type} at {url}")
                        response = await self.http_client.get(url)

                        if response.status_code == 200:
                            data = response.json()
                            models = backend.parser.parse(data, backend.type)

                            # Add UI control fields based on backend type
                            for model in models:
                                if backend.type == "sglang":
                                    # SGLang models are always loaded and cannot be toggled
                                    model["is_loaded"] = True
                                    model["can_toggle"] = False
                                else:
                                    # Unknown backend - default to non-toggleable
                                    model["is_loaded"] = True
                                    model["can_toggle"] = False

                            loaded_models.extend(models)
                            logger.debug(f"✅ Found {len(models)} models in {backend.type}: {[m['name'] for m in models]}")
                        else:
                            logger.warning(f"⚠️ {backend.type} returned status {response.status_code}")

                except Exception as e:
                    logger.warning(f"❌ Failed to fetch models from {backend.type}: {e}")

            logger.debug(f"📊 Total loaded models: {len(loaded_models)}")
            return loaded_models

        except Exception as e:
            logger.error(f"Failed to fetch loaded models: {e}", exc_info=True)
            return []

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

        Returns avg10 value (10-second average) from "some" line.
        Using avg10 provides real-time pressure indication.
        """
        try:
            if not os.path.exists(path):
                return 0.0

            with open(path, 'r') as f:
                for line in f:
                    if line.startswith("some"):
                        # Parse "some avg10=1.23 avg60=4.56 avg300=7.89 ..."
                        parts = line.split()
                        for part in parts:
                            if part.startswith("avg10="):
                                return float(part.split("=")[1])
            return 0.0
        except Exception as e:
            logger.warning(f"Failed to read PSI file {path}: {e}")
            return 0.0

    async def fetch_gpu_metrics(self) -> dict:
        """
        Fetch GPU temperature, power draw, and utilization using nvidia-smi.

        Returns dict with:
        - temperature_c: float (GPU temperature in Celsius)
        - power_draw_w: float (Power draw in Watts)
        - utilization_pct: float (GPU utilization percentage)
        """
        try:
            # Execute nvidia-smi with CSV output including utilization
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=temperature.gpu,power.draw,utilization.gpu", "--format=csv,noheader,nounits"],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                # Parse CSV output: "49, 11.44, 75"
                line = result.stdout.strip()
                if line:
                    parts = line.split(',')
                    if len(parts) >= 3:
                        temp = float(parts[0].strip())
                        power = float(parts[1].strip())
                        utilization = float(parts[2].strip())
                        return {
                            "temperature_c": temp,
                            "power_draw_w": power,
                            "utilization_pct": utilization
                        }

                logger.warning("nvidia-smi returned empty output")
                return {"temperature_c": 0, "power_draw_w": 0, "utilization_pct": 0}
            else:
                logger.warning(f"nvidia-smi command failed: {result.stderr}")
                return {"temperature_c": 0, "power_draw_w": 0, "utilization_pct": 0}
        except FileNotFoundError:
            logger.warning("nvidia-smi not found - GPU metrics unavailable")
            return {"temperature_c": 0, "power_draw_w": 0, "utilization_pct": 0}
        except Exception as e:
            logger.warning(f"Failed to fetch GPU metrics: {e}")
            return {"temperature_c": 0, "power_draw_w": 0, "utilization_pct": 0}

    async def fetch_cpu_utilization(self) -> float:
        """
        Fetch CPU utilization percentage.

        Reads /proc/stat twice with a small delay to calculate CPU usage.

        Returns:
            float: CPU utilization percentage (0-100)
        """
        try:
            def read_cpu_stats():
                """Read CPU stats from /proc/stat."""
                with open('/proc/stat', 'r') as f:
                    line = f.readline()
                    # Format: cpu  user nice system idle iowait irq softirq steal guest guest_nice
                    fields = line.strip().split()
                    if fields[0] == 'cpu':
                        # Sum all time values
                        times = [int(x) for x in fields[1:]]
                        idle = times[3]  # idle time
                        total = sum(times)
                        return idle, total
                return 0, 0

            # Read stats twice with 100ms delay
            idle1, total1 = read_cpu_stats()
            await asyncio.sleep(0.1)
            idle2, total2 = read_cpu_stats()

            # Calculate utilization
            idle_delta = idle2 - idle1
            total_delta = total2 - total1

            if total_delta == 0:
                return 0.0

            utilization = 100.0 * (1.0 - idle_delta / total_delta)
            return round(utilization, 2)

        except Exception as e:
            logger.warning(f"Failed to fetch CPU utilization: {e}")
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

    def _get_empty_snapshot(self) -> dict:
        """Return empty system snapshot."""
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "vram": self._get_empty_vram(),
            "queue_size": 0,
            "psi": {"cpu": 0, "memory": 0, "io": 0},
            "gpu": {"temperature_c": 0, "power_draw_w": 0},
            "cpu_utilization": 0.0,
            "maintenance_mode": False,
        }
