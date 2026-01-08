"use client";

import { create } from "zustand";

interface Model {
  id: string;
  name: string;
  description: string;
}

interface ModelState {
  models: Model[];
  selectedModelId: string;
  setSelectedModelId: (id: string) => void;
  setModels: (models: Model[]) => void;
  getSelectedModel: () => Model | undefined;
}

const defaultModels: Model[] = [
  { id: "gpt-oss:120b", name: "GPT-OSS-120B", description: "120B parameter model via Ollama" },
  { id: "deepseek-r1", name: "DeepSeek R1", description: "Reasoning-focused model" },
  { id: "llama-3.3-70b", name: "Llama 3.3 70B", description: "Meta's latest open model" },
];

export const useModelStore = create<ModelState>((set, get) => ({
  models: defaultModels,
  selectedModelId: "gpt-oss:120b",
  
  setSelectedModelId: (id: string) => set({ selectedModelId: id }),
  
  setModels: (models: Model[]) => set({ models }),
  
  getSelectedModel: () => {
    const state = get();
    return state.models.find((m) => m.id === state.selectedModelId);
  },
}));
