import WebSocket from "ws";
import { EventEmitter } from "events";
import type {
  IWebSocketClient,
  WebSocketEvents,
  SendMessageOptions,
  SessionStartEvent,
  RoutingEvent,
  QueuedEvent,
  StreamEvent,
  StreamEndEvent,
  ResponseEvent,
  QuestionEvent,
  FileEvent,
  ExecuteCommandEvent,
  ErrorEvent,
  HistoryEvent,
  CancelledEvent,
} from "@application/ports";

/**
 * WebSocket client implementation for TROISE AI.
 */
export class TroiseWebSocketClient implements IWebSocketClient {
  private ws: WebSocket | null = null;
  private emitter = new EventEmitter();
  private sessionId: string | undefined;
  private userId: string | undefined;
  private url: string = "";
  private reconnectDelay = 1000;
  private maxReconnectDelay = 30000;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 10;
  private pingInterval: NodeJS.Timeout | null = null;
  private reconnecting = false;

  async connect(url: string, userId: string): Promise<void> {
    this.url = url;
    this.userId = userId;

    return new Promise((resolve, reject) => {
      try {
        const wsUrl = `${url}/ws/chat?interface=cli&user_id=${userId}`;
        this.ws = new WebSocket(wsUrl);

        this.ws.on("open", () => {
          this.reconnectAttempts = 0;
          this.reconnectDelay = 1000;
          this.startPing();
        });

        this.ws.on("message", (data) => {
          try {
            const message = JSON.parse(data.toString());

            // Debug logging to file for troubleshooting
            if (process.env.DEBUG_WS) {
              const fs = require("fs");
              const logLine = `[${new Date().toISOString()}] ${message.type}: ${JSON.stringify(message).slice(0, 500)}\n`;
              fs.appendFileSync("/tmp/troise-ws-debug.log", logLine);
            }

            this.handleMessage(message);

            // Resolve on session_start
            if (message.type === "session_start") {
              resolve();
            }
          } catch (e) {
            console.error("Failed to parse message:", e);
          }
        });

        this.ws.on("close", (code, reason) => {
          this.stopPing();
          this.emitter.emit("disconnected", reason?.toString());

          // Auto-reconnect if not intentionally closed
          if (code !== 1000 && !this.reconnecting) {
            this.attemptReconnect();
          }
        });

        this.ws.on("error", (error) => {
          this.emitter.emit("error", { error: error.message });
          reject(error);
        });
      } catch (error) {
        reject(error);
      }
    });
  }

  async disconnect(): Promise<void> {
    this.stopPing();
    this.reconnecting = false;

    if (this.ws) {
      this.ws.close(1000, "Client disconnected");
      this.ws = null;
    }
  }

  async sendMessage(content: string, options?: SendMessageOptions): Promise<void> {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      throw new Error("Not connected to TROISE AI");
    }

    const message: Record<string, unknown> = {
      type: "message",
      content,
    };

    if (options?.files?.length) {
      message.files = options.files.map((f) => ({
        filename: f.filename,
        mimetype: f.mimetype,
        base64_data: f.base64Data,
      }));
    }

    if (options?.messageId) {
      message.message_id = options.messageId;
    }

    if (options?.metadata) {
      message.metadata = options.metadata;
    }

