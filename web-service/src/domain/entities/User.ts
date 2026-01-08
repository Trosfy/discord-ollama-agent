/**
 * Domain Entity - User
 *
 * Represents a user in the Trollama system.
 * Part of the Domain Layer (SOLID Architecture)
 */

export type UserRole = "admin" | "user";

export interface User {
  id: string;
  username: string;
  displayName: string;
  role: UserRole;
  email?: string;
  tokensRemaining: number;
  createdAt: Date;
  lastLoginAt?: Date;
}

export interface UserPreferences {
  theme: "light" | "dark" | "system";
  defaultModel?: string;
  temperature: number;
  enableWebSearch: boolean;
  thinkingMode: "auto" | "enabled" | "disabled";
}
