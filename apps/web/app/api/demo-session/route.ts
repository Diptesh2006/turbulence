import { timingSafeEqual } from "node:crypto";
import { NextRequest, NextResponse } from "next/server";
import { checkRateLimit } from "@vercel/firewall";
import { createDemoSessionToken } from "../../../lib/demo-session-token";

const cookieName = "turbulence_demo_access";
const sessionSeconds = 12 * 60 * 60;

function matchesInviteCode(expected: string, provided: string) {
  const expectedBytes = Buffer.from(expected);
  const providedBytes = Buffer.from(provided);
  return expectedBytes.length === providedBytes.length && timingSafeEqual(expectedBytes, providedBytes);
}

export async function POST(request: NextRequest) {
  if (request.headers.get("origin") !== request.nextUrl.origin) {
    return NextResponse.json({ detail: "Invalid request origin" }, { status: 403 });
  }

  const expected = process.env.DEMO_ACCESS_CODE;
  const sessionSecret = process.env.DEMO_SESSION_SECRET;
  if (
    !expected ||
    !sessionSecret ||
    Buffer.byteLength(expected) < 32 ||
    Buffer.byteLength(sessionSecret) < 32
  ) {
    return NextResponse.json({ detail: "Demo access is not configured" }, { status: 503 });
  }

  if (process.env.VERCEL) {
    try {
      const result = await checkRateLimit("demo-login", { request });
      if (result.rateLimited) {
        return NextResponse.json({ detail: "Too many attempts. Try again later." }, { status: 429 });
      }
    } catch {
      return NextResponse.json({ detail: "Invite verification is temporarily unavailable" }, { status: 503 });
    }
  }

  let code = "";
  try {
    const payload: unknown = await request.json();
    if (payload && typeof payload === "object" && "code" in payload && typeof payload.code === "string") {
      code = payload.code;
    }
  } catch {
    return NextResponse.json({ detail: "Invalid request" }, { status: 400 });
  }

  if (!matchesInviteCode(expected, code)) {
    return NextResponse.json({ detail: "Invalid invite code" }, { status: 401 });
  }

  const response = NextResponse.json({ authenticated: true });
  const token = await createDemoSessionToken(
    `${sessionSecret}:${expected}`,
    Date.now() + sessionSeconds * 1000,
  );
  response.cookies.set(cookieName, token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "strict",
    path: "/",
    maxAge: sessionSeconds,
  });
  return response;
}

export async function DELETE(request: NextRequest) {
  if (request.headers.get("origin") !== request.nextUrl.origin) {
    return NextResponse.json({ detail: "Invalid request origin" }, { status: 403 });
  }

  const response = NextResponse.json({ authenticated: false });
  response.cookies.delete(cookieName);
  return response;
}
