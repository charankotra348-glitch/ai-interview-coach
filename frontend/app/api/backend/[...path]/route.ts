import { NextRequest, NextResponse } from "next/server";
import { BACKEND_URL, TOKEN_COOKIE } from "@/lib/session";
import { isSameOrigin } from "@/lib/origin";

/**
 * Forwards /api/backend/<path> to the FastAPI backend, adding the token from the cookie.
 * The browser only ever talks to this server, so no CORS setup is needed and no
 * JavaScript in the page can read the token.
 */
async function forward(request: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  if (!isSameOrigin(request)) {
    return NextResponse.json({ detail: { code: "bad_origin", message: "Cross-site request refused." } }, { status: 403 });
  }
  const token = request.cookies.get(TOKEN_COOKIE)?.value;
  if (!token) {
    return NextResponse.json({ detail: { code: "unauthenticated", message: "Please log in." } }, { status: 401 });
  }

  const { path } = await ctx.params;
  const url = `${BACKEND_URL}/${path.map(encodeURIComponent).join("/")}${request.nextUrl.search}`;
  const headers = new Headers({ Authorization: `Bearer ${token}` });
  const contentType = request.headers.get("content-type");
  if (contentType) headers.set("Content-Type", contentType);   // keeps the multipart boundary for uploads

  const backend = await fetch(url, {
    method: request.method,
    headers,
    body: request.method === "GET" || request.method === "HEAD" ? undefined : await request.arrayBuffer(),
  });

  const response = new NextResponse(backend.body, {
    status: backend.status,
    headers: { "Content-Type": backend.headers.get("content-type") ?? "application/json" },
  });
  if (backend.status === 401) {
    response.cookies.delete(TOKEN_COOKIE);    // expired or invalid: forget it, so the next page asks to log in
  }
  return response;
}

export const GET = forward;
export const POST = forward;