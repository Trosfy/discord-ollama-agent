"""
Docker Client

Handles Docker operations for container management.
Follows Single Responsibility Principle by isolating Docker API interactions.
"""

import logging
import subprocess
from typing import Dict, List, Optional
import json

logger = logging.getLogger(__name__)


class DockerClient:
    """
    Client for Docker operations.

    Responsibilities:
    - List containers
    - Get container status
    - Restart containers
    - Get container stats
    - Get container logs

    This class isolates Docker-specific logic from business services,
    making it easier to test and swap implementations.
    """

    def __init__(self):
        """Initialize Docker client."""
        self._check_docker_available()

    def _check_docker_available(self) -> bool:
        """
        Check if Docker CLI is available.

        Returns:
            bool: True if Docker is available

        Raises:
            RuntimeError: If Docker is not available
        """
        try:
            result = subprocess.run(
                ["docker", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                logger.debug(f"Docker available: {result.stdout.strip()}")
                return True
            else:
                raise RuntimeError("Docker CLI not available")
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            raise RuntimeError(f"Docker CLI not available: {e}")

    def list_containers(
        self,
        all_containers: bool = False,
        filters: Optional[Dict[str, str]] = None
    ) -> List[Dict]:
        """
        List Docker containers.

        Args:
            all_containers: Include stopped containers
            filters: Docker filters (e.g., {"name": "trollama-"})

        Returns:
            List of container info dicts with:
                - id: Container ID
                - name: Container name
                - status: Container status
                - image: Image name
                - created: Creation timestamp

        Raises:
            RuntimeError: If unable to list containers
        """
        try:
            cmd = ["docker", "ps", "--format", "{{json .}}"]

            if all_containers:
                cmd.append("--all")

            if filters:
                for key, value in filters.items():
                    cmd.extend(["--filter", f"{key}={value}"])

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode != 0:
                raise RuntimeError(f"Docker ps failed: {result.stderr}")

            # Parse NDJSON output
            containers = []
            for line in result.stdout.strip().split('\n'):
                if line:
                    container_json = json.loads(line)
                    containers.append({
                        "id": container_json.get("ID"),
                        "name": container_json.get("Names"),
                        "status": container_json.get("Status"),
                        "image": container_json.get("Image"),
                        "created": container_json.get("CreatedAt")
                    })

            return containers

        except subprocess.TimeoutExpired:
            raise RuntimeError("Docker ps command timed out")
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Failed to parse docker ps output: {e}")
        except Exception as e:
            raise RuntimeError(f"Failed to list containers: {e}")

    def get_container_status(self, container_name: str) -> Dict:
        """
        Get detailed status of a specific container.

        Args:
            container_name: Name of the container

        Returns:
            Dict with container status:
                - id: Container ID
                - name: Container name
                - status: Running/Exited/etc
                - health: healthy/unhealthy/none
                - uptime: How long container has been running

        Raises:
            RuntimeError: If unable to inspect container
        """
        try:
            result = subprocess.run(
                ["docker", "inspect", container_name],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode != 0:
                raise RuntimeError(f"Container not found: {container_name}")

            inspect_data = json.loads(result.stdout)[0]
            state = inspect_data.get("State", {})
            health = inspect_data.get("State", {}).get("Health", {})

            return {
                "id": inspect_data.get("Id"),
                "name": inspect_data.get("Name", "").lstrip("/"),
                "status": state.get("Status"),
                "health": health.get("Status", "none"),
                "running": state.get("Running", False),
                "started_at": state.get("StartedAt"),
                "finished_at": state.get("FinishedAt"),
                "exit_code": state.get("ExitCode")
            }

        except subprocess.TimeoutExpired:
            raise RuntimeError("Docker inspect command timed out")
        except (json.JSONDecodeError, IndexError, KeyError) as e:
            raise RuntimeError(f"Failed to parse container status: {e}")
        except Exception as e:
            raise RuntimeError(f"Failed to get container status: {e}")

    def restart_container(self, container_name: str, timeout: int = 10) -> bool:
        """
        Restart a Docker container.

        Args:
            container_name: Name of the container to restart
            timeout: Timeout in seconds for restart operation

        Returns:
            bool: True if restart successful

        Raises:
            RuntimeError: If unable to restart container
        """
        try:
            logger.info(f"Restarting container: {container_name}")

            result = subprocess.run(
                ["docker", "restart", "--time", str(timeout), container_name],
                capture_output=True,
                text=True,
                timeout=timeout + 5
            )

            if result.returncode != 0:
                raise RuntimeError(f"Docker restart failed: {result.stderr}")

            logger.info(f"Successfully restarted container: {container_name}")
            return True

        except subprocess.TimeoutExpired:
            raise RuntimeError(f"Docker restart timed out for {container_name}")
        except Exception as e:
            raise RuntimeError(f"Failed to restart container: {e}")

    def get_container_logs(
        self,
        container_name: str,
        tail: int = 100,
        since: Optional[str] = None
    ) -> str:
        """
        Get logs from a Docker container.

        Args:
            container_name: Name of the container
            tail: Number of lines to return from end of logs
            since: Only return logs since timestamp (e.g., "2023-01-01T00:00:00")

        Returns:
            str: Container logs

        Raises:
            RuntimeError: If unable to get logs
        """
        try:
            cmd = ["docker", "logs", "--tail", str(tail)]

            if since:
                cmd.extend(["--since", since])

            cmd.append(container_name)

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=15
            )

            if result.returncode != 0:
                raise RuntimeError(f"Docker logs failed: {result.stderr}")

            # Combine stdout and stderr (docker logs outputs to both)
            return result.stdout + result.stderr

        except subprocess.TimeoutExpired:
            raise RuntimeError("Docker logs command timed out")
        except Exception as e:
            raise RuntimeError(f"Failed to get container logs: {e}")

    def get_container_stats(self, container_name: str) -> Dict:
        """
        Get resource usage stats for a container.

        Args:
            container_name: Name of the container

        Returns:
            Dict with stats:
                - cpu_percent: CPU usage percentage
                - memory_usage: Memory usage in MB
                - memory_limit: Memory limit in MB
                - memory_percent: Memory usage percentage
                - net_input: Network input in MB
                - net_output: Network output in MB

        Raises:
            RuntimeError: If unable to get stats
        """
        try:
            result = subprocess.run(
                ["docker", "stats", "--no-stream", "--format", "{{json .}}", container_name],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode != 0:
                raise RuntimeError(f"Docker stats failed: {result.stderr}")

            stats_json = json.loads(result.stdout)

            return {
                "container_name": stats_json.get("Name"),
                "cpu_percent": stats_json.get("CPUPerc", "0%").rstrip("%"),
                "memory_usage": stats_json.get("MemUsage", "0MiB / 0MiB").split(" / ")[0],
                "memory_limit": stats_json.get("MemUsage", "0MiB / 0MiB").split(" / ")[1],
                "memory_percent": stats_json.get("MemPerc", "0%").rstrip("%"),
                "net_input": stats_json.get("NetIO", "0B / 0B").split(" / ")[0],
                "net_output": stats_json.get("NetIO", "0B / 0B").split(" / ")[1],
                "block_input": stats_json.get("BlockIO", "0B / 0B").split(" / ")[0],
                "block_output": stats_json.get("BlockIO", "0B / 0B").split(" / ")[1]
            }

        except subprocess.TimeoutExpired:
            raise RuntimeError("Docker stats command timed out")
        except (json.JSONDecodeError, IndexError) as e:
            raise RuntimeError(f"Failed to parse container stats: {e}")
        except Exception as e:
            raise RuntimeError(f"Failed to get container stats: {e}")
