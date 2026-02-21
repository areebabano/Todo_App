"use client";

import React, { useState, useRef, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  sendMessage,
  StreamEvent,
  getConversations,
  getMessages,
  saveActiveConversationId,
  clearSavedConversationId,
  getSavedConversationId,
} from "@/lib/api/chat";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  isStreaming?: boolean;
  toolName?: string;
}

interface ChatInterfaceProps {
  compact?: boolean;
}

const THEME_COLORS = ["#8b5cf6", "#f43f5e", "#f59e0b", "#10b981"];

/**
 * Render simple inline markdown (bold, italic, strikethrough, inline code)
 * into React elements. Avoids needing a full markdown library.
 */
function renderSimpleMarkdown(text: string): React.ReactNode[] {
  const parts: React.ReactNode[] = [];
  const regex = /(\*\*(.+?)\*\*|\*(.+?)\*|~~(.+?)~~|`(.+?)`)/g;
  let lastIndex = 0;
  let match;
  let key = 0;

  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push(text.slice(lastIndex, match.index));
    }

    if (match[2]) {
      parts.push(<strong key={key++} className="font-semibold">{match[2]}</strong>);
    } else if (match[3]) {
      parts.push(<em key={key++}>{match[3]}</em>);
    } else if (match[4]) {
      parts.push(<del key={key++} className="text-slate-400">{match[4]}</del>);
    } else if (match[5]) {
      parts.push(
        <code key={key++} className="px-1 py-0.5 bg-slate-100 rounded text-xs font-mono">
          {match[5]}
        </code>
      );
    }

    lastIndex = match.index + match[0].length;
  }

  if (lastIndex < text.length) {
    parts.push(text.slice(lastIndex));
  }

  return parts.length > 0 ? parts : [text];
}

const SUGGESTED_PROMPTS = [
  {
    label: "Create a task",
    prompt: "Create a task called ",
    icon: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
      </svg>
    ),
    color: "from-brand-500 to-indigo-500",
    bg: "bg-brand-50",
    border: "border-brand-200",
    text: "text-brand-700",
  },
  {
    label: "Show my tasks",
    prompt: "Show me all my tasks",
    icon: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 10h16M4 14h16M4 18h16" />
      </svg>
    ),
    color: "from-accent-rose-500 to-pink-500",
    bg: "bg-accent-rose-50",
    border: "border-accent-rose-200",
    text: "text-accent-rose-700",
  },
  {
    label: "What's left?",
    prompt: "What tasks do I still need to complete?",
    icon: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    ),
    color: "from-accent-amber-500 to-orange-500",
    bg: "bg-accent-amber-50",
    border: "border-accent-amber-200",
    text: "text-accent-amber-700",
  },
  {
    label: "Complete a task",
    prompt: "Mark my latest task as complete",
    icon: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
      </svg>
    ),
    color: "from-accent-emerald-500 to-teal-500",
    bg: "bg-accent-emerald-50",
    border: "border-accent-emerald-200",
    text: "text-accent-emerald-700",
  },
];

