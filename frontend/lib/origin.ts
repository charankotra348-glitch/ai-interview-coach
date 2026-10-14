import type { NextRequest } from "next/server";

/**
 * Defense in depth against cross-site request forgery. The SameSite=Lax cookie already
 * stops other sites from sending it on POSTs; this also refuses any state-changing request
 * whose Origin header names another site. Browsers always send Origin on POST.
 */
export function isSameOrigin(request: NextRequest): boolean {
  const origin = request.headers.get("origin");
  if (!origin) return request.method === "GET" || request.method === "HEAD";
  return origin === request.nextUrl.origin;
}