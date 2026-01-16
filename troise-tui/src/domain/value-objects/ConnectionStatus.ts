/**
 * ConnectionStatus - WebSocket connection state
 */
export type ConnectionStatus =
  | "disconnected"
  | "connecting"
  | "connected"
  | "reconnecting"
  | "error";

export interface ConnectionState {
  status: ConnectionStatus;
  sessionId?: string;
  userId?: string;
  serverUrl: string;
  retryCount: number;
  lastError?: string;
  connectedAt?: Date;
}

export const CONNECTION_ICONS: Record<ConnectionStatus, string> = {
  disconnected: "🔴",
  connecting: "⚪",
  connected: "🟢",
  reconnecting: "🟡",
  error: "🔴",
};

export const CONNECTION_LABELS: Record<ConnectionStatus, string> = {
  disconnected: "Disconnected",
  connecting: "Connecting...",
  connected: "Connected",
  reconnecting: "Reconnecting...",
  error: "Connection Error",
};

/**
 * Create initial connection state
 */
export function createConnectionState(serverUrl: string): ConnectionState {
  return {
    status: "disconnected",
    serverUrl,
    retryCount: 0,
  };
}

/**
 * Check if connection is usable for sending messages
 */
export function canSendMessages(state: ConnectionState): boolean {
  return state.status === "connected";
}
