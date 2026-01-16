/**
 * Model client interface for model-related API operations.
 */
export interface IModelClient {
  /**
   * List available models
   */
  listModels(): Promise<ModelInfo[]>;

  /**
   * Get model details
   */
  getModel(modelId: string): Promise<ModelInfo | undefined>;

  /**
   * Check if model is loaded/available
   */
  isModelLoaded(modelId: string): Promise<boolean>;
}

export interface ModelInfo {
  /** Model identifier */
  id: string;
  /** Display name */
  name: string;
  /** Model description */
  description?: string;
  /** Model size (parameters) */
  size?: string;
  /** Context window size */
  contextWindow?: number;
  /** Whether model is currently loaded */
  loaded?: boolean;
  /** Model capabilities */
  capabilities?: ModelCapabilities;
  /** Model provider (ollama, sglang, etc.) */
  provider?: string;
}

export interface ModelCapabilities {
  /** Supports tool/function calling */
  tools?: boolean;
  /** Supports vision/images */
  vision?: boolean;
  /** Supports streaming */
  streaming?: boolean;
  /** Supports code execution */
  codeExecution?: boolean;
}
