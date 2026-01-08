/**
 * HTTP Client
 *
 * Configured Axios instance for API calls.
 * Part of the Infrastructure Layer (SOLID Architecture)
 */

import axios, { AxiosInstance, AxiosError, InternalAxiosRequestConfig } from "axios";
import { API_CONFIG } from "@/config/api.config";
import { STORAGE_KEYS } from "@/config/constants";

// Create Axios instance
export const httpClient: AxiosInstance = axios.create({
  baseURL: API_CONFIG.BASE_URL,
  timeout: API_CONFIG.TIMEOUTS.DEFAULT,
  headers: {
    "Content-Type": "application/json",
  },
  // Not using cookies - JWT tokens are in Authorization header
  withCredentials: false,
});

// Request interceptor - Add auth token to requests
httpClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    // Get token from localStorage
    const token = localStorage.getItem(STORAGE_KEYS.AUTH_TOKEN);

    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`;
    }

    return config;
  },
  (error: AxiosError) => {
    return Promise.reject(error);
  }
);

// Response interceptor - Handle errors and token refresh
httpClient.interceptors.response.use(
  (response) => {
    return response;
  },
  async (error: AxiosError) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean };

    // If 401 and we haven't already tried to refresh
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;

      // Try to refresh the token
      const refreshToken = localStorage.getItem(STORAGE_KEYS.REFRESH_TOKEN);

      if (refreshToken) {
        try {
          // Call refresh endpoint directly (bypass httpClient to avoid loop)
          const refreshResponse = await fetch(API_CONFIG.ENDPOINTS.AUTH.REFRESH, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify({ refresh_token: refreshToken }),
          });

          if (refreshResponse.ok) {
            const data = await refreshResponse.json();

            // Update stored access token
            localStorage.setItem(STORAGE_KEYS.AUTH_TOKEN, data.access_token);

            // Update Authorization header and retry the original request
            if (originalRequest.headers) {
              originalRequest.headers.Authorization = `Bearer ${data.access_token}`;
            }

            return httpClient(originalRequest);
          }
        } catch (refreshError) {
          console.error("Token refresh failed:", refreshError);
        }
      }

      // Refresh failed or no refresh token - clear auth and redirect
      localStorage.removeItem(STORAGE_KEYS.AUTH_TOKEN);
      localStorage.removeItem(STORAGE_KEYS.REFRESH_TOKEN);
      localStorage.removeItem(STORAGE_KEYS.USER);

      // Redirect to login page
      if (typeof window !== "undefined") {
        window.location.href = "/login";
      }
    }

    return Promise.reject(error);
  }
);

/**
 * Helper function to handle API errors
 */
export function handleApiError(error: unknown): string {
  if (axios.isAxiosError(error)) {
    // Server responded with error
    if (error.response) {
      return error.response.data?.error || error.response.data?.message || error.message;
    }

    // Request was made but no response
    if (error.request) {
      return "No response from server. Please check your connection.";
    }
  }

  // Something else happened
  if (error instanceof Error) {
    return error.message;
  }

  return "An unknown error occurred";
}

export default httpClient;
