/**
 * useAuth Hook
 *
 * Custom hook for authentication operations.
 * Part of the Presentation Layer (SOLID Architecture)
 */

import { useRouter } from "next/navigation";
import { useAuthStore } from "@/stores/authStore";
import { authApiService } from "@/infrastructure/api/AuthApiService";
import { LoginRequest } from "@/domain/interfaces/IAuthService";
import { useState } from "react";

export function useAuth() {
  const router = useRouter();
  const { user, accessToken, isAuthenticated, setUser, setTokens, clearAuth, setLoading } =
    useAuthStore();
  const [error, setError] = useState<string | null>(null);

  /**
   * Login user
   */
  const login = async (username: string, password: string) => {
    try {
      setLoading(true);
      setError(null);

      const request: LoginRequest = { username, password };
      const response = await authApiService.login(request);

      if (response.success) {
        const { user, accessToken, refreshToken } = response.data;
        setUser(user);
        setTokens(accessToken, refreshToken);
        router.push("/chat");
        return { success: true };
      } else {
        setError(response.error);
        return { success: false, error: response.error };
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : "Login failed";
      setError(errorMessage);
      return { success: false, error: errorMessage };
    } finally {
      setLoading(false);
    }
  };

  /**
   * Logout user
   */
  const logout = async () => {
    try {
      await authApiService.logout();
    } catch (err) {
      console.error("Logout error:", err);
    } finally {
      clearAuth();
      router.push("/login");
    }
  };

  /**
   * Check if user is authenticated
   */
  const checkAuth = async () => {
    if (!accessToken) {
      return false;
    }

    try {
      const response = await authApiService.getCurrentUser();
      if (response.success) {
        setUser(response.data);
        return true;
      } else {
        clearAuth();
        return false;
      }
    } catch (err) {
      clearAuth();
      return false;
    }
  };

  /**
   * Refresh access token using refresh token
   * Returns new access token if successful, null otherwise
   */
  const refreshAccessToken = async (): Promise<string | null> => {
    const { refreshToken } = useAuthStore.getState();

    if (!refreshToken) {
      return null;
    }

    try {
      const response = await authApiService.refreshToken(refreshToken);

      if (response.success) {
        const { accessToken: newToken, refreshToken: newRefresh } = response.data;
        setTokens(newToken, newRefresh);
        return newToken;
      } else {
        // Refresh failed - clear auth
        clearAuth();
        return null;
      }
    } catch (err) {
      console.error("Token refresh error:", err);
      clearAuth();
      return null;
    }
  };

  return {
    user,
    accessToken,
    isAuthenticated,
    error,
    login,
    logout,
    checkAuth,
    refreshAccessToken,
  };
}
