import type { NextRequest } from "next/server";

/**
 * Defense in depth against cross-site request forgery. The SameSite=Lax cookie already
 * stops other sites from sending it on POSTs; this also refuses any state-changing request
 * whose Origin header names another site. Browsers always send Origin on POST.
 *
 * The comparison is by host, read from the request's own Host header (or X-Forwarded-Host
 * from a proxy), not from `nextUrl`: behind CloudFront and a load balancer the standalone
 * server sees its own listen address there, and the scheme changes at the TLS edge
 * (https at CloudFront, http to the app), so an exact origin match would refuse every
 * real login. A cross-site page can't set either header, so the check still holds.
 */
export function isSameOrigin(request: NextRequest): boolean {
  const origin = request.headers.get("origin");
  if (!origin) return request.method === "GET" || request.method === "HEAD";
  let originHost: string;
  try {
    originHost = new URL(origin).host;
  } catch {
    return false;
  }
  const host = request.headers.get("x-forwarded-host") ?? request.headers.get("host") ?? request.nextUrl.host;
  return originHost === host.split(",")[0].trim();
}
