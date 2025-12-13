"""SQLite database for health history."""
import sqlite3
from datetime import datetime
from pathlib import Path
import json


class HealthDatabase:
    """Persistent storage for health checks and alerts."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self._init_schema()

    def _init_schema(self):
        """Initialize database schema."""
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS health_checks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                service TEXT NOT NULL,
                timestamp TIMESTAMP NOT NULL,
                healthy BOOLEAN NOT NULL,
                status_code INTEGER,
                response_time_ms REAL,
                error TEXT,
                details TEXT
            )
        ''')

        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                service TEXT NOT NULL,
                timestamp TIMESTAMP NOT NULL,
                severity TEXT NOT NULL,
                message TEXT NOT NULL,
                details TEXT
            )
        ''')

        # Index for faster queries
        self.conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_health_service_timestamp
            ON health_checks(service, timestamp)
        ''')

        self.conn.commit()

    def add_health_check(self, result: dict):
        """Add health check result."""
        self.conn.execute('''
            INSERT INTO health_checks (service, timestamp, healthy, status_code, error, details)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            result['service'],
            result['timestamp'],
            result['healthy'],
            result.get('status_code'),
            result.get('error'),
            json.dumps(result.get('details'))
        ))
        self.conn.commit()

    def add_alert(self, service: str, severity: str, message: str, details: dict):
        """Add alert."""
        self.conn.execute('''
            INSERT INTO alerts (service, timestamp, severity, message, details)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            service,
            datetime.utcnow(),
            severity,
            message,
            json.dumps(details)
        ))
        self.conn.commit()

    def get_health_history(self, service: str, since: datetime, limit: int = 1000):
        """Get health history for a service."""
        cursor = self.conn.execute('''
            SELECT timestamp, healthy, status_code, error
            FROM health_checks
            WHERE service = ? AND timestamp >= ?
            ORDER BY timestamp DESC
            LIMIT ?
        ''', (service, since, limit))

        return [
            {
                'timestamp': row[0],
                'healthy': bool(row[1]),
                'status_code': row[2],
                'error': row[3]
            }
            for row in cursor.fetchall()
        ]

    def get_alerts(self, limit: int = 50):
        """Get recent alerts."""
        cursor = self.conn.execute('''
            SELECT service, timestamp, severity, message, details
            FROM alerts
            ORDER BY timestamp DESC
            LIMIT ?
        ''', (limit,))

        return [
            {
                'service': row[0],
                'timestamp': row[1],
                'severity': row[2],
                'message': row[3],
                'details': json.loads(row[4]) if row[4] else None
            }
            for row in cursor.fetchall()
        ]

    def close(self):
        """Close database connection."""
        self.conn.close()
