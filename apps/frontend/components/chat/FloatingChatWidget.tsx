"use client";

import React, { useState } from "react";
import { usePathname } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import ChatInterface from "./ChatInterface";

const HIDDEN_PATHS = ["/chat", "/login", "/signup"];
const THEME_COLORS = ["#8b5cf6", "#f43f5e", "#f59e0b", "#10b981"];

export default function FloatingChatWidget() {
  const [isOpen, setIsOpen] = useState(false);
  const pathname = usePathname();

  if (HIDDEN_PATHS.some((p) => pathname.startsWith(p))) {
    return null;
  }

  return (
    <>
      {/* Overlay backdrop on mobile */}
      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/20 backdrop-blur-sm z-[59] sm:hidden"
            onClick={() => setIsOpen(false)}
          />
        )}
      </AnimatePresence>

      {/* Chat panel */}
      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, scale: 0.85, y: 30 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.85, y: 30 }}
            transition={{ type: "spring", damping: 22, stiffness: 280 }}
            className="fixed z-[60]
                       bottom-[88px] right-4 w-[400px] h-[520px]
                       max-sm:inset-4 max-sm:w-auto max-sm:h-auto max-sm:bottom-4"
          >
            <div className="h-full flex flex-col overflow-hidden rounded-2xl bg-white/85 backdrop-blur-xl border border-white/60 shadow-glass-xl relative">
              {/* Animated gradient border glow */}
              <motion.div
                animate={{ opacity: [0.3, 0.6, 0.3] }}
                transition={{ duration: 4, repeat: Infinity, ease: "easeInOut" }}
                className="absolute inset-0 rounded-2xl pointer-events-none"
                style={{
                  background: "linear-gradient(135deg, rgba(139,92,246,0.1), rgba(244,63,94,0.05), rgba(245,158,11,0.05), rgba(16,185,129,0.1))",
                }}
              />

              {/* Header */}
              <div className="relative z-10 flex items-center justify-between px-4 py-3 border-b border-slate-200/60">
                <div className="flex items-center gap-2.5">
                  {/* Mini animated logo */}
                  <div className="relative">
                    <motion.div
                      animate={{ rotate: 360 }}
                      transition={{ duration: 15, repeat: Infinity, ease: "linear" }}
                      className="absolute inset-[-2px] rounded-lg opacity-50"
                      style={{
                        background: "linear-gradient(135deg, #8b5cf6, #f43f5e, #f59e0b, #10b981, #8b5cf6)",
                      }}
                    />
                    <div className="relative w-8 h-8 rounded-lg bg-brand-gradient flex items-center justify-center shadow-sm">
                      <svg
                        className="w-4 h-4 text-white"
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
                  <div>
                    <span className="text-sm font-bold bg-clip-text text-transparent bg-gradient-to-r from-brand-600 to-accent-rose-500">
                      Todo Assistant
                    </span>
                    <div className="flex items-center gap-1 mt-0.5">
                      <motion.span
                        animate={{ scale: [1, 1.4, 1] }}
                        transition={{ duration: 2, repeat: Infinity }}
                        className="w-1.5 h-1.5 rounded-full bg-accent-emerald-500"
                      />
                      <span className="text-[10px] text-slate-400 font-medium">Online</span>
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-1">
                  {/* New Chat button */}
                  <motion.button
                    whileHover={{ scale: 1.1 }}
                    whileTap={{ scale: 0.9 }}
                    onClick={() => window.dispatchEvent(new CustomEvent("chatbot-clear"))}
                    title="New chat"
                    className="w-7 h-7 rounded-lg flex items-center justify-center text-slate-400
                               hover:bg-brand-50 hover:text-brand-500 transition-colors"
                  >
                    <svg
                      className="w-4 h-4"
                      fill="none"
                      viewBox="0 0 24 24"
                      strokeWidth={1.5}
                      stroke="currentColor"
                    >
                      <path strokeLinecap="round" strokeLinejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0 3.181 3.183a8.25 8.25 0 0 0 13.803-3.7M4.031 9.865a8.25 8.25 0 0 1 13.803-3.7l3.181 3.182" />
                    </svg>
                  </motion.button>

                  {/* Close button */}
                  <motion.button
                    whileHover={{ scale: 1.1, rotate: 90 }}
                    whileTap={{ scale: 0.9 }}
                    onClick={() => setIsOpen(false)}
                    className="w-7 h-7 rounded-lg flex items-center justify-center text-slate-400
                               hover:bg-accent-rose-50 hover:text-accent-rose-500 transition-colors"
                  >
                    <svg
                      className="w-4 h-4"
                      fill="none"
                      viewBox="0 0 24 24"
                      strokeWidth={2}
                      stroke="currentColor"
                    >
                      <path strokeLinecap="round" strokeLinejoin="round" d="M6 18 18 6M6 6l12 12" />
                    </svg>
                  </motion.button>
                </div>
              </div>

              {/* Rainbow accent bar under header */}
              <div className="h-0.5 bg-gradient-to-r from-brand-500 via-accent-rose-500 via-accent-amber-500 to-accent-emerald-500 opacity-40" />

              {/* Chat body */}
              <div className="flex-1 min-h-0 relative z-10">
                <ChatInterface compact />
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Floating button */}
      <div className="fixed z-[60] bottom-5 right-5">
        {/* Animated glow ring behind button */}
        <AnimatePresence>
          {!isOpen && (
            <motion.div
              initial={{ opacity: 0, scale: 0.8 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.8 }}
              className="absolute inset-0"
            >
              <motion.div
                animate={{ scale: [1, 1.3, 1], opacity: [0.4, 0.15, 0.4] }}
                transition={{ duration: 3, repeat: Infinity, ease: "easeInOut" }}
                className="absolute inset-[-6px] rounded-full"
                style={{
                  background: "linear-gradient(135deg, #8b5cf6, #f43f5e, #f59e0b, #10b981)",
                }}
              />
            </motion.div>
          )}
        </AnimatePresence>

        <motion.button
          onClick={() => setIsOpen(!isOpen)}
          whileHover={{ scale: 1.08 }}
          whileTap={{ scale: 0.92 }}
          className="relative w-14 h-14 rounded-full text-white shadow-brand-md
                     flex items-center justify-center overflow-hidden"
          style={{
            background: "linear-gradient(135deg, #8b5cf6 0%, #6366f1 40%, #3b82f6 100%)",
          }}
        >
          {/* Animated shimmer on button */}
          <motion.div
            animate={{ x: ["-100%", "200%"] }}
            transition={{ duration: 3, repeat: Infinity, ease: "linear", repeatDelay: 4 }}
            className="absolute inset-0 w-1/2"
            style={{
              background: "linear-gradient(90deg, transparent, rgba(255,255,255,0.2), transparent)",
              transform: "skewX(-20deg)",
            }}
          />

          <AnimatePresence mode="wait" initial={false}>
            {isOpen ? (
              <motion.svg
                key="close"
                initial={{ rotate: -90, opacity: 0, scale: 0.5 }}
                animate={{ rotate: 0, opacity: 1, scale: 1 }}
                exit={{ rotate: 90, opacity: 0, scale: 0.5 }}
                transition={{ duration: 0.2, type: "spring", stiffness: 300 }}
                className="w-6 h-6 relative z-10"
                fill="none"
                viewBox="0 0 24 24"
                strokeWidth={2}
                stroke="currentColor"
              >
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18 18 6M6 6l12 12" />
              </motion.svg>
            ) : (
              <motion.svg
                key="chat"
                initial={{ rotate: 90, opacity: 0, scale: 0.5 }}
                animate={{ rotate: 0, opacity: 1, scale: 1 }}
                exit={{ rotate: -90, opacity: 0, scale: 0.5 }}
                transition={{ duration: 0.2, type: "spring", stiffness: 300 }}
                className="w-6 h-6 relative z-10"
                fill="none"
                viewBox="0 0 24 24"
                strokeWidth={1.5}
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M9.813 15.904 9 18.75l-.813-2.846a4.5 4.5 0 0 0-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 0 0 3.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 0 0 3.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 0 0-3.09 3.09ZM18.259 8.715 18 9.75l-.259-1.035a3.375 3.375 0 0 0-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 0 0 2.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 0 0 2.455 2.456L21.75 6l-1.036.259a3.375 3.375 0 0 0-2.455 2.456Z"
                />
              </motion.svg>
            )}
          </AnimatePresence>

          {/* Colored dots orbiting the button (when closed) */}
          {!isOpen && (
            <>
              {THEME_COLORS.map((color, i) => (
                <motion.span
                  key={i}
                  animate={{
                    rotate: 360,
                  }}
                  transition={{
                    duration: 8,
                    repeat: Infinity,
                    ease: "linear",
                    delay: i * 2,
                  }}
                  className="absolute w-2 h-2 rounded-full"
                  style={{
                    backgroundColor: color,
                    top: i === 0 ? -1 : i === 2 ? "auto" : "50%",
                    bottom: i === 2 ? -1 : "auto",
                    left: i === 3 ? -1 : i === 1 ? "auto" : "50%",
                    right: i === 1 ? -1 : "auto",
                    transform: "translate(-50%, -50%)",
                    opacity: 0.7,
                  }}
                />
              ))}
            </>
          )}
        </motion.button>
      </div>
    </>
  );
}
