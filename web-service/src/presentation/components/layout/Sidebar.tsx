"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useConversationStore } from "@/stores/conversationStore";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  MessageSquare,
  PanelLeftClose,
  Trash2,
  Edit2,
  Check,
  X,
  Search,
  MoreHorizontal,
  Share,
  Download,
  Pin,
  Copy,
  Archive,
  Loader2,
  Plus,
} from "lucide-react";
import { cn } from "@/lib/utils";
import {
  closeConversation,
  shareConversation,
  downloadConversation,
} from "@/infrastructure/api/ConversationApiService";
import { toast } from "sonner";

interface SidebarProps {
  isOpen: boolean;
  onToggle: () => void;
  isMobile: boolean;
}

export function Sidebar({ isOpen, onToggle, isMobile }: SidebarProps) {
  const router = useRouter();
  const {
    conversations,
    currentConversationId,
    addConversation,
    updateConversation,
    deleteConversation,
    setCurrentConversation,
  } = useConversationStore();

  const [editingId, setEditingId] = useState<string | null>(null);
  const [editingTitle, setEditingTitle] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const handleNewChat = () => {
    // Check if there's already an empty "New Chat" conversation
    const emptyNewChat = conversations.find(
      (conv) =>
        conv.title === "New Chat" &&
        !conv.archived &&
        (!conv.messages || conv.messages.length === 0)
    );

    if (emptyNewChat) {
      // Reuse existing empty conversation
      setCurrentConversation(emptyNewChat.id);
      router.push(`/chat/${emptyNewChat.id}`);
    } else {
      // Create new conversation
      const newConversation = {
        id: Date.now().toString(),
        title: "New Chat",
        createdAt: new Date(),
        updatedAt: new Date(),
        archived: false,
      };
      addConversation(newConversation);
      router.push(`/chat/${newConversation.id}`);
    }

    if (isMobile) onToggle();
  };

  const handleDeleteConversation = async (id: string, e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    
    // Show loading state
    setDeletingId(id);
    
    try {
      // Call backend to delete from DynamoDB
      const result = await closeConversation(id);
      
      if (result.success) {
        // Remove from local store
        deleteConversation(id);
        
        toast.success("Conversation deleted", {
          description: result.deletedCount 
            ? `Deleted ${result.deletedCount} messages`
            : "Conversation removed",
        });
        
        if (id === currentConversationId) {
          router.push("/chat");
        }
      } else {
        toast.error("Failed to delete", {
          description: result.error || "Unknown error",
        });
      }
    } catch (err) {
      console.error("Delete error:", err);
      toast.error("Failed to delete", {
        description: "An unexpected error occurred",
      });
    } finally {
      setDeletingId(null);
    }
  };

  const handleShare = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    shareConversation(id);
    toast.success("Link copied", {
      description: "Conversation link copied to clipboard",
    });
  };

  const handleDownload = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    const conversation = conversations.find(c => c.id === id);
    if (conversation) {
      downloadConversation(id, conversation.messages || []);
      toast.success("Downloaded", {
        description: "Conversation exported as JSON",
      });
    }
  };

  const handlePin = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    const conversation = conversations.find(c => c.id === id);
    if (conversation) {
      updateConversation(id, { pinned: !conversation.pinned });
      toast.success(conversation.pinned ? "Unpinned" : "Pinned", {
        description: conversation.pinned 
          ? "Conversation unpinned" 
          : "Conversation pinned to top",
      });
    }
  };

  const handleClone = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();

    const conversation = conversations.find(c => c.id === id);
    if (!conversation) return;

    // Create new conversation with cloned data
    const clonedConversation = {
      id: Date.now().toString(),
      title: `${conversation.title} (Copy)`,
      createdAt: new Date(),
      updatedAt: new Date(),
      archived: false, // New conversation is not archived
      pinned: false, // New conversation is not pinned
      messages: conversation.messages ? [...conversation.messages] : [], // Deep copy messages
    };

    addConversation(clonedConversation);
    router.push(`/chat/${clonedConversation.id}`);

    toast.success("Conversation cloned", {
      description: "Continue the conversation or start fresh",
    });
  };

  const handleArchive = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    const conversation = conversations.find(c => c.id === id);
    if (conversation) {
      updateConversation(id, { archived: true });
      toast.success("Archived", {
        description: "Conversation moved to archive",
      });
    }
  };

  const handleStartEdit = (id: string, currentTitle: string, e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setEditingId(id);
    setEditingTitle(currentTitle);
  };

  const handleSaveEdit = (id: string) => {
    if (editingTitle.trim()) {
      updateConversation(id, { title: editingTitle.trim() });
    }
    setEditingId(null);
    setEditingTitle("");
  };

  const handleCancelEdit = () => {
    setEditingId(null);
    setEditingTitle("");
  };

  const handleConversationClick = (id: string) => {
    setCurrentConversation(id);
    router.push(`/chat/${id}`);
    if (isMobile) onToggle();
  };

  // Filter out archived, apply search, and sort pinned to top
  const filteredConversations = conversations
    .filter((c) => !c.archived) // Hide archived
    .filter((c) => c.title.toLowerCase().includes(searchQuery.toLowerCase()))
    .sort((a, b) => {
      // Pinned items first
      if (a.pinned && !b.pinned) return -1;
      if (!a.pinned && b.pinned) return 1;
      // Sort by date (most recent first)
      return new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime();
    });

  // Group conversations by time periods
  const groupConversationsByTime = () => {
    const now = new Date();
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const yesterday = new Date(today);
    yesterday.setDate(yesterday.getDate() - 1);
    const sevenDaysAgo = new Date(today);
    sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 7);
    const thirtyDaysAgo = new Date(today);
    thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30);

    const groups: Record<string, typeof filteredConversations> = {
      Today: [],
      Yesterday: [],
      "Previous 7 days": [],
      "Previous 30 days": [],
      Older: [],
    };

    filteredConversations.forEach((conv) => {
      const convDate = new Date(conv.updatedAt);
      if (convDate >= today) {
        groups.Today.push(conv);
      } else if (convDate >= yesterday) {
        groups.Yesterday.push(conv);
      } else if (convDate >= sevenDaysAgo) {
        groups["Previous 7 days"].push(conv);
      } else if (convDate >= thirtyDaysAgo) {
        groups["Previous 30 days"].push(conv);
      } else {
        groups.Older.push(conv);
      }
    });

    // Filter out empty groups
    return Object.entries(groups).filter(([_, convs]) => convs.length > 0);
  };

  const groupedConversations = groupConversationsByTime();

  return (
    <>
      {/* Overlay for mobile */}
      {isMobile && isOpen && (
        <div
          className="fixed inset-0 bg-black/60 z-40 lg:hidden backdrop-blur-sm"
          onClick={onToggle}
        />
      )}

      {/* Sidebar */}
      <aside
        className={cn(
          "fixed lg:relative h-screen z-50 lg:z-auto",
          "bg-[var(--color-gray-900)] text-foreground",
          "flex flex-col overflow-hidden",
          "transition-all duration-300 ease-in-out",
          isOpen ? "w-64" : "w-0 lg:w-0",
          isMobile && !isOpen && "-translate-x-full"
        )}
      >
        {/* Header - close button */}
        <div className="flex items-center p-3 h-14 shrink-0">
          <Button
            variant="ghost"
            size="icon"
            className="h-10 w-10 rounded-xl hover:bg-secondary"
            onClick={onToggle}
          >
            <PanelLeftClose className="h-5 w-5" />
            <span className="sr-only">Close sidebar</span>
          </Button>
        </div>

        {/* New Chat */}
        <div className="px-2 pb-2 shrink-0">
          <button
            onClick={handleNewChat}
            className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg hover:bg-secondary/80 transition-colors text-left"
          >
            <Plus className="h-5 w-5 shrink-0" />
            <span className="text-sm font-medium">New Chat</span>
          </button>
        </div>

        {/* Search */}
        <div className="px-2 pb-2 shrink-0">
          <button className="w-full relative flex items-center gap-3 px-3 py-2.5 rounded-lg hover:bg-secondary/80 transition-colors text-left">
            <Search className="h-5 w-5 shrink-0" />
            <Input
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search"
              className="flex-1 h-auto p-0 !bg-transparent border-0 text-sm leading-none focus-visible:ring-0 focus-visible:ring-offset-0 placeholder:text-muted-foreground shadow-none"
            />
          </button>
        </div>

        {/* Divider */}
        <div className="px-2 pb-2 shrink-0">
          <div className="h-px bg-border" />
        </div>

        {/* Conversations List - Grouped by Time */}
        <div className="flex-1 overflow-y-auto px-2 scrollbar-thin">
          {filteredConversations.length === 0 ? (
            <div className="text-center py-8 text-sm text-muted-foreground px-4">
              {searchQuery ? "No matching chats" : "No conversations yet"}
            </div>
          ) : (
            <div className="space-y-4 py-1">
              {groupedConversations.map(([groupName, conversations]) => (
                <div key={groupName}>
                  {/* Group Header */}
                  <div className="px-3 py-2 text-xs font-medium text-muted-foreground uppercase tracking-wider">
                    {groupName}
                  </div>

                  {/* Conversations in Group */}
                  <div className="space-y-0.5">
                    {conversations.map((conversation) => (
                <div
                  key={conversation.id}
                  className={cn(
                    "group relative flex items-center gap-2 px-3 py-1.5 rounded-lg",
                    "hover:bg-secondary/80 cursor-pointer transition-colors",
                    conversation.id === currentConversationId && "bg-secondary"
                  )}
                  onClick={() =>
                    editingId !== conversation.id &&
                    handleConversationClick(conversation.id)
                  }
                >
                  <MessageSquare className="h-4 w-4 text-muted-foreground shrink-0" />

                  {editingId === conversation.id ? (
                    <div className="flex-1 flex items-center gap-1">
                      <Input
                        value={editingTitle}
                        onChange={(e) => setEditingTitle(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter") handleSaveEdit(conversation.id);
                          else if (e.key === "Escape") handleCancelEdit();
                        }}
                        className="h-7 text-sm"
                        autoFocus
                        onClick={(e) => e.stopPropagation()}
                      />
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7 text-green-500"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleSaveEdit(conversation.id);
                        }}
                      >
                        <Check className="h-3.5 w-3.5" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleCancelEdit();
                        }}
                      >
                        <X className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                  ) : (
                    <>
                      <span className="flex-1 truncate text-sm leading-none">
                        {conversation.title}
                      </span>

                      {/* More actions dropdown - always visible */}
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button
                            variant="ghost"
                            size="icon"
                            className="!h-5 !w-5 opacity-60 hover:opacity-100 shrink-0"
                            onClick={(e) => e.stopPropagation()}
                            title="More"
                            disabled={deletingId === conversation.id}
                          >
                            {deletingId === conversation.id ? (
                              <Loader2 className="h-3 w-3 animate-spin" />
                            ) : (
                              <MoreHorizontal className="h-3 w-3" />
                            )}
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end" className="w-40">
                          <DropdownMenuItem onClick={(e) => handleShare(conversation.id, e)}>
                            <Share className="h-4 w-4 mr-2" />
                            Share
                          </DropdownMenuItem>
                          <DropdownMenuItem onClick={(e) => handleDownload(conversation.id, e)}>
                            <Download className="h-4 w-4 mr-2" />
                            Download
                          </DropdownMenuItem>
                          <DropdownMenuItem onClick={(e) => {
                            e.stopPropagation();
                            handleStartEdit(conversation.id, conversation.title, e);
                          }}>
                            <Edit2 className="h-4 w-4 mr-2" />
                            Rename
                          </DropdownMenuItem>
                          <DropdownMenuItem onClick={(e) => handlePin(conversation.id, e)}>
                            <Pin className="h-4 w-4 mr-2" />
                            {conversations.find(c => c.id === conversation.id)?.pinned ? "Unpin" : "Pin"}
                          </DropdownMenuItem>
                          <DropdownMenuItem onClick={(e) => handleClone(conversation.id, e)}>
                            <Copy className="h-4 w-4 mr-2" />
                            Clone
                          </DropdownMenuItem>
                          <DropdownMenuItem onClick={(e) => handleArchive(conversation.id, e)}>
                            <Archive className="h-4 w-4 mr-2" />
                            Archive
                          </DropdownMenuItem>
                          <DropdownMenuSeparator />
                          <DropdownMenuItem 
                            onClick={(e) => handleDeleteConversation(conversation.id, e)}
                            className="text-destructive focus:text-destructive"
                            disabled={deletingId === conversation.id}
                          >
                            {deletingId === conversation.id ? (
                              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                            ) : (
                              <Trash2 className="h-4 w-4 mr-2" />
                            )}
                            Delete
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </>
                  )}
                </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </aside>
    </>
  );
}
