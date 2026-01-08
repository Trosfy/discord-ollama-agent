/**
 * Auth Layout
 *
 * Layout for authentication pages (login, register, etc.)
 * Centered, minimal design.
 */

import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Login - Trollama",
  description: "Sign in to Trollama",
};

export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-screen flex items-center justify-center bg-background p-4">
      <div className="w-full max-w-md">
        {/* Logo/Brand */}
        <div className="text-center mb-8">
          <div className="flex items-center justify-center gap-3 mb-2">
            <img
              src="/trollama-badge-no-bg.svg"
              alt="Trollama"
              className="h-10 w-10"
            />
            <h1 className="text-4xl font-bold text-foreground mb-0">
              Trollama
            </h1>
          </div>
          <p className="text-muted-foreground">
            Homelab AI Workspace
          </p>
        </div>

        {/* Auth content */}
        {children}
      </div>
    </div>
  );
}
