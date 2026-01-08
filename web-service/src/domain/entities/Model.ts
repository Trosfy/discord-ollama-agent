/**
 * Domain Entity - Model
 *
 * Represents an AI model in the Trollama system.
 * Part of the Domain Layer (SOLID Architecture)
 */

export interface Model {
  id: string;
  name: string;
  displayName: string;
  provider: "ollama" | "anthropic" | "openai" | "other";
  isLoaded: boolean;
  vramUsage?: number;
  vramTotal?: number;
  contextLength: number;
  capabilities: ModelCapabilities;
  createdAt?: Date;
}

export interface ModelCapabilities {
  chat: boolean;
  vision: boolean;
  functionCalling: boolean;
  streaming: boolean;
  thinking: boolean;
}

export interface VRAMStats {
  total: number;
  used: number;
  available: number;
  models: Array<{
    modelId: string;
    name: string;
    vramUsage: number;
  }>;
  timestamp: Date;
}
