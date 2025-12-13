"""Generalized health check HTTP server for all services."""
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
from typing import Dict, Callable


class HealthCheckHandler(BaseHTTPRequestHandler):
    """HTTP handler for health checks."""

    # Class variables shared across instances
    health_checks: Dict[str, Callable[[], bool]] = {}
    service_name: str = "unknown"

    def do_GET(self):
        if self.path == '/health':
            try:
                results = {}
                all_healthy = True

                for check_name, check_func in self.health_checks.items():
                    try:
                        is_healthy = check_func()
                        results[check_name] = {
                            "status": "healthy" if is_healthy else "unhealthy",
                            "healthy": is_healthy
                        }
                        if not is_healthy:
                            all_healthy = False
                    except Exception as e:
                        results[check_name] = {
                            "status": "error",
                            "healthy": False,
                            "error": str(e)
                        }
                        all_healthy = False

                response = {
                    "service": self.service_name,
                    "status": "healthy" if all_healthy else "unhealthy",
                    "checks": results
                }

                status_code = 200 if all_healthy else 503
                self.send_response(status_code)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(response).encode())

            except Exception as e:
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({
                    "service": self.service_name,
                    "status": "error",
                    "error": str(e)
                }).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass  # Suppress HTTP logs


class HealthCheckServer:
    """Generalized health check server."""

    def __init__(self, service_name: str, port: int = 9998):
        self.service_name = service_name
        self.port = port
        self.health_checks: Dict[str, Callable[[], bool]] = {}
        self.server = None
        self.thread = None

    def register_check(self, name: str, check_func: Callable[[], bool]):
        """Register a health check function.

        Args:
            name: Name of the check (e.g., "mount", "database")
            check_func: Function that returns True if healthy, False otherwise
        """
        self.health_checks[name] = check_func

    def start(self):
        """Start the health check HTTP server."""
        # Update class variables
        HealthCheckHandler.health_checks = self.health_checks
        HealthCheckHandler.service_name = self.service_name

        # Start HTTP server in background thread
        self.server = HTTPServer(('0.0.0.0', self.port), HealthCheckHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        print(f"✅ Health check server started for {self.service_name} on port {self.port}")

    def stop(self):
        """Stop the health check server."""
        if self.server:
            self.server.shutdown()
