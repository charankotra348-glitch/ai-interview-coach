# 006: Backend-for-Frontend with an httpOnly cookie; the browser never holds the token

Status: Accepted (2026-10-13)

## Context

Decision 005 gives the API short-lived JWT access tokens. The Next.js frontend needs to
send that token on every call without exposing it. The usual shortcut, keeping the token
in `localStorage` and calling FastAPI directly from the browser, lets any injected script
(an XSS bug, a compromised npm package) read the token and use it from anywhere.

## Decision

1. **The browser talks only to the Next.js server.** Next.js route handlers act as a
   Backend-for-Frontend (BFF): `/api/auth/*` for register, login and logout, and
   `/api/backend/<path>` forwarding everything else to FastAPI.
2. **On login, the BFF puts the token in an `httpOnly`, `SameSite=Lax` cookie** (plus
   `Secure` in production) with the token's own lifetime, and returns no token in the body.
   Page JavaScript cannot read the cookie (`document.cookie` does not contain it).
3. **The BFF adds `Authorization: Bearer <token>`** when forwarding to FastAPI. FastAPI is
   unchanged and still validates every request (decision 005).
4. **Cross-site requests are refused twice:** `SameSite=Lax` keeps the cookie off cross-site
   POSTs, and the BFF rejects any POST whose `Origin` names another site (403 `bad_origin`).
5. **When FastAPI answers 401, the BFF deletes the cookie,** and the page sends the user to
   `/login?next=<page>`. Only same-site paths are accepted as `next` (no open redirects).
6. **`proxy.ts` (Next 16's middleware) guards pages** by checking that the cookie exists.
   It does not validate the token; the API does that on the first call.

## Why

- An `httpOnly` cookie removes the most common way tokens are stolen. XSS can still act
  inside an open page, but it cannot carry the token away.
- Same origin means no CORS configuration and no preflight requests.
- FastAPI keeps one simple contract (bearer tokens) for the frontend, scripts and tests.

## Measured

- The BFF adds a hop. Its own cost is small next to model calls of several seconds;
  measure it in Step 8c on the interview screen.

## Accepted limits

- **No refresh token yet.** The cookie lives exactly as long as the 30-minute access token,
  so a user is asked to log in again after 30 minutes. Revisit before real users: an opaque
  refresh token in a second `httpOnly` cookie, rotated on use.
- **Logout only deletes the cookie.** The token stays valid until it expires (decision 005).
- **`proxy.ts` trusts the cookie's presence.** An expired cookie shows the page shell
  briefly before the first API call redirects to login.

## Revisit when

- A mobile app or third party needs the API: they use bearer tokens directly, as scripts do.
- The frontend and API move to different domains: the cookie and the Origin check need
  the deployment's real domains (Step 11).