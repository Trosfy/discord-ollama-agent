/**
 * Base domain error class
 */
export class DomainError extends Error {
  constructor(
    message: string,
    public readonly code: string,
    public readonly details?: Record<string, unknown>
  ) {
    super(message);
    this.name = "DomainError";
  }
}

/**
 * Connection-related errors
 */
export class ConnectionError extends DomainError {
  constructor(message: string, details?: Record<string, unknown>) {
    super(message, "CONNECTION_ERROR", details);
    this.name = "ConnectionError";
  }
}

export class ConnectionTimeoutError extends ConnectionError {
  constructor(timeoutMs: number) {
    super(`Connection timed out after ${timeoutMs}ms`, { timeoutMs });
    this.name = "ConnectionTimeoutError";
  }
}

export class ConnectionRefusedError extends ConnectionError {
  constructor(url: string) {
    super(`Connection refused: ${url}`, { url });
    this.name = "ConnectionRefusedError";
  }
}

/**
 * File system errors
 */
export class FileSystemError extends DomainError {
  constructor(
    message: string,
    public readonly path: string,
    details?: Record<string, unknown>
  ) {
    super(message, "FILESYSTEM_ERROR", { path, ...details });
    this.name = "FileSystemError";
  }
}

export class FileNotFoundError extends FileSystemError {
  constructor(path: string) {
    super(`File not found: ${path}`, path);
    this.name = "FileNotFoundError";
  }
}

export class FileReadError extends FileSystemError {
  constructor(path: string, reason?: string) {
    super(`Failed to read file: ${path}${reason ? ` (${reason})` : ""}`, path, {
      reason,
    });
    this.name = "FileReadError";
  }
}

export class FileWriteError extends FileSystemError {
  constructor(path: string, reason?: string) {
    super(`Failed to write file: ${path}${reason ? ` (${reason})` : ""}`, path, {
      reason,
    });
    this.name = "FileWriteError";
  }
}

export class FileTooLargeError extends FileSystemError {
  constructor(path: string, size: number, maxSize: number) {
    super(
      `File too large: ${path} (${size} bytes, max ${maxSize} bytes)`,
      path,
      { size, maxSize }
    );
    this.name = "FileTooLargeError";
  }
}

/**
 * Command execution errors
 */
export class CommandError extends DomainError {
  constructor(
    message: string,
    public readonly command: string,
    details?: Record<string, unknown>
  ) {
    super(message, "COMMAND_ERROR", { command, ...details });
    this.name = "CommandError";
  }
}

export class CommandTimeoutError extends CommandError {
  constructor(command: string, timeoutMs: number) {
    super(`Command timed out after ${timeoutMs}ms: ${command}`, command, {
      timeoutMs,
    });
    this.name = "CommandTimeoutError";
  }
}

export class CommandRejectedError extends CommandError {
  constructor(command: string) {
    super(`Command rejected by user: ${command}`, command);
    this.name = "CommandRejectedError";
  }
}

/**
 * Validation errors
 */
export class ValidationError extends DomainError {
  constructor(
    message: string,
    public readonly field: string,
    details?: Record<string, unknown>
  ) {
    super(message, "VALIDATION_ERROR", { field, ...details });
    this.name = "ValidationError";
  }
}

/**
 * Configuration errors
 */
export class ConfigurationError extends DomainError {
  constructor(message: string, details?: Record<string, unknown>) {
    super(message, "CONFIGURATION_ERROR", details);
    this.name = "ConfigurationError";
  }
}

export class ProfileNotFoundError extends ConfigurationError {
  constructor(profileName: string) {
    super(`Profile not found: ${profileName}`, { profileName });
    this.name = "ProfileNotFoundError";
  }
}

export class ServerNotFoundError extends ConfigurationError {
  constructor(serverName: string) {
    super(`Server configuration not found: ${serverName}`, { serverName });
    this.name = "ServerNotFoundError";
  }
}
