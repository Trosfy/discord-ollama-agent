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

    def cleanup_old_records(self, retention_days: int = 7):
        """Delete health checks and alerts older than retention period.

        Args:
            retention_days: Number of days to keep (default: 7)

        Returns:
            Dict with cleanup statistics:
            {
                'health_checks_deleted': int,
                'alerts_deleted': int,
                'cutoff_date': str
            }
        """
        from datetime import timedelta

        # Calculate cutoff date
        cutoff_date = datetime.utcnow() - timedelta(days=retention_days)

        # Count records before deletion (for metrics)
        cursor = self.conn.execute('SELECT COUNT(*) FROM health_checks WHERE timestamp < ?', (cutoff_date,))
        health_checks_to_delete = cursor.fetchone()[0]

        cursor = self.conn.execute('SELECT COUNT(*) FROM alerts WHERE timestamp < ?', (cutoff_date,))
        alerts_to_delete = cursor.fetchone()[0]

        # Delete old health checks
        self.conn.execute('DELETE FROM health_checks WHERE timestamp < ?', (cutoff_date,))

        # Delete old alerts
        self.conn.execute('DELETE FROM alerts WHERE timestamp < ?', (cutoff_date,))

        # Commit changes
        self.conn.commit()

        # Vacuum to reclaim disk space
        self.conn.execute('VACUUM')

        return {
            'health_checks_deleted': health_checks_to_delete,
            'alerts_deleted': alerts_to_delete,
            'cutoff_date': cutoff_date.isoformat()
        }

    def get_database_stats(self):
        """Get database statistics.

        Returns:
            Dict with database metrics:
            {
                'health_checks_count': int,
                'alerts_count': int,
                'oldest_health_check': str,
                'newest_health_check': str,
                'database_size_mb': float
            }
        """
        # Count health checks
        cursor = self.conn.execute('SELECT COUNT(*) FROM health_checks')
        health_checks_count = cursor.fetchone()[0]

        # Count alerts
        cursor = self.conn.execute('SELECT COUNT(*) FROM alerts')
        alerts_count = cursor.fetchone()[0]

        # Get date range
        cursor = self.conn.execute('SELECT MIN(timestamp), MAX(timestamp) FROM health_checks')
        oldest, newest = cursor.fetchone()

        # Get database file size
        db_size_bytes = Path(self.db_path).stat().st_size
        db_size_mb = db_size_bytes / 1024 / 1024

        return {
            'health_checks_count': health_checks_count,
            'alerts_count': alerts_count,
            'oldest_health_check': oldest,
            'newest_health_check': newest,
            'database_size_mb': round(db_size_mb, 2)
        }

    def close(self):
        """Close database connection."""
        self.conn.close()