// Thinking indicator
function ThinkingIndicator({ compact }: { compact: boolean }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -8 }}
      className={`flex items-center gap-2.5 ${compact ? "py-1" : "py-1.5"}`}
    >
      <div className="relative">
        <motion.div
          animate={{ rotate: 360 }}
          transition={{ duration: 4, repeat: Infinity, ease: "linear" }}
          className="absolute inset-[-2px] rounded-full opacity-40"
          style={{
            background: "linear-gradient(135deg, #8b5cf6, #f43f5e, #f59e0b, #10b981)",
          }}
        />
        <motion.div
          animate={{ scale: [1, 1.15, 1] }}
          transition={{ duration: 1.5, repeat: Infinity, ease: "easeInOut" }}
          className="relative w-6 h-6 rounded-full bg-white flex items-center justify-center"
        >
          <svg className="w-3.5 h-3.5 text-brand-500" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904 9 18.75l-.813-2.846a4.5 4.5 0 0 0-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 0 0 3.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 0 0 3.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 0 0-3.09 3.09Z" />
          </svg>
        </motion.div>
      </div>
      <div className="flex items-center gap-1.5">
        <motion.span
          animate={{ opacity: [0.5, 1, 0.5] }}
          transition={{ duration: 1.8, repeat: Infinity, ease: "easeInOut" }}
          className="text-xs font-semibold bg-clip-text text-transparent bg-gradient-to-r from-brand-500 via-accent-rose-500 to-accent-amber-500"
        >
          Thinking
        </motion.span>
        <div className="flex gap-0.5">
          {THEME_COLORS.map((color, i) => (
            <motion.span
              key={i}
              animate={{ y: [0, -4, 0], scale: [0.8, 1.2, 0.8] }}
              transition={{ duration: 0.7, repeat: Infinity, delay: i * 0.12, ease: "easeInOut" }}
              className="w-1.5 h-1.5 rounded-full"
              style={{ backgroundColor: color }}
            />
          ))}
        </div>
      </div>
    </motion.div>
  );
}

// Tool call indicator
function ToolCallBadge({ name, compact }: { name: string; compact: boolean }) {
  // Human-friendly tool names
  const friendlyNames: Record<string, string> = {
    create_task: "Creating task...",
    list_tasks: "Fetching tasks...",
    update_task: "Updating task...",
    delete_task: "Deleting task...",
    complete_task: "Completing task...",
    incomplete_task: "Reopening task...",
    complete_task_by_name: "Completing task...",
    delete_task_by_name: "Deleting task...",
    greeting: "Preparing...",
  };
  const displayName = friendlyNames[name] || name;

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.8, x: -10 }}
      animate={{ opacity: 1, scale: 1, x: 0 }}
      exit={{ opacity: 0, scale: 0.8 }}
      transition={{ type: "spring", stiffness: 400, damping: 25 }}
      className={`flex items-center gap-2 ${compact ? "px-2.5 py-1.5" : "px-3 py-2"} rounded-xl my-1.5 relative overflow-hidden`}
      style={{
        background: "linear-gradient(135deg, rgba(139,92,246,0.08), rgba(244,63,94,0.05), rgba(16,185,129,0.08))",
        border: "1px solid rgba(139,92,246,0.15)",
      }}
    >
      <motion.div
        animate={{ x: ["-100%", "200%"] }}
        transition={{ duration: 2, repeat: Infinity, ease: "linear", repeatDelay: 1 }}
        className="absolute inset-0 w-1/3"
        style={{
          background: "linear-gradient(90deg, transparent, rgba(139,92,246,0.1), transparent)",
          transform: "skewX(-20deg)",
        }}
      />
      <div className="relative w-4 h-4 flex-shrink-0">
        <motion.div
          animate={{ rotate: 360 }}
          transition={{ duration: 1.2, repeat: Infinity, ease: "linear" }}
          className="w-4 h-4 rounded-full"
          style={{
            border: "2px solid transparent",
            borderTopColor: "#8b5cf6",
            borderRightColor: "#f43f5e",
            borderBottomColor: "#f59e0b",
          }}
        />
      </div>
      <div className="relative z-10 flex items-center gap-1.5">
        <svg className="w-3 h-3 text-brand-500" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" d="M11.42 15.17 17.25 21A2.652 2.652 0 0 0 21 17.25l-5.877-5.877M11.42 15.17l2.496-3.03c.317-.384.74-.626 1.208-.766M11.42 15.17l-4.655 5.653a2.548 2.548 0 1 1-3.586-3.586l6.837-5.63m5.108-.233c.55-.164 1.163-.188 1.743-.14a4.5 4.5 0 0 0 4.486-6.336l-3.276 3.277a3.004 3.004 0 0 1-2.25-2.25l3.276-3.276a4.5 4.5 0 0 0-6.336 4.486c.091 1.076-.071 2.264-.904 2.95l-.102.085" />
        </svg>
        <span className="text-xs font-semibold text-brand-600">{displayName}</span>
      </div>
    </motion.div>
  );
}

