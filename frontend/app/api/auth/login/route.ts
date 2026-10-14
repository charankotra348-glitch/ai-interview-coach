import { NextRequest, NextResponse } from "next/server";
import { BACKEND_URL, TOKEN_COOKIE, tokenCookieOptions } from "@/lib/session";
import { isSameOrigin } from "@/lib/origin";
import { fetchBackend } from "@/lib/backend-fetch";

export async function POST(request: NextRequest) {
  if (!isSameOrigin(request)) {
    return NextResponse.json({ detail: { code: "bad_origin", message: "Cross-site request refused." } }, { status: 403 });
  }
  const { email, password } = await request.json().catch(() => ({}));

  // FastAPI's login is the OAuth2 password flow: form fields "username" and "password".
  const backend = await fetchBackend(`${BACKEND_URL}/auth/token`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({ username: String(email ?? ""), password: String(password ?? "") }),
  });
  const body = await backend.json().catch(() => ({}));
  if (!backend.ok) {
    return NextResponse.json(body, { status: backend.status });
  }

  // The token goes into an httpOnly cookie. The response body never contains it.
  const response = NextResponse.json({ ok: true });
  response.cookies.set(TOKEN_COOKIE, body.access_token, tokenCookieOptions(body.expires_in));
  return response;
}