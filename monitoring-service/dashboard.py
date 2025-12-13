"""FastAPI web dashboard for monitoring."""
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from datetime import datetime, timedelta

templates = Jinja2Templates(directory="templates")


def create_app(health_checker, database):
    """Create FastAPI application."""
    app = FastAPI(title="System Health Monitor")

    @app.get("/", response_class=HTMLResponse)
    async def dashboard(request: Request):
        """Main dashboard page."""
        status = health_checker.get_current_status()
        return templates.TemplateResponse("index.html", {
            "request": request,
            "services": status,
            "last_update": datetime.utcnow().isoformat()
        })

    @app.get("/api/status")
    async def get_status():
        """API endpoint for current status."""
        return health_checker.get_current_status()

    @app.get("/api/history/{service}")
    async def get_history(service: str, hours: int = 24):
        """Get historical data for a service."""
        since = datetime.utcnow() - timedelta(hours=hours)
        history = database.get_health_history(service, since=since)
        return {"service": service, "history": history}

    @app.get("/api/alerts")
    async def get_alerts(limit: int = 50):
        """Get recent alerts."""
        alerts = database.get_alerts(limit=limit)
        return {"alerts": alerts}

    @app.get("/health")
    async def monitor_health():
        """Health check for monitoring service itself."""
        status = health_checker.get_current_status()
        all_healthy = all(
            s.get('current', {}).get('healthy', False)
            for s in status.values()
        )
        return {
            "status": "healthy" if all_healthy else "degraded",
            "services": {
                name: s.get('current', {}).get('healthy', False)
                for name, s in status.items()
            }
        }

    return app
