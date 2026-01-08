"""Unified memory monitor for DGX Spark (Grace Blackwell)."""
import subprocess
from typing import Dict

from app.services.vram.interfaces import IMemoryMonitor, MemoryStatus
from app.services.vram.model_registry import ModelRegistry
import logging_client

logger = logging_client.setup_logger('vram_monitor')


class UnifiedMemoryMonitor(IMemoryMonitor):
    """
    Memory monitoring for unified memory architecture.

    Single Responsibility: Query system memory and PSI.

    Uses Linux `free` and `/proc/pressure/memory` since nvidia-smi
    doesn't work on unified memory systems.
    """

    def __init__(self, registry: ModelRegistry):
        self._registry = registry

    async def get_status(self) -> MemoryStatus:
        """Query system memory using Linux `free` command and PSI."""
        try:
            # Run `free -b` to get bytes
            result = subprocess.run(
                ['free', '-b'],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode != 0:
                raise RuntimeError(f"free command failed: {result.stderr}")

            # Parse output
            lines = result.stdout.strip().split('\n')
            mem_line = lines[1]  # Second line: "Mem: ..."
            parts = mem_line.split()

            total_bytes = int(parts[1])
            used_bytes = int(parts[2])
            available_bytes = int(parts[6])  # "available" column

            # Convert to GB
            total_gb = total_bytes / (1024**3)
            used_gb = used_bytes / (1024**3)
            available_gb = available_bytes / (1024**3)

            # Get model usage from registry
            model_usage_gb = self._registry.get_total_usage_gb()

            # Check PSI
            psi_pressure = await self.check_pressure()
            if psi_pressure['some_avg10'] > 20.0:
                logger.warning(
                    f"⚠️  Memory pressure: "
                    f"some={psi_pressure['some_avg10']:.1f}%, "
                    f"full={psi_pressure['full_avg10']:.1f}%"
                )

            return MemoryStatus(
                total_gb=total_gb,
                used_gb=used_gb,
                available_gb=available_gb,
                model_usage_gb=model_usage_gb,
                psi_pressure=psi_pressure
            )

        except Exception as e:
            logger.error(f"❌ Failed to query memory: {e}")
            return MemoryStatus(
                total_gb=128.0,
                used_gb=100.0,
                available_gb=28.0,
                model_usage_gb=self._registry.get_total_usage_gb(),
                psi_pressure={'some_avg10': 0.0, 'full_avg10': 0.0}
            )

    async def check_pressure(self) -> Dict[str, float]:
        """
        Check Pressure Stall Information (PSI).

        From research: Early warning system for memory exhaustion.
        """
        try:
            with open('/proc/pressure/memory', 'r') as f:
                lines = f.readlines()

            psi = {'some_avg10': 0.0, 'full_avg10': 0.0}

            for line in lines:
                if line.startswith('some'):
                    parts = line.split()
                    for part in parts:
                        if part.startswith('avg10='):
                            psi['some_avg10'] = float(part.split('=')[1])
                elif line.startswith('full'):
                    parts = line.split()
                    for part in parts:
                        if part.startswith('avg10='):
                            psi['full_avg10'] = float(part.split('=')[1])

            return psi

        except Exception as e:
            logger.debug(f"Could not read PSI: {e}")
            return {'some_avg10': 0.0, 'full_avg10': 0.0}

    async def flush_cache(self) -> None:
        """Flush system buffer cache before loading large models."""
        try:
            logger.info("🧹 Flushing buffer cache")
            subprocess.run(
                ['sudo', 'sh', '-c', 'sync; echo 3 > /proc/sys/vm/drop_caches'],
                timeout=10,
                check=True
            )
            logger.info("✅ Buffer cache flushed")
        except FileNotFoundError:
            # Running in Docker without sudo
            logger.info(
                "⏭️  Skipping cache flush (Docker environment). "
                "Ensure external loader (start_sglang.sh) flushes cache."
            )
        except subprocess.CalledProcessError as e:
            logger.warning(f"⚠️  Cache flush failed (sudo required): {e}")
        except Exception as e:
            logger.warning(f"⚠️  Cache flush error: {e}")
