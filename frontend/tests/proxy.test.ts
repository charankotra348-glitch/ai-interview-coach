import { NextRequest } from "next/server";
import { describe, expect, it } from "vitest";

import { proxy } from "@/proxy";
import { TOKEN_COOKIE } from "@/lib/session";

function visit(path: string, signedIn: boolean) {
  const headers: Record<string, string> = signedIn ? { cookie: `${TOKEN_COOKIE}=jwt` } : {};
  return proxy(new NextRequest(`http://localhost:3000${path}`, { headers }));
}

describe("page guard", () => {
  it("sends visitors without a session to login, remembering where they were going", () => {
    const response = visit("/interview/abc?x=1", false);
    expect(response.status).toBe(307);
    const location = new URL(response.headers.get("location")!);
    expect(location.pathname).toBe("/login");
    expect(location.searchParams.get("next")).toBe("/interview/abc?x=1");
  });

  it("lets signed-in users through to protected pages", () => {
    expect(visit("/dashboard", true).headers.get("location")).toBeNull();
  });

  it("sends signed-in users away from the login page", () => {
    expect(new URL(visit("/login", true).headers.get("location")!).pathname).toBe("/dashboard");
  });

  it("leaves public pages and look-alike paths alone", () => {
    expect(visit("/", false).headers.get("location")).toBeNull();
    expect(visit("/dashboards-are-public", false).headers.get("location")).toBeNull();
  });
});