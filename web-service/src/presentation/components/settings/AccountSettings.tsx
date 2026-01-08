"use client";

import { useAuth } from "@/hooks/useAuth";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { User } from "lucide-react";

/**
 * Account Settings Component
 *
 * Displays user account information (read-only for Phase 1).
 * Future: Add password change, email update, profile editing.
 */
export function AccountSettings() {
  const { user } = useAuth();

  if (!user) {
    return (
      <Card>
        <CardContent className="pt-6 text-center text-muted-foreground">
          <p>Not logged in</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <User className="h-5 w-5" />
            Profile Information
          </CardTitle>
          <CardDescription>
            View your account information
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Username */}
          <div className="space-y-2">
            <Label htmlFor="username">Username</Label>
            <Input
              id="username"
              value={user.username || "N/A"}
              disabled
              className="bg-muted"
            />
          </div>

          {/* Display Name */}
          {user.displayName && (
            <div className="space-y-2">
              <Label htmlFor="displayName">Display Name</Label>
              <Input
                id="displayName"
                value={user.displayName}
                disabled
                className="bg-muted"
              />
            </div>
          )}

          {/* Email */}
          {user.email && (
            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                value={user.email}
                disabled
                className="bg-muted"
              />
            </div>
          )}

          {/* Role */}
          <div className="space-y-2">
            <Label htmlFor="role">Role</Label>
            <Input
              id="role"
              value={user.role || "user"}
              disabled
              className="bg-muted capitalize"
            />
          </div>

          <div className="pt-2 text-sm text-muted-foreground">
            <p>
              Contact an administrator to update your account details.
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
