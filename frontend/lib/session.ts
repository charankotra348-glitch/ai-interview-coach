/**
 * Server-only settings for the Backend-for-Frontend (see docs/decisions/006).
 * The browser never sees the access token: it lives in an httpOnly cookie that only
 * this Next.js server reads, and the server adds it to calls to the FastAPI backend.
 */
export const BACKEND_URL = (process.env.BACKEND_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");

export const TOKEN_COOKIE = "aic_token";

export function tokenCookieOptions(maxAgeSeconds: number) {
  return {
    httpOnly: true,                                   // JavaScript in the page cannot read it
    secure: process.env.NODE_ENV === "production",    // HTTPS only, outside local development
    sameSite: "lax" as const,                         // not sent on cross-site POSTs
    path: "/",
    maxAge: maxAgeSeconds,                            // expires together with the token
  };
}

/** Pages that need a signed-in user. proxy.ts sends visitors without a cookie to /login. */
export const PROTECTED_PREFIXES = ["/dashboard", "/interview"];
export const AUTH_PAGES = ["/login", "/register"];