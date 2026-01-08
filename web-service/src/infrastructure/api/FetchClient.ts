/**
 * Fetch Client with Auto-Logout on 401
 *
 * Wrapper around native fetch that:
 * - Automatically adds Authorization header
 * - Handles 401 errors by clearing auth and redirecting to login
 * - Prevents infinite redirect loops
 * - Checks token expiry before making requests
 */

import { STORAGE_KEYS } from "@/config/constants";

let isRedirecting = false;

/**
 * Decode JWT without verification to check expiry
 */
function decodeJWT(token: string): any {
  try {
    const base64Url = token.split('.')[1];
    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
    const jsonPayload = decodeURIComponent(
      atob(base64)
        .split('')
        .map((c) => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
        .join('')
    );
    return JSON.parse(jsonPayload);
  } catch (e) {
    return null;
  }
}

/**
 * Check if token is expired
 */
export function isTokenExpired(token: string | null): boolean {
  if (!token) return true;

  const payload = decodeJWT(token);
  if (!payload || !payload.exp) return true;

  const now = Date.now() / 1000;
  return payload.exp < now;
}

/**
 * Clear auth and redirect to login
 */
export function redirectToLogin(reason?: string) {
  if (isRedirecting) return;

  isRedirecting = true;

  // Clear auth state
  localStorage.removeItem(STORAGE_KEYS.AUTH_TOKEN);
  localStorage.removeItem(STORAGE_KEYS.REFRESH_TOKEN);
  localStorage.removeItem(STORAGE_KEYS.USER);

  // Show notification
  console.warn(`Session expired. Redirecting to login... (${reason || 'token expired'})`);

  // Redirect to login
  if (typeof window !== 'undefined') {
    const redirect = reason === 'expired' ? '?expired=true' : '?unauthorized=true';
    window.location.href = `/login${redirect}`;
  }
}

/**
 * Try to refresh the access token
 * Returns new token if successful, null otherwise
 */
async function tryRefreshToken(): Promise<string | null> {
  const refreshToken = localStorage.getItem(STORAGE_KEYS.REFRESH_TOKEN);
  if (!refreshToken) return null;

  try {
    const authBaseUrl = process.env.NEXT_PUBLIC_AUTH_URL || "http://localhost:8002";
    const response = await fetch(`${authBaseUrl}/refresh`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });

    if (response.ok) {
      const data = await response.json();
      localStorage.setItem(STORAGE_KEYS.AUTH_TOKEN, data.access_token);
      return data.access_token;
    }
  } catch (error) {
    console.error("Token refresh failed:", error);
  }

  return null;
}

/**
 * Enhanced fetch that handles authentication automatically
 */
export async function authenticatedFetch(
  url: string,
  options: RequestInit = {}
): Promise<Response> {
  // Get token from localStorage
  let token = localStorage.getItem(STORAGE_KEYS.AUTH_TOKEN);

  // Check if token is expired before making request
  if (isTokenExpired(token)) {
    // Try to refresh the token
    const newToken = await tryRefreshToken();
    if (newToken) {
      token = newToken;
    } else {
      redirectToLogin('expired');
      throw new Error('Session expired');
    }
  }

  // Add Authorization header if token exists
  const headers = new Headers(options.headers);
  if (token && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${token}`);
  }

  // Make request
  const response = await fetch(url, {
    ...options,
    headers,
  });

  // Handle 401 Unauthorized - try to refresh and retry once
  if (response.status === 401) {
    const newToken = await tryRefreshToken();
    if (newToken) {
      // Retry with new token
      headers.set('Authorization', `Bearer ${newToken}`);
      const retryResponse = await fetch(url, {
        ...options,
        headers,
      });
      return retryResponse;
    }

    redirectToLogin('unauthorized');
    throw new Error('Session expired');
  }

  return response;
}

/**
 * Get current access token
 */
export function getAccessToken(): string | null {
  return localStorage.getItem(STORAGE_KEYS.AUTH_TOKEN);
}

/**
 * Check if user is authenticated
 */
export function isAuthenticated(): boolean {
  const token = getAccessToken();
  return !isTokenExpired(token);
}
