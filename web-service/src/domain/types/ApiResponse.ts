/**
 * Domain Types - API Response
 *
 * Generic types for API responses across the application.
 * Part of the Domain Layer (SOLID Architecture)
 */

export type ApiResponse<T> = {
  success: true;
  data: T;
} | {
  success: false;
  error: string;
  code?: string;
};

export type PaginatedResponse<T> = {
  items: T[];
  total: number;
  page: number;
  pageSize: number;
  hasMore: boolean;
};

export type ApiError = {
  message: string;
  code: string;
  status: number;
  details?: Record<string, unknown>;
};
