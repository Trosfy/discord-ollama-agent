import { useState, useEffect, useCallback, useRef } from "react";
import { authenticatedFetch } from "@/infrastructure/api/FetchClient";

export interface MemoryStats {
  usage: string;      // e.g., "1.2GiB / 15.5GiB"
  percentage: string; // e.g., "7.74%"
}

export interface DockerContainer {
  name: string;
  status: string;
  state: "running" | "exited" | "paused" | "restarting";
  image: string;
  healthy: boolean;
  memory: MemoryStats | null;
}

interface UseDockerContainersReturn {
  containers: DockerContainer[];
  loading: boolean;
  error: string | null;
  transitioning: Map<string, "starting" | "stopping">;  // Container names and their action
  startContainer: (name: string) => Promise<void>;
  stopContainer: (name: string) => Promise<void>;
  refresh: () => Promise<void>;
}

const ADMIN_API_URL = process.env.NEXT_PUBLIC_ADMIN_API_URL || "http://localhost:8003";

export function useDockerContainers(autoRefresh = true): UseDockerContainersReturn {
  const [containers, setContainers] = useState<DockerContainer[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [transitioning, setTransitioning] = useState<Map<string, "starting" | "stopping">>(new Map());
  const hasLoadedRef = useRef(false);

  const fetchContainers = useCallback(async () => {
    try {
      // Only show loading spinner on initial fetch, not on refreshes
      const isInitialLoad = !hasLoadedRef.current;
      if (isInitialLoad) {
        setLoading(true);
      }
      setError(null);

      const response = await authenticatedFetch(
        `${ADMIN_API_URL}/admin/system/docker/containers`
      );

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();
      setContainers(data.containers || []);

      // Mark as loaded and hide loading spinner
      if (isInitialLoad) {
        setLoading(false);
        hasLoadedRef.current = true;
      }
    } catch (err) {
      // If it's a session expired error, don't show error message
      // (user will be redirected to login automatically)
      if (err instanceof Error && err.message === 'Session expired') {
        return;
      }

      console.error("Failed to fetch containers:", err);
      setError(err instanceof Error ? err.message : "Failed to fetch containers");

      // Mark as loaded even on error
      if (!hasLoadedRef.current) {
        setLoading(false);
        hasLoadedRef.current = true;
      }
    }
  }, []);

  const startContainer = useCallback(async (name: string) => {
    // Mark container as transitioning with action type
    setTransitioning(prev => new Map(prev).set(name, "starting"));

    try {
      setError(null);
      const response = await authenticatedFetch(
        `${ADMIN_API_URL}/admin/system/docker/containers/${name}/start`,
        {
          method: "POST",
        }
      );

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || "Failed to start container");
      }

      // Refresh container list after short delay to allow container to start
      setTimeout(fetchContainers, 1000);
    } catch (err) {
      if (err instanceof Error && err.message === 'Session expired') {
        return;
      }
      console.error(`Failed to start ${name}:`, err);
      setError(err instanceof Error ? err.message : `Failed to start ${name}`);
      throw err;
    } finally {
      // Remove from transitioning after request completes
      setTransitioning(prev => {
        const next = new Map(prev);
        next.delete(name);
        return next;
      });
    }
  }, [fetchContainers]);

  const stopContainer = useCallback(async (name: string) => {
    // Mark container as transitioning with action type
    setTransitioning(prev => new Map(prev).set(name, "stopping"));

    try {
      setError(null);
      const response = await authenticatedFetch(
        `${ADMIN_API_URL}/admin/system/docker/containers/${name}/stop`,
        {
          method: "POST",
        }
      );

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || "Failed to stop container");
      }

      // Refresh container list after short delay to allow container to stop
      setTimeout(fetchContainers, 1000);
    } catch (err) {
      if (err instanceof Error && err.message === 'Session expired') {
        return;
      }
      console.error(`Failed to stop ${name}:`, err);
      setError(err instanceof Error ? err.message : `Failed to stop ${name}`);
      throw err;
    } finally {
      // Remove from transitioning after request completes
      setTransitioning(prev => {
        const next = new Map(prev);
        next.delete(name);
        return next;
      });
    }
  }, [fetchContainers]);

  // Initial fetch
  useEffect(() => {
    fetchContainers();
  }, [fetchContainers]);

  // Auto-refresh every 10 seconds
  useEffect(() => {
    if (!autoRefresh) return;

    const interval = setInterval(fetchContainers, 10000);
    return () => clearInterval(interval);
  }, [autoRefresh, fetchContainers]);

  return {
    containers,
    loading,
    error,
    transitioning,
    startContainer,
    stopContainer,
    refresh: fetchContainers,
  };
}