export default function ChatInterface({ compact = false }: ChatInterfaceProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [activeToolCall, setActiveToolCall] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const [isLoadingHistory, setIsLoadingHistory] = useState(true);

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, activeToolCall, scrollToBottom]);

  // Auto-resize textarea
  useEffect(() => {
    const el = inputRef.current;
    if (el) {
      el.style.height = "auto";
      el.style.height = Math.min(el.scrollHeight, compact ? 80 : 120) + "px";
    }
  }, [input, compact]);

  // Load chat history from database on mount
  useEffect(() => {
    let cancelled = false;

    async function loadHistory() {
      try {
        // Try the conversation saved in localStorage first
        const savedId = getSavedConversationId();
        if (savedId) {
          try {
            const msgs = await getMessages(savedId);
            if (cancelled) return;
            if (msgs && msgs.length > 0) {
              setConversationId(savedId);
              setMessages(
                msgs.map((m) => ({
                  id: m.id,
                  role: m.role as "user" | "assistant",
                  content: m.content,
                  isStreaming: false,
                }))
              );
              return;
            }
          } catch {
            // Saved conversation no longer valid – fall through
            clearSavedConversationId();
          }
        }

        // Fallback: find the most recent active conversation
        const conversations = await getConversations();
        if (cancelled) return;

        const active = conversations.find((c) => c.is_active);
        if (!active) return;

        const msgs = await getMessages(active.id);
        if (cancelled) return;

        if (msgs && msgs.length > 0) {
          setConversationId(active.id);
          saveActiveConversationId(active.id);
          setMessages(
            msgs.map((m) => ({
              id: m.id,
              role: m.role as "user" | "assistant",
              content: m.content,
              isStreaming: false,
            }))
          );
        }
      } catch (err) {
        // Non-fatal – just show an empty chat
        console.error("[chat] Failed to load history:", err);
      } finally {
        if (!cancelled) setIsLoadingHistory(false);
      }
    }

    loadHistory();
    return () => {
      cancelled = true;
    };
  }, []);

  // Safety: auto-reset loading after 45 s to prevent permanent stuck state
  useEffect(() => {
    if (!isLoading) return;
    const timer = setTimeout(() => {
      console.warn("[chat] Loading stuck for 45 s – auto-resetting");
      setIsLoading(false);
      setActiveToolCall(null);
      setMessages((prev) =>
        prev.map((m) =>
          m.isStreaming
            ? {
                ...m,
                isStreaming: false,
                content:
                  m.content ||
                  "Sorry, the request timed out. Please try again.",
              }
            : m
        )
      );
    }, 45_000);
    return () => clearTimeout(timer);
  }, [isLoading]);

  const handleClearChat = useCallback(() => {
    // Abort any active stream
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }
    setMessages([]);
    setConversationId(null);
    setIsLoading(false);
    setActiveToolCall(null);
    setInput("");
    clearSavedConversationId();
    inputRef.current?.focus();
  }, []);

  // Listen for external clear event (from FloatingChatWidget)
  useEffect(() => {
    function onClear() {
      handleClearChat();
    }
    window.addEventListener("chatbot-clear", onClear);
    return () => window.removeEventListener("chatbot-clear", onClear);
  }, [handleClearChat]);

  const handleSend = useCallback(
    (text?: string) => {
      const messageText = (text || input).trim();
      if (!messageText || isLoading) return;

      setInput("");
      setActiveToolCall(null);

      const userMsg: Message = {
        id: `user-${Date.now()}`,
        role: "user",
        content: messageText,
      };

      const assistantMsg: Message = {
        id: `assistant-${Date.now()}`,
        role: "assistant",
        content: "",
        isStreaming: true,
      };

      setMessages((prev) => [...prev, userMsg, assistantMsg]);
      setIsLoading(true);

      const controller = sendMessage(
        messageText,
        conversationId,
        (event: StreamEvent) => {
          switch (event.event) {
            case "conversation_id":
              setConversationId(event.data.conversation_id);
              saveActiveConversationId(event.data.conversation_id);
              break;

            case "text_delta":
              setActiveToolCall(null);
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantMsg.id
                    ? { ...m, content: m.content + event.data.content }
                    : m
                )
              );
              break;

            case "tool_call":
              setActiveToolCall(event.data.name);
              break;

            case "tool_output":
              setActiveToolCall(null);
              // Notify tasks page to refresh when chatbot performs operations
              window.dispatchEvent(new CustomEvent("chatbot-task-updated"));
              break;

            case "done":
              setActiveToolCall(null);
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantMsg.id
                    ? {
                        ...m,
                        content: m.content || event.data.content,
                        isStreaming: false,
                      }
                    : m
                )
              );
              setIsLoading(false);
              // Refresh tasks page in case chatbot made changes
              window.dispatchEvent(new CustomEvent("chatbot-task-updated"));
              break;

            case "error":
              setActiveToolCall(null);
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantMsg.id
                    ? {
                        ...m,
                        content: event.data.content,
                        isStreaming: false,
                      }
                    : m
                )
              );
              setIsLoading(false);
              break;
          }
        }
      );

      abortRef.current = controller;
    },
    [input, isLoading, conversationId]
  );

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const showWelcome = messages.length === 0 && !isLoadingHistory;

  return (
    <div className="flex flex-col h-full relative">
      {/* Subtle animated mesh background */}
      {!compact && (
        <div className="absolute inset-0 pointer-events-none overflow-hidden">
          <motion.div
            animate={{ opacity: [0.3, 0.5, 0.3] }}
            transition={{ duration: 8, repeat: Infinity, ease: "easeInOut" }}
            className="absolute top-0 right-0 w-64 h-64 rounded-full"
            style={{
              background: "radial-gradient(circle, rgba(139,92,246,0.06) 0%, transparent 70%)",
            }}
          />
          <motion.div
            animate={{ opacity: [0.2, 0.4, 0.2] }}
            transition={{ duration: 10, repeat: Infinity, ease: "easeInOut", delay: 2 }}
            className="absolute bottom-20 left-0 w-48 h-48 rounded-full"
            style={{
              background: "radial-gradient(circle, rgba(244,63,94,0.05) 0%, transparent 70%)",
            }}
          />
        </div>
      )}

      {/* Messages area */}
      <div className="flex-1 overflow-y-auto relative z-10">
        {showWelcome ? (
          <div className={`flex flex-col items-center justify-center h-full ${compact ? "px-3" : "px-6"} py-6`}>
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, ease: "easeOut" }}
              className="text-center w-full max-w-sm"
            >
              {/* Animated logo with rainbow ring */}
              <div className="relative mx-auto mb-5" style={{ width: compact ? 56 : 72, height: compact ? 56 : 72 }}>
                <motion.div
                  animate={{ rotate: 360 }}
                  transition={{ duration: 12, repeat: Infinity, ease: "linear" }}
                  className="absolute inset-[-3px] rounded-2xl opacity-60"
                  style={{
                    background: "linear-gradient(135deg, #8b5cf6, #f43f5e, #f59e0b, #10b981, #8b5cf6)",
                  }}
                />
                <div
                  className={`relative ${compact ? "w-14 h-14" : "w-[72px] h-[72px]"} rounded-2xl bg-brand-gradient flex items-center justify-center shadow-brand-md`}
                >
                  <motion.svg
                    animate={{ scale: [1, 1.1, 1] }}
                    transition={{ duration: 3, repeat: Infinity, ease: "easeInOut" }}
                    className={`${compact ? "w-7 h-7" : "w-9 h-9"} text-white`}
                    fill="none"
                    viewBox="0 0 24 24"
                    strokeWidth={1.5}
                    stroke="currentColor"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M9.813 15.904 9 18.75l-.813-2.846a4.5 4.5 0 0 0-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 0 0 3.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 0 0 3.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 0 0-3.09 3.09ZM18.259 8.715 18 9.75l-.259-1.035a3.375 3.375 0 0 0-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 0 0 2.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 0 0 2.455 2.456L21.75 6l-1.036.259a3.375 3.375 0 0 0-2.455 2.456ZM16.894 20.567 16.5 21.75l-.394-1.183a2.25 2.25 0 0 0-1.423-1.423L13.5 18.75l1.183-.394a2.25 2.25 0 0 0 1.423-1.423l.394-1.183.394 1.183a2.25 2.25 0 0 0 1.423 1.423l1.183.394-1.183.394a2.25 2.25 0 0 0-1.423 1.423Z"
                    />
                  </motion.svg>
                </div>
              </div>

              <h2 className={`${compact ? "text-lg" : "text-xl"} font-bold text-slate-800 mb-1`}>
                <span className="bg-clip-text text-transparent bg-gradient-to-r from-brand-600 via-accent-rose-500 to-brand-600">
                  Todo Assistant
                </span>
              </h2>
              <p className={`${compact ? "text-xs" : "text-sm"} text-slate-400 mb-5`}>
                Your AI-powered task management companion
              </p>

              {/* Rainbow divider */}
              <div className="mx-auto w-24 h-1 rounded-full bg-gradient-to-r from-brand-500 via-accent-rose-500 via-accent-amber-500 to-accent-emerald-500 opacity-40 mb-5" />

              {/* Suggested prompts grid */}
              <div className={`grid ${compact ? "grid-cols-2 gap-2" : "grid-cols-2 gap-2.5"}`}>
                {SUGGESTED_PROMPTS.map((sp, i) => (
                  <motion.button
                    key={sp.label}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.2 + i * 0.08, duration: 0.3 }}
                    whileHover={{ y: -2, scale: 1.02 }}
                    whileTap={{ scale: 0.97 }}
                    onClick={() => {
                      if (sp.prompt.endsWith(" ")) {
                        setInput(sp.prompt);
                        inputRef.current?.focus();
                      } else {
                        handleSend(sp.prompt);
                      }
                    }}
                    className={`flex items-center gap-2 ${compact ? "px-2.5 py-2" : "px-3 py-2.5"} rounded-xl border ${sp.border} ${sp.bg}
                               hover:shadow-sm transition-all duration-200 text-left`}
                  >
                    <div className={`flex-shrink-0 w-7 h-7 rounded-lg bg-gradient-to-br ${sp.color} text-white flex items-center justify-center shadow-sm`}>
                      {sp.icon}
                    </div>
                    <span className={`${compact ? "text-[11px]" : "text-xs"} font-semibold ${sp.text} leading-tight`}>
                      {sp.label}
                    </span>
                  </motion.button>
                ))}
              </div>
            </motion.div>
          </div>
        ) : (
          <div className={`${compact ? "px-3" : "px-4 sm:px-6"} py-4 space-y-3`}>
            <AnimatePresence initial={false}>
              {messages.map((msg, index) => {
                const colorIndex = index % THEME_COLORS.length;
                const isUser = msg.role === "user";

                return (
                  <motion.div
                    key={msg.id}
                    initial={{ opacity: 0, y: 12, scale: 0.97 }}
                    animate={{ opacity: 1, y: 0, scale: 1 }}
                    transition={{
                      type: "spring",
                      stiffness: 400,
                      damping: 30,
                    }}
                    className={`flex ${isUser ? "justify-end" : "justify-start"}`}
                  >
                    {/* Assistant avatar */}
                    {!isUser && (
                      <div className="flex-shrink-0 mr-2 mt-1">
                        <div className={`${compact ? "w-6 h-6" : "w-7 h-7"} rounded-lg bg-brand-gradient flex items-center justify-center shadow-sm`}>
                          <svg
                            className={`${compact ? "w-3 h-3" : "w-3.5 h-3.5"} text-white`}
                            fill="none"
                            viewBox="0 0 24 24"
                            strokeWidth={1.5}
                            stroke="currentColor"
                          >
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              d="M9.813 15.904 9 18.75l-.813-2.846a4.5 4.5 0 0 0-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 0 0 3.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 0 0 3.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 0 0-3.09 3.09Z"
                            />
                          </svg>
                        </div>
                      </div>
                    )}

                    <div
                      className={`max-w-[80%] ${compact ? "text-[13px]" : "text-sm"} ${
                        isUser
                          ? "rounded-2xl rounded-br-md px-4 py-2.5 bg-brand-gradient text-white shadow-brand-sm"
                          : "rounded-2xl rounded-bl-md px-4 py-3 bg-white/90 backdrop-blur-sm border border-slate-100 shadow-sm"
                      }`}
                    >
                      {/* Color accent bar for assistant messages */}
                      {!isUser && (
                        <div
                          className="w-8 h-0.5 rounded-full mb-2 opacity-60"
                          style={{
                            background: `linear-gradient(90deg, ${THEME_COLORS[colorIndex]}, ${THEME_COLORS[(colorIndex + 1) % THEME_COLORS.length]})`,
                          }}
                        />
                      )}

                      <div className="whitespace-pre-wrap break-words leading-relaxed">
                        {isUser ? msg.content : renderSimpleMarkdown(msg.content)}
                        {msg.isStreaming && msg.content && (
                          <motion.span
                            animate={{ opacity: [1, 0.3, 1] }}
                            transition={{ duration: 0.8, repeat: Infinity }}
                            className="inline-block w-1.5 h-4 ml-0.5 rounded-sm align-text-bottom"
                            style={{ backgroundColor: isUser ? "#fff" : THEME_COLORS[colorIndex] }}
                          />
                        )}
                      </div>

                      {/* Thinking indicator when streaming but no content yet */}
                      <AnimatePresence>
                        {msg.isStreaming && !msg.content && !activeToolCall && (
                          <ThinkingIndicator compact={compact} />
                        )}
                      </AnimatePresence>

                      {/* Tool call badge inside the streaming message */}
                      <AnimatePresence>
                        {msg.isStreaming && activeToolCall && (
                          <ToolCallBadge name={activeToolCall} compact={compact} />
                        )}
                      </AnimatePresence>
                    </div>

                    {/* User avatar */}
                    {isUser && (
                      <div className="flex-shrink-0 ml-2 mt-1">
                        <div className={`${compact ? "w-6 h-6" : "w-7 h-7"} rounded-lg bg-gradient-to-br from-accent-rose-500 to-accent-amber-500 flex items-center justify-center shadow-sm`}>
                          <svg
                            className={`${compact ? "w-3 h-3" : "w-3.5 h-3.5"} text-white`}
                            fill="none"
                            viewBox="0 0 24 24"
                            strokeWidth={1.5}
                            stroke="currentColor"
                          >
                            <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 6a3.75 3.75 0 1 1-7.5 0 3.75 3.75 0 0 1 7.5 0ZM4.501 20.118a7.5 7.5 0 0 1 14.998 0A17.933 17.933 0 0 1 12 21.75c-2.676 0-5.216-.584-7.499-1.632Z" />
                          </svg>
                        </div>
                      </div>
                    )}
                  </motion.div>
                );
              })}
            </AnimatePresence>
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Input area */}
      <div className={`relative z-10 border-t border-slate-200/60 ${compact ? "p-2.5" : "p-3 sm:p-4"}`}>
        <div className="flex items-end gap-2">
          {/* Clear chat button - only show when there are messages */}
          {messages.length > 0 && (
            <motion.button
              initial={{ opacity: 0, scale: 0.8 }}
              animate={{ opacity: 1, scale: 1 }}
              onClick={handleClearChat}
              title="New chat"
              className={`flex-shrink-0 ${compact ? "w-9 h-9" : "w-10 h-10"} rounded-xl
                         flex items-center justify-center
                         border border-slate-200 bg-white/80 text-slate-400
                         hover:text-accent-rose-500 hover:border-accent-rose-200 hover:bg-accent-rose-50
                         transition-all duration-200`}
            >
              <svg
                className={compact ? "w-4 h-4" : "w-4.5 h-4.5"}
                fill="none"
                viewBox="0 0 24 24"
                strokeWidth={1.5}
                stroke="currentColor"
              >
                <path strokeLinecap="round" strokeLinejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0 3.181 3.183a8.25 8.25 0 0 0 13.803-3.7M4.031 9.865a8.25 8.25 0 0 1 13.803-3.7l3.181 3.182" />
              </svg>
            </motion.button>
          )}

          <div className="relative flex-1">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask me anything about your tasks..."
              rows={1}
              className={`w-full resize-none rounded-xl border border-slate-200 bg-white/80 backdrop-blur-sm
                         ${compact ? "pl-3 pr-3 py-2 text-[13px]" : "pl-4 pr-4 py-2.5 text-sm"}
                         focus:outline-none focus:ring-2 focus:ring-brand-400/30 focus:border-brand-400
                         placeholder:text-slate-400 transition-all duration-200`}
            />
          </div>
          <motion.button
            onClick={() => handleSend()}
            disabled={!input.trim() || isLoading}
            whileHover={{ scale: 1.05, y: -1 }}
            whileTap={{ scale: 0.95 }}
            className={`flex-shrink-0 ${compact ? "w-9 h-9" : "w-10 h-10"} rounded-xl text-white
                       flex items-center justify-center shadow-brand-sm
                       transition-all duration-200
                       disabled:opacity-40 disabled:shadow-none`}
            style={{
              background: input.trim() && !isLoading
                ? "linear-gradient(135deg, #8b5cf6 0%, #6366f1 50%, #3b82f6 100%)"
                : "linear-gradient(135deg, #cbd5e1 0%, #94a3b8 100%)",
            }}
          >
            {isLoading ? (
              <motion.div
                animate={{ rotate: 360 }}
                transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
                className={`${compact ? "w-4 h-4" : "w-5 h-5"} rounded-full border-2 border-white/30 border-t-white`}
              />
            ) : (
              <svg
                className={compact ? "w-4 h-4" : "w-5 h-5"}
                fill="none"
                viewBox="0 0 24 24"
                strokeWidth={2}
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M6 12 3.269 3.125A59.769 59.769 0 0 1 21.485 12 59.768 59.768 0 0 1 3.27 20.875L5.999 12Zm0 0h7.5"
                />
              </svg>
            )}
          </motion.button>
        </div>

        {/* Bottom bar with animated dots */}
        <div className={`flex items-center justify-center gap-2 mt-2 ${compact ? "text-[10px]" : "text-xs"} text-slate-400`}>
          <div className="flex items-center gap-1">
            {THEME_COLORS.map((color, i) => (
              <motion.span
                key={i}
                animate={{ scale: [1, 1.3, 1] }}
                transition={{ duration: 2.5, repeat: Infinity, delay: i * 0.5 }}
                className="w-1.5 h-1.5 rounded-full"
                style={{ backgroundColor: color, opacity: 0.6 }}
              />
            ))}
          </div>
          <span>Powered by AI</span>
        </div>
      </div>
    </div>
  );
}
