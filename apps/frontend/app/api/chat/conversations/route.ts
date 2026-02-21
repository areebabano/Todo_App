import { NextRequest } from "next/server";
import { proxyToBackend } from "@/lib/api-proxy";

/**
 * GET /api/chat/conversations -> GET /api/v1/chat/conversations
 */
export async function GET(request: NextRequest) {
  return proxyToBackend(request, "/chat/conversations");
}
