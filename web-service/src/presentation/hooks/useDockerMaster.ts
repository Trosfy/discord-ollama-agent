import { useCallback } from "react";
import { authenticatedFetch } from "@/infrastructure/api/FetchClient";

const ADMIN_API_URL = process.env.NEXT_PUBLIC_ADMIN_API_URL || "http://localhost:8003";

export function useDockerMaster() {
  const startAll = useCallback(async () => {
    try {
      const response = await authenticatedFetch(
        `${ADMIN_API_URL}/admin/system/docker/start-all`,
        {
          method: "POST",
        }
      );

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || "Failed to start all services");
      }

      return await response.json();
    } catch (err) {
      if (err instanceof Error && err.message === 'Session expired') {
        return;
      }
      console.error("Failed to start all containers:", err);
      throw err;
    }
  }, []);

  const stopAll = useCallback(async () => {
    try {
      const response = await authenticatedFetch(
        `${ADMIN_API_URL}/admin/system/docker/stop-all`,
        {
          method: "POST",
        }
      );

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || "Failed to stop all services");
      }

      return await response.json();
    } catch (err) {
      if (err instanceof Error && err.message === 'Session expired') {
        return;
      }
      console.error("Failed to stop all containers:", err);
      throw err;
    }
  }, []);

  return {
    startAll,
    stopAll,
  };
}
