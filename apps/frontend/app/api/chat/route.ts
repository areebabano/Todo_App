import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api/v1";

/**
 * Extract the raw session token from a Better Auth signed cookie value.
 * Better Auth format: encodeURIComponent(`rawToken.hmacBase64Signature`)
 */
function extractRawToken(cookieValue: string): string {
  let decoded: string;
  try {
    decoded = decodeURIComponent(cookieValue);
  } catch {
    decoded = cookieValue;
  }

  const lastDot = decoded.lastIndexOf(".");
  if (lastDot < 1) return decoded;

  const signature = decoded.substring(lastDot + 1);
  if (signature.length === 44 && signature.endsWith("=")) {
    return decoded.substring(0, lastDot);
  }

  return decoded;
}

/**
 * Proxy streaming chat requests to the FastAPI backend.
 *
 * POST /api/chat -> POST /api/v1/chat/stream (SSE)
 */
export async function POST(request: NextRequest) {
  const rawCookieValue = request.cookies.get(
    "better-auth.session_token"
  )?.value;

  if (!rawCookieValue) {
    return NextResponse.json({ detail: "Not authenticated" }, { status: 401 });
  }

  const sessionToken = extractRawToken(rawCookieValue);
  const body = await request.text();
  const url = `${BACKEND_URL}/chat/stream`;

  try {
    const backendRes = await fetch(url, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${sessionToken}`,
        "Content-Type": "application/json",
      },
      body,
      cache: "no-store",
    });

    const contentType = backendRes.headers.get("content-type") || "";
    if (contentType.includes("text/event-stream")) {
      return new Response(backendRes.body, {
        status: backendRes.status,
        headers: {
          "Content-Type": "text/event-stream",
          "Cache-Control": "no-cache",
          Connection: "keep-alive",
          "X-Accel-Buffering": "no",
        },
      });
    }

    // Non-streaming fallback (e.g. error responses)
    const data = await backendRes.text();
    return new NextResponse(data, {
      status: backendRes.status,
      headers: { "Content-Type": "application/json" },
    });
  } catch (err) {
    console.error("[chat-proxy] Backend fetch failed:", err);
    return NextResponse.json(
      { detail: "Chat service unavailable" },
      { status: 502 }
    );
  }
}
