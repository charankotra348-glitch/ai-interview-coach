import { NextRequest } from "next/server";
import { afterEach, describe, expect, it, vi } from "vitest";

import { POST as login } from "@/app/api/auth/login/route";
import { POST as logout } from "@/app/api/auth/logout/route";
import { GET as backendGet, POST as backendPost } from "@/app/api/backend/[...path]/route";
import { TOKEN_COOKIE } from "@/lib/session";

const ORIGIN = "http://localhost:3000";

function request(path: string, init: { method?: string; body?: BodyInit; headers?: Record<string, string>; cookie?: string } = {}) {
  const headers: Record<string, string> = { ...init.headers };
  if (init.method && init.method !== "GET") headers.origin ??= ORIGIN;   // browsers send Origin on POST
  if (init.cookie) headers.cookie = `${TOKEN_COOKIE}=${init.cookie}`;
  return new NextRequest(`${ORIGIN}${path}`, { method: init.method ?? "GET", body: init.body, headers });
}

function mockBackend(status: number, body: unknown) {
  const fetchMock = vi.fn().mockResolvedValue(
    new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } }),
  );
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

const params = (...path: string[]) => ({ params: Promise.resolve({ path }) });

afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

describe("login", () => {
  it("keeps the token in an httpOnly cookie and out of the response body", async () => {
    const fetchMock = mockBackend(200, { access_token: "jwt-123", token_type: "bearer", expires_in: 1800 });
    const response = await login(request("/api/auth/login", {
      method: "POST", body: JSON.stringify({ email: "a@example.com", password: "a long enough password" }),
    }));

    expect(response.status).toBe(200);
    expect(JSON.stringify(await response.json())).not.toContain("jwt-123");
    const cookie = response.headers.get("set-cookie") ?? "";
    expect(cookie).toContain(`${TOKEN_COOKIE}=jwt-123`);
    expect(cookie.toLowerCase()).toContain("httponly");
    expect(cookie.toLowerCase()).toContain("samesite=lax");
    expect(cookie).toContain("Max-Age=1800");

    // FastAPI's OAuth2 form: the email goes in "username".
    const sent = fetchMock.mock.calls[0];
    expect(sent[0]).toBe("http://127.0.0.1:8000/auth/token");
    expect(String(sent[1].body)).toContain("username=a%40example.com");
  });

  it("passes a failed login through and sets no cookie", async () => {
    mockBackend(401, { detail: { code: "invalid_credentials", message: "Incorrect email or password." } });
    const response = await login(request("/api/auth/login", {
      method: "POST", body: JSON.stringify({ email: "a@example.com", password: "wrong" }),
    }));
    expect(response.status).toBe(401);
    expect((await response.json()).detail.code).toBe("invalid_credentials");
    expect(response.headers.get("set-cookie")).toBeNull();
  });

  it("refuses a login posted from another site", async () => {
    const fetchMock = mockBackend(200, {});
    const response = await login(request("/api/auth/login", {
      method: "POST", body: "{}", headers: { origin: "https://evil.example" },
    }));
    expect(response.status).toBe(403);
    expect(fetchMock).not.toHaveBeenCalled();
  });
});

describe("logout", () => {
  it("expires the cookie", async () => {
    const response = await logout(request("/api/auth/logout", { method: "POST", cookie: "jwt-123" }));
    const cookie = response.headers.get("set-cookie") ?? "";
    expect(cookie).toContain(`${TOKEN_COOKIE}=;`);
    expect(cookie).toMatch(/Expires=Thu, 01 Jan 1970|Max-Age=0/);
  });
});

describe("backend proxy", () => {
  it("adds the token from the cookie and forwards the path and query", async () => {
    const fetchMock = mockBackend(200, { email: "a@example.com" });
    const response = await backendGet(request("/api/backend/profiles/gap?candidate_id=1", { cookie: "jwt-123" }),
                                      params("profiles", "gap"));
    expect(response.status).toBe(200);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("http://127.0.0.1:8000/profiles/gap?candidate_id=1");
    expect(new Headers(init.headers).get("authorization")).toBe("Bearer jwt-123");
  });

  it("answers 401 without calling the backend when there is no cookie", async () => {
    const fetchMock = mockBackend(200, {});
    const response = await backendGet(request("/api/backend/auth/me"), params("auth", "me"));
    expect(response.status).toBe(401);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("deletes the cookie when the backend says the token is no longer valid", async () => {
    mockBackend(401, { detail: { code: "unauthenticated", message: "Invalid or expired token." } });
    const response = await backendGet(request("/api/backend/auth/me", { cookie: "expired" }), params("auth", "me"));
    expect(response.status).toBe(401);
    expect(response.headers.get("set-cookie") ?? "").toContain(`${TOKEN_COOKIE}=;`);
  });

  it("forwards a POST body with its content type", async () => {
    const fetchMock = mockBackend(201, { id: "s1" });
    await backendPost(request("/api/backend/sessions", {
      method: "POST", cookie: "jwt-123", body: '{"mode":"behavioral"}', headers: { "content-type": "application/json" },
    }), params("sessions"));
    const [, init] = fetchMock.mock.calls[0];
    expect(new Headers(init.headers).get("content-type")).toBe("application/json");
    expect(new TextDecoder().decode(init.body)).toBe('{"mode":"behavioral"}');
  });

  it("refuses a cross-site POST even with a valid cookie", async () => {
    const fetchMock = mockBackend(201, {});
    const response = await backendPost(request("/api/backend/sessions", {
      method: "POST", cookie: "jwt-123", body: "{}", headers: { origin: "https://evil.example" },
    }), params("sessions"));
    expect(response.status).toBe(403);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("cannot be steered to another host through the path", async () => {
    const fetchMock = mockBackend(200, {});
    await backendGet(request("/api/backend/x", { cookie: "jwt-123" }), params("..", "@evil.example", "x"));
    expect(fetchMock.mock.calls[0][0]).toMatch(/^http:\/\/127\.0\.0\.1:8000\//);
  });
});


describe("backend unreachable", () => {
  function backendDown() {
    const fetchMock = vi.fn().mockRejectedValue(new TypeError("fetch failed"));
    vi.stubGlobal("fetch", fetchMock);
    vi.spyOn(console, "error").mockImplementation(() => {});   // keep the expected log out of test output
  }

  it("turns a failed login connection into a clear, retryable 503", async () => {
    backendDown();
    const response = await login(request("/api/auth/login", {
      method: "POST", body: JSON.stringify({ email: "a@example.com", password: "a long enough password" }),
    }));
    expect(response.status).toBe(503);
    const detail = (await response.json()).detail;
    expect(detail.code).toBe("backend_unavailable");
    expect(detail.retryable).toBe(true);
    expect(response.headers.get("set-cookie")).toBeNull();
  });

  it("does the same for proxied API calls, and keeps the session cookie", async () => {
    backendDown();
    const response = await backendGet(request("/api/backend/auth/me", { cookie: "jwt-123" }), params("auth", "me"));
    expect(response.status).toBe(503);
    expect(response.headers.get("set-cookie")).toBeNull();     // an outage is not a logout
  });
});