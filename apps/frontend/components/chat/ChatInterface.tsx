"use client";

import { ChatKit, useChatKit } from "@openai/chatkit-react";

/**
 * ChatInterface wraps the OpenAI ChatKit React component, configured
 * to communicate with our self-hosted ChatKit Python backend via the
 * Next.js API proxy at /api/chat.
 *
 * Authentication is handled transparently — the proxy route extracts
 * the Better Auth session cookie and forwards it as a Bearer token.
 */
export default function ChatInterface() {
  const { control } = useChatKit({
    api: {
      url: "/api/chat",
      domainKey: "local-dev",
    },
    startScreen: {
      greeting: "How can I help you with your tasks?",
      prompts: [
        { label: "Create a task", prompt: "Create a task called " },
        { label: "Show my tasks", prompt: "Show me all my tasks" },
        { label: "What's left to do?", prompt: "What tasks do I still need to complete?" },
      ],
    },
    header: {
      enabled: true,
      title: {
        enabled: true,
        text: "Todo Assistant",
      },
    },
    history: {
      enabled: true,
      showDelete: true,
    },
    composer: {
      placeholder: "Ask me to create, list, update, or complete tasks...",
    },
    disclaimer: {
      text: "AI assistant for task management. Responses may not always be accurate.",
    },
    theme: "light",
  });

  return (
    <ChatKit
      control={control}
      className="h-full w-full"
    />
  );
}