    this.ws.send(JSON.stringify(message));
  }

  async sendAnswer(requestId: string, answer: string): Promise<void> {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      throw new Error("Not connected to TROISE AI");
    }

    this.ws.send(
      JSON.stringify({
        type: "answer",
        request_id: requestId,
        content: answer,
      })
    );
  }

  async cancelRequest(requestId: string): Promise<void> {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      return;
    }

    this.ws.send(
      JSON.stringify({
        type: "cancel",
        request_id: requestId,
      })
    );
  }

  async requestHistory(): Promise<void> {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      throw new Error("Not connected to TROISE AI");
    }

    this.ws.send(JSON.stringify({ type: "history" }));
  }

  /**
   * Send command output back to TROISE AI (for agent-initiated commands)
   */
  async sendCommandOutput(
    requestId: string,
    stdout: string,
    stderr: string,
    exitCode: number,
    status: "completed" | "running" | "cancelled" | "error"
  ): Promise<void> {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      return;
    }

    this.ws.send(
      JSON.stringify({
        type: "command_output",
        request_id: requestId,
        stdout,
        stderr,
        exit_code: exitCode,
        status,
      })
    );
  }

  /**
   * Send streaming command output
   */
  async sendCommandStream(
    requestId: string,
    chunk: string,
    stream: "stdout" | "stderr"
  ): Promise<void> {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      return;
    }

    this.ws.send(
      JSON.stringify({
        type: "command_stream",
        request_id: requestId,
        chunk,
        stream,
      })
    );
  }

  isConnected(): boolean {
    return this.ws !== null && this.ws.readyState === WebSocket.OPEN;
  }

  getSessionId(): string | undefined {
    return this.sessionId;
  }

  on<K extends keyof WebSocketEvents>(
    event: K,
    handler: WebSocketEvents[K]
  ): void {
    this.emitter.on(event, handler);
  }

  off<K extends keyof WebSocketEvents>(
    event: K,
    handler: WebSocketEvents[K]
  ): void {
    this.emitter.off(event, handler);
  }

  private handleMessage(message: Record<string, unknown>): void {
    const type = message.type as string;

    switch (type) {
      case "session_start":
        this.sessionId = message.session_id as string;
        this.emitter.emit("connected", {
          sessionId: message.session_id,
          userId: message.user_id,
          interface: message.interface,
          resumed: message.resumed,
          messageCount: message.message_count,
        } as SessionStartEvent);
        break;

      case "routing":
        this.emitter.emit("routing", {
          skillOrAgent: message.skill_or_agent,
          routingType: message.routing_type,
          reason: message.reason,
        } as RoutingEvent);
        break;

      case "queued":
        this.emitter.emit("queued", {
          requestId: message.request_id,
          position: message.position,
        } as QueuedEvent);
        break;

      case "stream":
        this.emitter.emit("stream", {
          content: message.content,
          requestId: message.request_id,
        } as StreamEvent);
        break;

      case "stream_end":
        this.emitter.emit("streamEnd", {
          requestId: message.request_id,
        } as StreamEndEvent);
        break;

      case "response":
        this.emitter.emit("response", {
          content: message.content,
          source: message.source,
          part: message.part,
          totalParts: message.total_parts,
        } as ResponseEvent);
        break;

      case "question":
        this.emitter.emit("question", {
          requestId: message.request_id,
          question: message.question || message.content,
          options: message.options,
        } as QuestionEvent);
        break;

      case "file":
        this.emitter.emit("file", {
          filename: message.filename,
          base64Data: message.base64_data,
          mimetype: message.mimetype,
          confidence: message.confidence,
        } as FileEvent);
        break;

      case "execute_command":
        this.emitter.emit("executeCommand", {
          requestId: message.request_id,
          command: message.command,
          workingDir: message.working_dir,
          requiresApproval: message.requires_approval ?? true,
        } as ExecuteCommandEvent);
        break;

      case "error":
        this.emitter.emit("error", {
          error: message.error || message.content,
          code: message.code,
        } as ErrorEvent);
        break;

      case "history":
        this.emitter.emit("history", {
          sessionId: message.session_id,
          messages: message.messages,
        } as HistoryEvent);
        break;

      case "cancelled":
        this.emitter.emit("cancelled", {
          requestId: message.request_id,
          reason: message.reason,
        } as CancelledEvent);
        break;

      case "pong":
        // Heartbeat response - ignore
        break;

      default:
        console.warn(`Unknown message type: ${type}`);
    }
  }

  private startPing(): void {
    this.stopPing();
    this.pingInterval = setInterval(() => {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        this.ws.send(JSON.stringify({ type: "ping" }));
      }
    }, 30000);
  }

  private stopPing(): void {
    if (this.pingInterval) {
      clearInterval(this.pingInterval);
      this.pingInterval = null;
    }
  }

  private async attemptReconnect(): Promise<void> {
    if (this.reconnecting || this.reconnectAttempts >= this.maxReconnectAttempts) {
      return;
    }

    this.reconnecting = true;

    while (
      this.reconnectAttempts < this.maxReconnectAttempts &&
      this.reconnecting
    ) {
      this.reconnectAttempts++;

      const delay = Math.min(
        this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1),
        this.maxReconnectDelay
      );

      console.log(
        `Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})...`
      );

      await new Promise((resolve) => setTimeout(resolve, delay));

      try {
        if (this.userId) {
          await this.connect(this.url, this.userId);
          this.reconnecting = false;
          console.log("Reconnected successfully");
          return;
        }
      } catch (error) {
        console.error("Reconnection failed:", error);
      }
    }

    this.reconnecting = false;
    console.error("Max reconnection attempts reached");
  }
}
