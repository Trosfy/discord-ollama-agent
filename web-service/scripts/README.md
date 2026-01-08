# Web Service Scripts

This directory contains host management scripts that can be executed from within the web-service Docker container.

## Purpose

The web-service container has access to:
- Docker socket (`/var/run/docker.sock`) for container management
- This scripts directory for executing host-level operations

## Security

- All scripts must be carefully reviewed before execution
- Scripts have full Docker access through the mounted socket
- Only admin users should be able to execute scripts
- Script execution is logged for audit purposes

## Usage

Scripts placed in this directory can be executed by the web-service container using the bash interpreter.

Example structure:
```
scripts/
├── README.md (this file)
├── backup/
│   └── backup-database.sh
├── maintenance/
│   └── cleanup-logs.sh
└── monitoring/
    └── check-health.sh
```

## Best Practices

1. **Always validate inputs** - Never trust user-provided parameters
2. **Use absolute paths** - Avoid relying on relative paths
3. **Add error handling** - Check for failures and report them clearly
4. **Log operations** - Keep track of what scripts do
5. **Test thoroughly** - Test scripts in development before production use
