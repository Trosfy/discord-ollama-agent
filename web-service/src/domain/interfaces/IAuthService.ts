/**
 * Domain Interface - IAuthService
 *
 * Defines the contract for authentication services.
 * Part of the Domain Layer (SOLID Architecture)
 *
 * Implementations:
 * - infrastructure/api/AuthApiService.ts (calls FastAPI)
 */

import { User } from "../entities/User";
import { ApiResponse } from "../types/ApiResponse";

export interface LoginRequest {
  username: string;
  password: string;
}

export interface LoginResponse {
  user: User;
  accessToken: string;
  refreshToken?: string;
  expiresIn: number;
}

export interface IAuthService {
  /**
   * Authenticate user with username and password
   */
  login(request: LoginRequest): Promise<ApiResponse<LoginResponse>>;

  /**
   * Log out current user
   */
  logout(): Promise<ApiResponse<void>>;

  /**
   * Get current authenticated user
   */
  getCurrentUser(): Promise<ApiResponse<User>>;

  /**
   * Refresh authentication token
   */
  refreshToken(refreshToken: string): Promise<ApiResponse<LoginResponse>>;

  /**
   * Validate if user is authenticated
   */
  isAuthenticated(): boolean;
}
