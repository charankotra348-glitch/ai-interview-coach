# 005: Short-lived JWT access tokens and Argon2id passwords

Status: Accepted (2026-10-13)

## Context

Until Step 7 every request ran as one development user. The API now needs real accounts:
each person's resumes, job profiles and interviews must be visible only to them. The
clients are the Next.js frontend (Step 8) and scripts, both calling a JSON API.

## Decision

1. **Passwords are hashed with Argon2id** (pwdlib, argon2-cffi defaults: 64 MiB, 3 passes,
   4 lanes). Passwords are 12 to 128 characters. The plain password is never stored or logged.
2. **Login is the OAuth2 password flow** at `POST /auth/token`, returning a bearer token.
   This is the standard FastAPI shape, and it makes the Authorize button in `/docs` work.
3. **Access tokens are JWTs signed with HS256 and valid for 30 minutes.** Decoding accepts
   only HS256 and requires `sub`, `exp`, `iat`, `iss`, `aud`, plus `type = access`.
4. **The signing secret comes from `JWT_SECRET`.** Outside development the server refuses
   to start without one of at least 32 characters. In development a random secret is
   generated when none is set.
5. **Every route except `/health`, `/ready`, `/auth/register` and `/auth/token` needs a
   token.** A test reads the OpenAPI schema and fails if any other route answers without one.
6. **Resources owned by someone else return 404, not 403**, so a caller cannot learn that
   they exist.

## Why

- Argon2id is the current OWASP recommendation. It is memory-hard, so guessing passwords
  on GPUs is expensive.
- Stateless tokens fit an API called by a separate frontend, and any server can check one
  without a database lookup for the session. The user row is still loaded on every request,
  which also rejects tokens of deleted accounts.
- HS256 with one secret is enough while one service both issues and checks tokens.

## Login does not reveal which emails are registered

- A wrong password and an unknown email return the same 401 body.
- An unknown email still runs a full Argon2 check against a dummy hash, so both take the
  same time. Measured on a MacBook Air: about 38 ms against 37 ms.

## Measured

- Password check with production settings: about 38 ms on a MacBook Air, about 120 ms in a
  small cloud container. Tests use cheaper Argon2 settings; one test checks the real ones.

## Accepted limits

- **No refresh tokens or revocation.** A stolen token works until it expires (30 minutes),
  and logging out only means the client forgets the token. Revisit in Step 8: a refresh token
  in an httpOnly cookie, plus a `token_version` column on users to revoke all tokens at once.
- **Registration reveals that an email exists** (409 `email_taken`). Most products accept this.
  The fix (always answer "check your email") needs email delivery, which this project lacks.
- **No rate limiting on login yet.** Argon2 slows guessing, but repeated attempts are not
  blocked. Planned at the edge in Step 11 (for example AWS WAF rate rules), not in the app.
- **No email verification or password reset.** Both need an email service.

## Revisit when

- A second service needs to verify tokens: switch to an asymmetric algorithm (RS256 or
  EdDSA), so verifiers hold only the public key.
- Real users arrive: add refresh tokens, revocation, rate limiting and email verification.