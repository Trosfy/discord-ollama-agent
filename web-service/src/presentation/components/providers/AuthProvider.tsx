"use client";

/**
 * Auth Provider
 *
 * Client-side authentication provider that checks auth status on mount.
 * Redirects to login if not authenticated.
 */

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";

// Public routes that don't require authentication
const PUBLIC_ROUTES = ["/login", "/api/health"];

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { isAuthenticated, checkAuth } = useAuth();
  const [isChecking, setIsChecking] = useState(true);

  useEffect(() => {
    const verifyAuth = async () => {
      // Skip auth check for public routes
      if (PUBLIC_ROUTES.some((route) => pathname.startsWith(route))) {
        setIsChecking(false);
        return;
      }

      // Check authentication
      const isAuth = await checkAuth();

      if (!isAuth) {
        router.push("/login");
      }

      setIsChecking(false);
    };

    verifyAuth();
  }, [pathname, checkAuth, router]);

  // Show loading state while checking auth
  if (isChecking) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto mb-4"></div>
          <p className="text-muted-foreground">Loading...</p>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
