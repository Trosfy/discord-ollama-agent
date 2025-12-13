"""Monitoring service configuration."""
import sys
sys.path.insert(0, '/shared')

from log_config import LogSettings

# Expose log settings for monitoring service
log_settings = LogSettings()
