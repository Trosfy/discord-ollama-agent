"use client";

import { useState, useEffect } from "react";
import { toast } from "sonner";

interface User {
  user_id: string;
  username?: string;
  tokens_remaining: number;
  tokens_used: number;
  is_banned: boolean;
  created_at?: string;
  last_active?: string;
}

// Use admin-service endpoint (port 8003)
const ADMIN_API_URL = process.env.NEXT_PUBLIC_ADMIN_API_URL || "http://localhost:8003";

export function UsersManager() {
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedUser, setSelectedUser] = useState<User | null>(null);
  const [tokenAmount, setTokenAmount] = useState("1000");
  const [showGrantModal, setShowGrantModal] = useState(false);

  useEffect(() => {
    fetchUsers();
  }, []);

  const fetchUsers = async () => {
    try {
      const response = await fetch(`${ADMIN_API_URL}/admin/users`, {
        credentials: "include",
      });
      if (response.ok) {
        const data = await response.json();
        setUsers(data.users || []);
      }
    } catch (error) {
      console.error("Failed to fetch users:", error);
      toast.error("Failed to fetch users");
    } finally {
      setLoading(false);
    }
  };

  const grantTokens = async () => {
    if (!selectedUser) return;

    try {
      const response = await fetch(
        `${ADMIN_API_URL}/admin/users/grant-tokens`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify({
            user_id: selectedUser.user_id,
            amount: parseInt(tokenAmount),
          }),
        }
      );

      if (response.ok) {
        toast.success(`Granted ${tokenAmount} tokens to user`);
        setShowGrantModal(false);
        await fetchUsers();
      } else {
        const error = await response.json();
        toast.error(`Failed to grant tokens: ${error.detail || "Unknown error"}`);
      }
    } catch (error) {
      toast.error("Failed to grant tokens");
    }
  };

  const banUser = async (userId: string) => {
    try {
      const response = await fetch(
        `${ADMIN_API_URL}/admin/users/${encodeURIComponent(userId)}/ban`,
        {
          method: "POST",
          credentials: "include",
        }
      );

      if (response.ok) {
        toast.success("User banned successfully");
        await fetchUsers();
      } else {
        const error = await response.json();
        toast.error(`Failed to ban user: ${error.detail || "Unknown error"}`);
      }
    } catch (error) {
      toast.error("Failed to ban user");
    }
  };

  const unbanUser = async (userId: string) => {
    try {
      const response = await fetch(
        `${ADMIN_API_URL}/admin/users/${encodeURIComponent(
          userId
        )}/unban`,
        {
          method: "POST",
          credentials: "include",
        }
      );

      if (response.ok) {
        toast.success("User unbanned successfully");
        await fetchUsers();
      } else {
        const error = await response.json();
        toast.error(`Failed to unban user: ${error.detail || "Unknown error"}`);
      }
    } catch (error) {
      toast.error("Failed to unban user");
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-400">Loading users...</div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-2xl font-semibold text-white">User Management</h2>
        <button
          onClick={fetchUsers}
          className="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded transition-colors"
        >
          Refresh
        </button>
      </div>

      {/* Users Table */}
      <div className="bg-gray-800/50 rounded-lg border border-gray-700 overflow-hidden">
        <table className="w-full">
          <thead className="bg-gray-900/50">
            <tr>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase">
                User ID
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase">
                Username
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase">
                Tokens Remaining
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase">
                Tokens Used
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase">
                Status
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase">
                Actions
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-700">
            {users.map((user) => (
              <tr key={user.user_id} className="hover:bg-gray-900/30">
                <td className="px-4 py-3 text-sm text-gray-300">
                  {user.user_id.substring(0, 12)}...
                </td>
                <td className="px-4 py-3 text-sm text-white">
                  {user.username || "Unknown"}
                </td>
                <td className="px-4 py-3 text-sm text-gray-300">
                  {user.tokens_remaining.toLocaleString()}
                </td>
                <td className="px-4 py-3 text-sm text-gray-300">
                  {user.tokens_used.toLocaleString()}
                </td>
                <td className="px-4 py-3 text-sm">
                  {user.is_banned ? (
                    <span className="px-2 py-1 rounded text-xs font-medium text-red-400 bg-red-400/10">
                      Banned
                    </span>
                  ) : (
                    <span className="px-2 py-1 rounded text-xs font-medium text-green-400 bg-green-400/10">
                      Active
                    </span>
                  )}
                </td>
                <td className="px-4 py-3 text-sm">
                  <div className="flex gap-2">
                    <button
                      onClick={() => {
                        setSelectedUser(user);
                        setShowGrantModal(true);
                      }}
                      className="px-3 py-1 bg-blue-600 hover:bg-blue-700 text-white rounded text-xs transition-colors"
                    >
                      Grant Tokens
                    </button>
                    {user.is_banned ? (
                      <button
                        onClick={() => unbanUser(user.user_id)}
                        className="px-3 py-1 bg-green-600 hover:bg-green-700 text-white rounded text-xs transition-colors"
                      >
                        Unban
                      </button>
                    ) : (
                      <button
                        onClick={() => banUser(user.user_id)}
                        className="px-3 py-1 bg-red-600 hover:bg-red-700 text-white rounded text-xs transition-colors"
                      >
                        Ban
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {users.length === 0 && (
        <div className="text-center py-12 text-gray-400">No users found</div>
      )}

      {/* Grant Tokens Modal */}
      {showGrantModal && selectedUser && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-gray-800 rounded-lg p-6 max-w-md w-full border border-gray-700">
            <h3 className="text-xl font-semibold text-white mb-4">
              Grant Tokens
            </h3>
            <div className="mb-4">
              <label className="block text-sm text-gray-400 mb-2">
                User: {selectedUser.username || selectedUser.user_id}
              </label>
              <label className="block text-sm text-gray-400 mb-2">
                Token Amount
              </label>
              <input
                type="number"
                value={tokenAmount}
                onChange={(e) => setTokenAmount(e.target.value)}
                className="w-full px-4 py-2 bg-gray-900 border border-gray-700 rounded text-white focus:outline-none focus:border-blue-500"
                placeholder="Enter token amount"
              />
            </div>
            <div className="flex gap-2 justify-end">
              <button
                onClick={() => setShowGrantModal(false)}
                className="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={grantTokens}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded transition-colors"
              >
                Grant Tokens
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
