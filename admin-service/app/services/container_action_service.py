"""
Container Action Service

Executes container start/stop actions using custom scripts or default docker commands.
Configuration-driven to avoid hardcoding and support extensibility.

For scripts that require host-level access (swap, systemd, etc.), uses SSH to the host
machine to ensure proper TTY allocation and full environment access.
"""

import os
import asyncio
import subprocess
import logging
import yaml
from typing import Dict, Optional
from pathlib import Path
from app.clients.docker_client import DockerClient

logger = logging.getLogger(__name__)


class ContainerActionService:
    """Manages container actions (start/stop) using config-driven approach."""

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the service.

        Args:
            config_path: Path to container_actions.yaml (defaults to app/config/container_actions.yaml)
        """
        if config_path is None:
            config_path = Path(__file__).parent.parent / "config" / "container_actions.yaml"

        self.config_path = Path(config_path)
        self.config = self._load_config()

        # Path to mounted host project for script validation
        self.host_project_mount = Path("/host/project")

        # SSH configuration for host script execution
        self.ssh_host = os.getenv("SSH_HOST", "host.docker.internal")
        self.ssh_user = os.getenv("SSH_USER", "trosfy")
        self.ssh_key_path = os.getenv("SSH_KEY_PATH", "/home/app/.ssh/id_ed25519")

        # Docker client for health checks
        try:
            self.docker_client = DockerClient()
        except RuntimeError as e:
            logger.warning(f"Docker client not available: {e}")
            self.docker_client = None

    def _load_config(self) -> Dict:
        """Load container actions configuration from YAML."""
        try:
            if not self.config_path.exists():
                logger.warning(f"Config file not found at {self.config_path}, using defaults")
                return {"containers": {}}

            with open(self.config_path, 'r') as f:
                config = yaml.safe_load(f)
                return config or {"containers": {}}

        except Exception as e:
            logger.error(f"Failed to load container config: {e}")
            return {"containers": {}}

    def get_container_config(self, container_name: str) -> Optional[Dict]:
        """
        Get configuration for a specific container.

        Args:
            container_name: Name of the container (e.g., "trollama-sglang")

        Returns:
            Container config dict or None if no custom config exists
        """
        return self.config.get("containers", {}).get(container_name)

    async def start_container(self, container_name: str) -> Dict[str, any]:
        """
        Start a container using custom script or default docker command.

        For custom scripts: Trusts script's built-in health checking (e.g., start_sglang.sh)
        For default docker commands: Adds health check waiting to ensure container is ready

        Args:
            container_name: Name of the container to start

        Returns:
            dict: {"status": "success"|"error", "message": str, "method": "script"|"docker"}
        """
        container_config = self.get_container_config(container_name)

        # Start the container
        if container_config and "start_script" in container_config:
            # Custom script - trust its built-in health checking
            result = await self._run_script(
                script_path=container_config["start_script"],
                action="start",
                container_name=container_name,
                timeout=container_config.get("timeout", 300)
            )
            # Script already waited for health, return immediately
            return result
        else:
            # Default docker command - need to add health check
            result = await self._run_docker_command(
                container_name=container_name,
                action="start"
            )

            # If start failed, return immediately
            if result["status"] == "error":
                return result

            # Wait for container to become healthy
            health_timeout = container_config.get("health_timeout", 300) if container_config else 300
            health_result = await self._wait_for_healthy(container_name, timeout=health_timeout)

            # If health check failed, return error
            if health_result["status"] == "error":
                return health_result

            # Success - container is healthy
            return result

    async def stop_container(self, container_name: str) -> Dict[str, any]:
        """
        Stop a container using custom script or default docker command.

        Args:
            container_name: Name of the container to stop

        Returns:
            dict: {"status": "success"|"error", "message": str, "method": "script"|"docker"}
        """
        container_config = self.get_container_config(container_name)

        if container_config and "stop_script" in container_config:
            return await self._run_script(
                script_path=container_config["stop_script"],
                action="stop",
                container_name=container_name,
                timeout=container_config.get("timeout", 60)
            )
        else:
            return await self._run_docker_command(
                container_name=container_name,
                action="stop"
            )

    async def _run_script(
        self,
        script_path: str,
        action: str,
        container_name: str,
        timeout: int
    ) -> Dict[str, any]:
        """
        Run a custom script on the HOST via SSH.

        Uses SSH to execute the script on the host machine, providing:
        - Proper TTY allocation (fixes tqdm/progress bar issues)
        - Full host environment and PATH
        - Native sudo access
        - Reliable signal handling

        Args:
            script_path: Relative path from project root to script
            action: "start" or "stop"
            container_name: Container name for logging
            timeout: Script timeout in seconds

        Returns:
            Result dict with status and message
        """
        try:
            # Normalize script path (remove leading ./ if present)
            normalized_path = script_path.lstrip("./")

            # Verify script exists in mounted host project directory
            container_script_path = self.host_project_mount / normalized_path
            if not container_script_path.exists():
                logger.error(f"Script not found: {container_script_path}")
                return {
                    "status": "error",
                    "message": f"Script not found: {script_path}",
                    "method": "ssh"
                }

            # Verify SSH key exists
            if not Path(self.ssh_key_path).exists():
                logger.error(f"SSH key not found: {self.ssh_key_path}")
                return {
                    "status": "error",
                    "message": "SSH key not configured. Run scripts/setup_admin_ssh.sh first.",
                    "method": "ssh"
                }

            # Get host project root for script execution
            host_project_root = os.getenv("HOST_PROJECT_ROOT", "/home/trosfy/projects/discord-ollama-agent")
            host_script_path = f"{host_project_root}/{normalized_path}"

            logger.info(f"Running {action} script via SSH for {container_name}: {script_path}")

            # Build SSH command with TTY allocation
            ssh_cmd = [
                "ssh",
                "-t", "-t",  # Force TTY allocation (double -t for non-interactive)
                "-o", "StrictHostKeyChecking=no",
                "-o", "UserKnownHostsFile=/dev/null",
                "-o", "BatchMode=yes",
                "-o", "ConnectTimeout=10",
                "-o", "LogLevel=ERROR",  # Suppress SSH warnings
                "-i", self.ssh_key_path,
                f"{self.ssh_user}@{self.ssh_host}",
                f"{host_script_path} {host_project_root}"
            ]

            logger.debug(f"SSH command: {' '.join(ssh_cmd)}")

            # Use asyncio subprocess for non-blocking execution
            proc = await asyncio.create_subprocess_exec(
                *ssh_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=timeout
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                logger.error(f"Script timeout for {container_name} after {timeout}s")
                return {
                    "status": "error",
                    "message": f"Script timeout after {timeout} seconds",
                    "method": "ssh"
                }

            stdout_str = stdout.decode() if stdout else ""
            stderr_str = stderr.decode() if stderr else ""

            if proc.returncode == 0:
                logger.info(f"Successfully {action}ed {container_name} via SSH")
                return {
                    "status": "success",
                    "message": f"Container {container_name} {action}ed successfully via SSH",
                    "method": "ssh",
                    "output": stdout_str
                }
            else:
                # SSH returns exit code from remote command
                error_msg = stderr_str or stdout_str or f"Exit code {proc.returncode}"
                logger.error(f"SSH script failed for {container_name}: {error_msg}")
                return {
                    "status": "error",
                    "message": f"Script failed: {error_msg}",
                    "method": "ssh",
                    "exit_code": proc.returncode
                }

        except Exception as e:
            logger.error(f"Failed to run script for {container_name}: {e}")
            return {
                "status": "error",
                "message": str(e),
                "method": "ssh"
            }

    async def _run_docker_command(
        self,
        container_name: str,
        action: str
    ) -> Dict[str, any]:
        """
        Run default docker start/stop command.

        Args:
            container_name: Container name
            action: "start" or "stop"

        Returns:
            Result dict with status and message
        """
        try:
            if action == "start":
                cmd = ["docker", "start", container_name]
                timeout = 30
            else:  # stop
                cmd = ["docker", "stop", container_name, "-t", "10"]
                timeout = 30

            logger.info(f"Running docker {action} for {container_name}")

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=True
            )

            logger.info(f"Successfully {action}ed {container_name} via docker")
            return {
                "status": "success",
                "message": f"Container {container_name} {action}ed successfully",
                "method": "docker"
            }

        except subprocess.CalledProcessError as e:
            error_msg = e.stderr if e.stderr else str(e)
            logger.error(f"Docker {action} failed for {container_name}: {error_msg}")
            return {
                "status": "error",
                "message": f"Docker {action} failed: {error_msg}",
                "method": "docker"
            }
        except Exception as e:
            logger.error(f"Failed to {action} {container_name}: {e}")
            return {
                "status": "error",
                "message": str(e),
                "method": "docker"
            }

    async def _wait_for_healthy(
        self,
        container_name: str,
        timeout: int = 300,
        poll_interval: int = 2
    ) -> Dict[str, any]:
        """
        Wait for container to become healthy.

        Polls container health status until it reaches "healthy" or timeout expires.
        For containers without health checks, verifies container is running.

        Args:
            container_name: Name of the container to check
            timeout: Maximum time to wait in seconds (default 5 minutes)
            poll_interval: Time between health checks in seconds (default 2s)

        Returns:
            Result dict with status and message
        """
        if not self.docker_client:
            logger.warning(f"Docker client unavailable, skipping health check for {container_name}")
            return {
                "status": "success",
                "message": "Health check skipped (Docker client unavailable)"
            }

        start_time = asyncio.get_event_loop().time()
        elapsed = 0
        last_health_status = None

        logger.info(f"Waiting for {container_name} to become healthy (timeout: {timeout}s)")

        try:
            while elapsed < timeout:
                try:
                    # Get container status
                    status = self.docker_client.get_container_status(container_name)
                    health = status.get("health", "none")
                    running = status.get("running", False)

                    # Log status changes
                    if health != last_health_status:
                        logger.info(f"{container_name} health: {health} (running: {running})")
                        last_health_status = health

                    # Check if healthy
                    if health == "healthy":
                        logger.info(f"✅ {container_name} is healthy after {elapsed:.1f}s")
                        return {
                            "status": "success",
                            "message": f"Container {container_name} is healthy",
                            "health": health,
                            "elapsed_seconds": elapsed
                        }

                    # For containers without health checks, just verify running
                    if health == "none" and running:
                        logger.info(f"✅ {container_name} is running (no health check defined) after {elapsed:.1f}s")
                        return {
                            "status": "success",
                            "message": f"Container {container_name} is running",
                            "health": "none",
                            "elapsed_seconds": elapsed
                        }

                    # If container stopped or exited, fail immediately
                    if not running:
                        logger.error(f"❌ {container_name} stopped unexpectedly during health check")
                        return {
                            "status": "error",
                            "message": f"Container {container_name} stopped unexpectedly",
                            "health": health
                        }

                    # Wait before next check
                    await asyncio.sleep(poll_interval)
                    elapsed = asyncio.get_event_loop().time() - start_time

                except RuntimeError as e:
                    # Container not found or inspect failed
                    logger.warning(f"Failed to check {container_name} status: {e}")
                    await asyncio.sleep(poll_interval)
                    elapsed = asyncio.get_event_loop().time() - start_time

            # Timeout expired
            logger.error(f"❌ {container_name} health check timed out after {timeout}s (last status: {last_health_status})")
            return {
                "status": "error",
                "message": f"Container {container_name} did not become healthy within {timeout}s (status: {last_health_status})",
                "health": last_health_status,
                "elapsed_seconds": elapsed
            }

        except Exception as e:
            logger.error(f"Error during health check for {container_name}: {e}")
            return {
                "status": "error",
                "message": f"Health check failed: {str(e)}"
            }
