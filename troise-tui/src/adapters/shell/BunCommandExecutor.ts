import { spawn, type Subprocess } from "bun";
import type {
  ICommandExecutor,
  ExecuteOptions,
  CommandResult,
  CommandStream,
} from "@application/ports";
import { createCommand, type Command } from "@domain/entities";

/**
 * Command executor implementation using Bun's spawn API.
 */
export class BunCommandExecutor implements ICommandExecutor {
  private runningCommands = new Map<string, Subprocess>();
  private commandEntities = new Map<string, Command>();

  async execute(
    command: string,
    options?: ExecuteOptions
  ): Promise<CommandResult> {
    const commandId = options?.commandId || crypto.randomUUID();
    const startTime = Date.now();

    const proc = spawn({
      cmd: [options?.shell || "bash", "-c", command],
      cwd: options?.cwd || process.cwd(),
      env: { ...process.env, ...options?.env },
      stdout: "pipe",
      stderr: "pipe",
    });

    this.runningCommands.set(commandId, proc);

    // Create command entity for tracking
    const cmdEntity = createCommand(
      command,
      options?.cwd || process.cwd(),
      "user"
    );
    cmdEntity.id = commandId;
    this.commandEntities.set(commandId, cmdEntity);

    try {
      // Read all output
      const stdoutChunks: string[] = [];
      const stderrChunks: string[] = [];

      // Read stdout
      if (proc.stdout) {
        const reader = proc.stdout.getReader();
        const decoder = new TextDecoder();
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          stdoutChunks.push(decoder.decode(value));
        }
      }

      // Read stderr
      if (proc.stderr) {
        const reader = proc.stderr.getReader();
        const decoder = new TextDecoder();
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          stderrChunks.push(decoder.decode(value));
        }
      }

      // Wait for process to exit
      const exitCode = await proc.exited;

      const result: CommandResult = {
        commandId,
        exitCode,
        stdout: stdoutChunks.join(""),
        stderr: stderrChunks.join(""),
        durationMs: Date.now() - startTime,
        timedOut: false,
        killed: false,
      };

      return result;
    } finally {
      this.runningCommands.delete(commandId);
      this.commandEntities.delete(commandId);
    }
  }

  async *executeStreaming(
    command: string,
    options?: ExecuteOptions
  ): AsyncGenerator<CommandStream, CommandResult> {
    const commandId = options?.commandId || crypto.randomUUID();
    const startTime = Date.now();

    const proc = spawn({
      cmd: [options?.shell || "bash", "-c", command],
      cwd: options?.cwd || process.cwd(),
      env: { ...process.env, ...options?.env },
      stdout: "pipe",
      stderr: "pipe",
    });

    this.runningCommands.set(commandId, proc);

    // Create command entity for tracking
    const cmdEntity = createCommand(
      command,
      options?.cwd || process.cwd(),
      "user"
    );
    cmdEntity.id = commandId;
    this.commandEntities.set(commandId, cmdEntity);

    const stdoutChunks: string[] = [];
    const stderrChunks: string[] = [];

    try {
      // Stream stdout and stderr concurrently
      const decoder = new TextDecoder();

      const streamReader = async function* (
        stream: ReadableStream<Uint8Array> | null,
        type: "stdout" | "stderr",
        chunks: string[]
      ): AsyncGenerator<CommandStream> {
        if (!stream) return;
        const reader = stream.getReader();
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          const text = decoder.decode(value);
          chunks.push(text);
          yield { type, data: text, commandId };
        }
      };

      // Interleave stdout and stderr streams
      const stdoutStream = streamReader(proc.stdout, "stdout", stdoutChunks);
      const stderrStream = streamReader(proc.stderr, "stderr", stderrChunks);

      // Process both streams
      const processStream = async function* (
        gen: AsyncGenerator<CommandStream>
      ): AsyncGenerator<CommandStream> {
        for await (const chunk of gen) {
          yield chunk;
        }
      };

      // Yield from both streams (simplified - in practice you'd want proper interleaving)
      for await (const chunk of processStream(stdoutStream)) {
        yield chunk;
      }
      for await (const chunk of processStream(stderrStream)) {
        yield chunk;
      }

      // Wait for process to exit
      const exitCode = await proc.exited;

      return {
        commandId,
        exitCode,
        stdout: stdoutChunks.join(""),
        stderr: stderrChunks.join(""),
        durationMs: Date.now() - startTime,
        timedOut: false,
        killed: false,
      };
    } finally {
      this.runningCommands.delete(commandId);
      this.commandEntities.delete(commandId);
    }
  }

  async kill(commandId: string): Promise<void> {
    const proc = this.runningCommands.get(commandId);
    if (proc) {
      proc.kill();
      this.runningCommands.delete(commandId);
      this.commandEntities.delete(commandId);
    }
  }

  isRunning(commandId: string): boolean {
    return this.runningCommands.has(commandId);
  }

  getRunningCommands(): Command[] {
    return Array.from(this.commandEntities.values());
  }
}
