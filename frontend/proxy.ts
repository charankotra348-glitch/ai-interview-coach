import { NextRequest, NextResponse } from "next/server";
import { AUTH_PAGES, PROTECTED_PREFIXES, TOKEN_COOKIE } from "@/lib/session";

/**
 * Runs before pages render. It only checks that the cookie exists; the backend checks
 * that the token inside is valid. An expired token gets a 401 from the API, the BFF
 * deletes the cookie, and the next navigation lands here and redirects to /login.
 */
export function proxy(request: NextRequest) {
  const { pathname, search } = request.nextUrl;
  const signedIn = request.cookies.has(TOKEN_COOKIE);

  if (!signedIn && PROTECTED_PREFIXES.some((p) => pathname === p || pathname.startsWith(`${p}/`))) {
    const login = new URL("/login", request.url);
    login.searchParams.set("next", pathname + search);
    return NextResponse.redirect(login);
  }
  if (signedIn && AUTH_PAGES.includes(pathname)) {
    return NextResponse.redirect(new URL("/dashboard", request.url));
  }
  return NextResponse.next();
}

export const config = {
  // Pages only: not the API routes, Next.js assets or files in public/.
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|ico)$).*)"],
};