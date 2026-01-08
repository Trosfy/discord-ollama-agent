import { useCallback } from "react";
import { authenticatedFetch } from "@/infrastructure/api/FetchClient";

const ADMIN_API_URL = process.env.NEXT_PUBLIC_ADMIN_API_URL || "http://localhost:8003";

export function useModelManagement() {
  const loadModel = useCallback(async (modelId: string) => {
    try {
      const response = await authenticatedFetch(
        `${ADMIN_API_URL}/admin/models/load`,
        {
          method: "POST",
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ model_id: modelId }),
        }
      );

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || "Failed to load model");
      }

      return await response.json();
    } catch (err) {
      if (err instanceof Error && err.message === 'Session expired') {
        return;
      }
      console.error(`Failed to load model ${modelId}:`, err);
      throw err;
    }
  }, []);

  const unloadModel = useCallback(async (modelId: string) => {
    try {
      const response = await authenticatedFetch(
        `${ADMIN_API_URL}/admin/models/unload`,
        {
          method: "POST",
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ model_id: modelId }),
        }
      );

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || "Failed to unload model");
      }

      return await response.json();
    } catch (err) {
      if (err instanceof Error && err.message === 'Session expired') {
        return;
      }
      console.error(`Failed to unload model ${modelId}:`, err);
      throw err;
    }
  }, []);

  return {
    loadModel,
    unloadModel,
  };
}
