import { NextRequest } from "next/server";
import { proxyToBackend } from "@/lib/api-proxy";

/**
 * GET /api/chat/conversations/:id/messages -> GET /api/v1/chat/conversations/:id/messages
 */
export async function GET(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  const { id } = params;
  return proxyToBackend(request, `/chat/conversations/${id}/messages`);
}
