import { describe, expect, it } from "vitest";
import { safeNext, toApiError } from "@/lib/api";

describe("error messages", () => {
  it("reads our standard error shape", () => {
    const error = toApiError(503, { detail: { code: "ai_unavailable", message: "Busy.", retryable: true } });
    expect([error.code, error.message, error.retryable]).toEqual(["ai_unavailable", "Busy.", true]);
  });

  it("turns FastAPI validation errors into one readable message", () => {
    const error = toApiError(422, { detail: [{ loc: ["body", "password"], msg: "String should have at least 12 characters" }] });
    expect(error.message).toBe("password: String should have at least 12 characters");
  });

  it("falls back to a generic message for anything else", () => {
    expect(toApiError(500, "<html>").message).toMatch(/Something went wrong/);
  });
});

describe("redirect after login", () => {
  it("only follows paths on this site", () => {
    expect(safeNext("/interview/abc")).toBe("/interview/abc");
    expect(safeNext("https://evil.example")).toBe("/dashboard");
    expect(safeNext("//evil.example")).toBe("/dashboard");
    expect(safeNext(null)).toBe("/dashboard");
  });
});