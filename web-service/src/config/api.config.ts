/**
 * API Configuration
 *
 * Central configuration for all API endpoints and settings.
 * Part of the Config Layer (SOLID Architecture)
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001";
const WS_BASE_URL = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8001";
const AUTH_BASE_URL = process.env.NEXT_PUBLIC_AUTH_URL || "http://localhost:8002";
const ADMIN_BASE_URL = process.env.NEXT_PUBLIC_ADMIN_API_URL || "http://localhost:8003";

export const API_CONFIG = {
  // Base URLs
  BASE_URL: API_BASE_URL,
  WS_BASE_URL: WS_BASE_URL,
  AUTH_BASE_URL: AUTH_BASE_URL,
  ADMIN_BASE_URL: ADMIN_BASE_URL,

  // Endpoints
  ENDPOINTS: {
    // Authentication
    AUTH: {
      LOGIN: `${AUTH_BASE_URL}/login`,
      REGISTER: `${AUTH_BASE_URL}/register`,
      REFRESH: `${AUTH_BASE_URL}/refresh`,
      LINK_AUTH_METHOD: `${AUTH_BASE_URL}/link-auth-method`,
      HEALTH: `${AUTH_BASE_URL}/health`,
    },

    // Chat
    CHAT: {
      SEND: `${API_BASE_URL}/api/chat/send`,
      STATUS: (requestId: string) => `${API_BASE_URL}/api/chat/status/${requestId}`,
      CONVERSATION: (conversationId: string) => `${API_BASE_URL}/api/chat/conversation/${conversationId}`,
      LIST: (userId: string) => `${API_BASE_URL}/api/chat/conversations/${userId}`,
      CREATE: `${API_BASE_URL}/api/chat/conversation`,
      DELETE: (conversationId: string) => `${API_BASE_URL}/api/chat/conversation/${conversationId}`,
      REGENERATE: (conversationId: string, messageId: string) =>
        `${API_BASE_URL}/api/chat/conversation/${conversationId}/message/${messageId}/regenerate`,
    },

    // WebSocket (TROISE-AI compatible)
    WS: {
      CHAT: (sessionId: string, userId: string, token?: string) => {
        const base = `${WS_BASE_URL}/ws/chat?session_id=${sessionId}&user_id=${userId}&interface=web`;
        return token ? `${base}&token=${encodeURIComponent(token)}` : base;
      },
    },

    // File uploads (TROISE-AI compatible)
    FILES: {
      UPLOAD: `${API_BASE_URL}/files/upload`,
      MODELS: `${API_BASE_URL}/models`,  // Get available models for dropdown
    },

    // SSE
    SSE: {
      MONITORING: `${ADMIN_BASE_URL}/admin/monitoring/stream`,
    },

    // Admin
    ADMIN: {
      MODELS: {
        LIST: `${ADMIN_BASE_URL}/admin/models/list`,
        LOADED: `${ADMIN_BASE_URL}/admin/models/loaded`,
        LOAD: `${ADMIN_BASE_URL}/admin/models/load`,
        UNLOAD: `${ADMIN_BASE_URL}/admin/models/unload`,
        EVICT: `${ADMIN_BASE_URL}/admin/models/evict`,
      },
      VRAM: {
        STATUS: `${ADMIN_BASE_URL}/admin/vram/status`,
        HEALTH: `${ADMIN_BASE_URL}/admin/vram/health`,
        MODEL: (modelId: string) => `${ADMIN_BASE_URL}/admin/vram/models/${modelId}`,
      },
      USERS: {
        LIST: `${ADMIN_BASE_URL}/admin/users/list`,
        GET: (userId: string) => `${ADMIN_BASE_URL}/admin/users/${userId}`,
        GRANT_TOKENS: (userId: string) => `${ADMIN_BASE_URL}/admin/users/${userId}/grant-tokens`,
        BAN: (userId: string) => `${ADMIN_BASE_URL}/admin/users/${userId}/ban`,
        UNBAN: (userId: string) => `${ADMIN_BASE_URL}/admin/users/${userId}/unban`,
      },
      SYSTEM: {
        HEALTH: `${ADMIN_BASE_URL}/admin/system/health`,
        MAINTENANCE: `${ADMIN_BASE_URL}/admin/system/maintenance`,
        QUEUE_STATS: `${ADMIN_BASE_URL}/admin/system/queue/stats`,
        QUEUE_PURGE: `${ADMIN_BASE_URL}/admin/system/queue/purge`,
        DOCKER_CONTAINERS: `${ADMIN_BASE_URL}/admin/system/docker/containers`,
        DOCKER_START: (containerName: string) => `${ADMIN_BASE_URL}/admin/system/docker/containers/${containerName}/start`,
        DOCKER_STOP: (containerName: string) => `${ADMIN_BASE_URL}/admin/system/docker/containers/${containerName}/stop`,
      },
      METRICS: {
        HISTORY: `${ADMIN_BASE_URL}/admin/metrics/history`,
        SUMMARY: `${ADMIN_BASE_URL}/admin/metrics/summary`,
      },
      LOGS: {
        DATES: `${ADMIN_BASE_URL}/admin/logs/dates`,
        CONTENT: `${ADMIN_BASE_URL}/admin/logs/content`,
        SEARCH: `${ADMIN_BASE_URL}/admin/logs/search`,
      },
    },
  },

  // Timeouts
  TIMEOUTS: {
    DEFAULT: 30000, // 30 seconds
    UPLOAD: 120000, // 2 minutes
    LONG_POLL: 300000, // 5 minutes
  },

  // Polling
  POLLING: {
    INTERVAL: 2000, // 2 seconds
    MAX_ATTEMPTS: 150, // 5 minutes total (150 * 2s)
  },

  // File upload
  UPLOAD: {
    MAX_SIZE: 10 * 1024 * 1024, // 10MB
    ALLOWED_TYPES: [
      "image/jpeg",
      "image/png",
      "image/gif",
      "image/webp",
      "application/pdf",
      "text/plain",
      "text/markdown",
      "application/json",
      "text/javascript",
      "text/typescript",
    ],
  },
} as const;

export default API_CONFIG;
