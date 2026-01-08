/**
 * Authentication API Service
 *
 * Implementation of IAuthService using HTTP API.
 * Part of the Infrastructure Layer (SOLID Architecture)
 */

import {
  IAuthService,
  LoginRequest,
  LoginResponse,
} from "@/domain/interfaces/IAuthService";
import { User } from "@/domain/entities/User";
import { ApiResponse } from "@/domain/types/ApiResponse";
import { httpClient, handleApiError } from "./HttpClient";
import { API_CONFIG } from "@/config/api.config";
import { STORAGE_KEYS } from "@/config/constants";

export class AuthApiService implements IAuthService {
  async login(request: LoginRequest): Promise<ApiResponse<LoginResponse>> {
    try {
      // Transform request to auth service format
      const authServiceRequest = {
        provider: "password",
        identifier: request.username,
        credentials: request.password,
      };

      const response = await httpClient.post<{
        access_token: string;
        refresh_token: string;
        token_type: string;
        user: {
          user_id: string;
          display_name: string;
          role: string;
          email?: string;
        };
      }>(API_CONFIG.ENDPOINTS.AUTH.LOGIN, authServiceRequest);

      // Transform response to frontend format
      const loginResponse: LoginResponse = {
        user: {
          id: response.data.user.user_id,
          username: response.data.user.display_name,
          displayName: response.data.user.display_name,
          email: response.data.user.email,
          role: response.data.user.role as "admin" | "user",
          tokensRemaining: 0, // TODO: Fetch from backend
          createdAt: new Date(),
        },
        accessToken: response.data.access_token,
        refreshToken: response.data.refresh_token,
        expiresIn: 28800, // 8 hours (matches auth-service)
      };

      // Store tokens in localStorage
      localStorage.setItem(STORAGE_KEYS.AUTH_TOKEN, loginResponse.accessToken);
      if (loginResponse.refreshToken) {
        localStorage.setItem(STORAGE_KEYS.REFRESH_TOKEN, loginResponse.refreshToken);
      }
      localStorage.setItem(STORAGE_KEYS.USER, JSON.stringify(loginResponse.user));

      // CRITICAL: Also store token in cookie for Next.js middleware auth check
      // Middleware runs server-side and can't access localStorage
      document.cookie = `trollama_auth_token=${loginResponse.accessToken}; path=/; max-age=${loginResponse.expiresIn}; SameSite=Lax`;
      if (loginResponse.refreshToken) {
        document.cookie = `trollama_refresh_token=${loginResponse.refreshToken}; path=/; max-age=2592000; SameSite=Lax`; // 30 days
      }

      return {
        success: true,
        data: loginResponse,
      };
    } catch (error) {
      return {
        success: false,
        error: handleApiError(error),
      };
    }
  }

  async logout(): Promise<ApiResponse<void>> {
    try {
      // JWT tokens are stateless, just clear local storage
      // No need to call backend logout endpoint
      localStorage.removeItem(STORAGE_KEYS.AUTH_TOKEN);
      localStorage.removeItem(STORAGE_KEYS.REFRESH_TOKEN);
      localStorage.removeItem(STORAGE_KEYS.USER);

      // Clear cookies as well
      document.cookie = "trollama_auth_token=; path=/; max-age=0";
      document.cookie = "trollama_refresh_token=; path=/; max-age=0";

      return {
        success: true,
        data: undefined,
      };
    } catch (error) {
      return {
        success: false,
        error: handleApiError(error),
      };
    }
  }

  async getCurrentUser(): Promise<ApiResponse<User>> {
    try {
      // Get user from localStorage (stored during login)
      const cachedUser = localStorage.getItem(STORAGE_KEYS.USER);
      if (cachedUser) {
        const user = JSON.parse(cachedUser);
        return {
          success: true,
          data: user,
        };
      }

      // No cached user and auth service doesn't have /me endpoint yet
      return {
        success: false,
        error: "User not authenticated",
      };
    } catch (error) {
      return {
        success: false,
        error: handleApiError(error),
      };
    }
  }

  async refreshToken(refreshToken: string): Promise<ApiResponse<LoginResponse>> {
    try {
      // Call auth-service refresh endpoint directly (bypass httpClient to avoid circular refresh)
      const response = await fetch(API_CONFIG.ENDPOINTS.AUTH.REFRESH, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ refresh_token: refreshToken }),
      });

      if (!response.ok) {
        // Refresh failed - token expired or invalid
        return {
          success: false,
          error: response.status === 401 ? "Refresh token expired" : "Token refresh failed",
        };
      }

      const data = await response.json();

      // Get existing user from localStorage
      const cachedUser = localStorage.getItem(STORAGE_KEYS.USER);
      const user = cachedUser ? JSON.parse(cachedUser) : null;

      if (!user) {
        return {
          success: false,
          error: "User data not found",
        };
      }

      // Update stored access token
      localStorage.setItem(STORAGE_KEYS.AUTH_TOKEN, data.access_token);

      // Update cookie as well
      document.cookie = `trollama_auth_token=${data.access_token}; path=/; max-age=28800; SameSite=Lax`;

      const loginResponse: LoginResponse = {
        user,
        accessToken: data.access_token,
        refreshToken, // Keep existing refresh token
        expiresIn: 28800, // 8 hours
      };

      return {
        success: true,
        data: loginResponse,
      };
    } catch (error) {
      return {
        success: false,
        error: handleApiError(error),
      };
    }
  }

  isAuthenticated(): boolean {
    const token = localStorage.getItem(STORAGE_KEYS.AUTH_TOKEN);
    return !!token;
  }
}

// Export singleton instance
export const authApiService = new AuthApiService();
