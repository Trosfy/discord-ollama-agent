"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useConversationStore } from "@/stores/conversationStore";
import { useAuthStore } from "@/stores/authStore";
import { closeConversation } from "@/infrastructure/api/ConversationApiService";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import {
  Archive,
  MessageSquare,
  RotateCcw,
  Trash2,
  ArrowLeft,
  Loader2,
} from "lucide-react";

/**
 * Archived Chats Page
 *
 * View and manage archived conversations.
 * Users can restore conversations back to active status or permanently delete them.
 */
export default function ArchivedChatsPage() {
  const router = useRouter();
  const { conversations, updateConversation, deleteConversation } = useConversationStore();
  const { user } = useAuthStore();
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [restoringId, setRestoringId] = useState<string | null>(null);

  // Filter archived conversations
  const archivedConversations = conversations
    .filter((c) => c.archived)
    .sort((a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime());

  const handleRestore = async (id: string) => {
    setRestoringId(id);
    try {
      // Update conversation to unarchived
      updateConversation(id, { archived: false });
      toast.success("Conversation restored", {
        description: "Conversation moved back to your chat list",
      });
    } catch (error) {
      console.error("Failed to restore conversation:", error);
      toast.error("Failed to restore conversation");
    } finally {
      setRestoringId(null);
    }
  };

  const handleDelete = async (id: string) => {
    // Confirm deletion
    if (!confirm("Are you sure you want to permanently delete this conversation? This action cannot be undone.")) {
      return;
    }

    setDeletingId(id);
    try {
      // Call backend to delete from DynamoDB
      const result = await closeConversation(id, user?.id || "anonymous");

      if (result.success) {
        // Remove from local store
        deleteConversation(id);

        toast.success("Conversation permanently deleted", {
          description: result.deletedCount
            ? `Deleted ${result.deletedCount} messages`
            : "Conversation removed",
        });
      } else {
        toast.error("Failed to delete conversation", {
          description: result.error || "Unknown error",
        });
      }
    } catch (err) {
      console.error("Delete error:", err);
      toast.error("Failed to delete conversation", {
        description: "An unexpected error occurred",
      });
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <div className="container mx-auto p-4 sm:p-6 lg:p-8 space-y-6 sm:space-y-8">
      {/* Back Button & Count */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Archive className="h-4 w-4" />
          <span>
            {archivedConversations.length} archived conversation{archivedConversations.length !== 1 ? "s" : ""}
          </span>
        </div>
        <Button variant="outline" size="sm" onClick={() => router.push("/chat")}>
          <ArrowLeft className="w-4 h-4 mr-2" />
          Back to Chat
        </Button>
      </div>

      {/* Empty State */}
      {archivedConversations.length === 0 ? (
        <Card>
          <CardContent className="py-16 text-center">
            <Archive className="w-16 h-16 mx-auto mb-4 text-muted-foreground/50" />
            <h2 className="text-xl font-semibold mb-2">No Archived Conversations</h2>
            <p className="text-muted-foreground mb-6">
              Conversations you archive will appear here. You can restore or permanently delete them.
            </p>
            <Button variant="default" onClick={() => router.push("/chat")}>
              <MessageSquare className="w-4 h-4 mr-2" />
              Go to Chat
            </Button>
          </CardContent>
        </Card>
      ) : (
        /* Archived Conversations List */
        <div className="space-y-3">
          {archivedConversations.map((conversation) => {
            const isDeleting = deletingId === conversation.id;
            const isRestoring = restoringId === conversation.id;
            const isProcessing = isDeleting || isRestoring;

            return (
              <Card
                key={conversation.id}
                className="hover:shadow-md transition-shadow duration-200"
              >
                <CardContent className="p-4">
                  <div className="flex items-start gap-3">
                    {/* Icon */}
                    <MessageSquare className="w-5 h-5 text-muted-foreground shrink-0 mt-0.5" />

                    {/* Content */}
                    <div className="flex-1 min-w-0">
                      <h3 className="font-semibold text-foreground truncate mb-1">
                        {conversation.title}
                      </h3>
                      <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                        <span>
                          Archived on {new Date(conversation.updatedAt).toLocaleDateString()}
                        </span>
                        {conversation.messages && conversation.messages.length > 0 && (
                          <>
                            <span>•</span>
                            <span>{conversation.messages.length} messages</span>
                          </>
                        )}
                      </div>
                    </div>

                    {/* Actions */}
                    <div className="flex flex-col sm:flex-row gap-2 shrink-0">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleRestore(conversation.id)}
                        disabled={isProcessing}
                        className="gap-2"
                      >
                        {isRestoring ? (
                          <>
                            <Loader2 className="w-4 h-4 animate-spin" />
                            Restoring...
                          </>
                        ) : (
                          <>
                            <RotateCcw className="w-4 h-4" />
                            <span className="hidden sm:inline">Restore</span>
                          </>
                        )}
                      </Button>
                      <Button
                        variant="destructive"
                        size="sm"
                        onClick={() => handleDelete(conversation.id)}
                        disabled={isProcessing}
                        className="gap-2"
                      >
                        {isDeleting ? (
                          <>
                            <Loader2 className="w-4 h-4 animate-spin" />
                            Deleting...
                          </>
                        ) : (
                          <>
                            <Trash2 className="w-4 h-4" />
                            <span className="hidden sm:inline">Delete</span>
                          </>
                        )}
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}

      {/* Info Card */}
      {archivedConversations.length > 0 && (
        <Card className="bg-muted/50">
          <CardContent className="p-4">
            <p className="text-sm text-muted-foreground">
              <strong>Note:</strong> Restoring a conversation will move it back to your active chat
              list. Deleted conversations are permanently removed from the server and cannot be recovered.
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
