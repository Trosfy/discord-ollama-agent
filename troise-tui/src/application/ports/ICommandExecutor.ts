import type { Command } from "@domain/entities";

/**
 * Command executor interface for shell command execution.
 */
export interface ICommandExecutor {
  /**
   * Execute a shell command
   */
  execute(
    command: string,
    options?: ExecuteOptions
  ): Promise<CommandResult>;

  /**
   * Execute command with streaming output
   */
  executeStreaming(
    command: string,
    options?: ExecuteOptions
  ): AsyncGenerator<CommandStream, CommandResult>;

  /**
   * Kill a running command
   */
  kill(commandId: string): Promise<void>;

  /**
   * Check if a command is currently running
   */
  isRunning(commandId: string): boolean;

  /**
   * Get running commands
   */
  getRunningCommands(): Command[];
}

export interface ExecuteOptions {
  /** Working directory */
  cwd?: string;
  /** Environment variables */
  env?: Record<string, string>;
  /** Timeout in milliseconds */
  timeout?: number;
  /** Shell to use (bash, zsh, sh) */
  shell?: string;
  /** Command ID for tracking */
  commandId?: string;
}

export interface CommandResult {
  commandId: string;
  exitCode: number;
  stdout: string;
  stderr: string;
  durationMs: number;
  timedOut: boolean;
  killed: boolean;
}

export interface CommandStream {
  type: "stdout" | "stderr";
  data: string;
  commandId: string;
}
