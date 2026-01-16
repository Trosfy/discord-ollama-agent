/**
 * Command entity - represents a shell command execution.
 */
export interface Command {
  id: string;
  command: string;
  args: string[];
  workingDir: string;
  status: CommandStatus;
  stdout: string;
  stderr: string;
  exitCode?: number;
  startedAt: Date;
  completedAt?: Date;
  /** Who initiated the command */
  initiator: "user" | "agent";
  /** Request ID if agent-initiated */
  requestId?: string;
  /** Whether user approved (for dangerous commands) */
  approved?: boolean;
}

export type CommandStatus =
  | "pending"      // Waiting for approval
  | "running"      // Currently executing
  | "completed"    // Finished successfully (exit code 0)
  | "failed"       // Finished with error (exit code != 0)
  | "cancelled"    // User cancelled
  | "timeout";     // Exceeded timeout

/**
 * Dangerous command patterns that require user approval
 */
export const DANGEROUS_PATTERNS = [
  /^rm\s/,
  /^sudo\s/,
  /^chmod\s+[0-7]*7/,
  /^chown\s/,
  /^mv\s.*\//,
  /^dd\s/,
  />\s*\/dev\//,
  /mkfs/,
  /fdisk/,
  /parted/,
  /kill\s+-9/,
  /killall/,
  /shutdown/,
  /reboot/,
  /init\s+0/,
  /systemctl\s+(stop|disable|mask)/,
  /npm\s+publish/,
  /git\s+push\s+.*--force/,
  /git\s+reset\s+--hard/,
  /DROP\s+TABLE/i,
  /DELETE\s+FROM/i,
  /TRUNCATE/i,
];

/**
 * Check if a command is dangerous and requires approval
 */
export function isDangerousCommand(command: string): boolean {
  const fullCommand = command.trim();
  return DANGEROUS_PATTERNS.some((pattern) => pattern.test(fullCommand));
}

/**
 * Create a new command
 */
export function createCommand(
  command: string,
  workingDir: string,
  initiator: "user" | "agent",
  requestId?: string
): Command {
  const parts = parseCommand(command);
  const needsApproval = isDangerousCommand(command);

  return {
    id: crypto.randomUUID(),
    command: parts.command,
    args: parts.args,
    workingDir,
    status: needsApproval ? "pending" : "running",
    stdout: "",
    stderr: "",
    startedAt: new Date(),
    initiator,
    requestId,
    approved: !needsApproval,
  };
}

/**
 * Parse a command string into command and arguments
 */
function parseCommand(input: string): { command: string; args: string[] } {
  const parts = input.trim().split(/\s+/);
  return {
    command: parts[0] || "",
    args: parts.slice(1),
  };
}

/**
 * Format command for display
 */
export function formatCommand(cmd: Command): string {
  return `${cmd.command} ${cmd.args.join(" ")}`.trim();
}

/**
 * Calculate command duration in milliseconds
 */
export function getCommandDuration(cmd: Command): number | null {
  if (!cmd.completedAt) return null;
  return cmd.completedAt.getTime() - cmd.startedAt.getTime();
}
