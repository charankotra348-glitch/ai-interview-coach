import { NextResponse } from "next/server";

/**
 * fetch() to the FastAPI backend that never throws. When the backend cannot be reached
 * (stopped, restarting, or its database is down), the browser gets a clear, retryable
 * 503 instead of a bare 500.
 */
export async function fetchBackend(url: string, init: RequestInit): Promise<Response> {
  try {
    return await fetch(url, init);
  } catch (error) {
    console.error(JSON.stringify({ event: "backend_unreachable", url, error: String(error) }));
    return NextResponse.json(
      { detail: { code: "backend_unavailable", message: "The service is unavailable right now. Please try again in a moment.", retryable: true } },
      { status: 503 },
    );
  }
}