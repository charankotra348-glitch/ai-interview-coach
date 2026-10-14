import { NextRequest, NextResponse } from "next/server";
import { BACKEND_URL } from "@/lib/session";
import { isSameOrigin } from "@/lib/origin";

export async function POST(request: NextRequest) {
  if (!isSameOrigin(request)) {
    return NextResponse.json({ detail: { code: "bad_origin", message: "Cross-site request refused." } }, { status: 403 });
  }
  const backend = await fetch(`${BACKEND_URL}/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: await request.text(),
  });
  return NextResponse.json(await backend.json().catch(() => ({})), { status: backend.status });
}