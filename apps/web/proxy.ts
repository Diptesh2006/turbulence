import { NextRequest, NextResponse } from "next/server";
import { verifyDemoSessionToken } from "@/lib/demo-session-token";

const sessionCookie = "turbulence_demo_access";

export async function proxy(request: NextRequest) {
  if (process.env.NODE_ENV !== "production") {
    return NextResponse.next();
  }

  const inviteCode = process.env.DEMO_ACCESS_CODE;
  const sessionSecret = process.env.DEMO_SESSION_SECRET;
  if (
    !inviteCode ||
    !sessionSecret ||
    new TextEncoder().encode(inviteCode).byteLength < 32 ||
    new TextEncoder().encode(sessionSecret).byteLength < 32
  ) {
    return NextResponse.json({ detail: "Demo access is not configured" }, { status: 503 });
  }

  const pathname = request.nextUrl.pathname;
  if (pathname === "/access" || pathname === "/api/demo-session") {
    return NextResponse.next();
  }

  const sessionToken = request.cookies.get(sessionCookie)?.value;
  if (sessionToken && await verifyDemoSessionToken(sessionToken, `${sessionSecret}:${inviteCode}`)) {
    return NextResponse.next();
  }

  if (pathname.startsWith("/api/")) {
    return NextResponse.json({ detail: "Invite code required" }, { status: 401 });
  }

  return NextResponse.redirect(new URL("/access", request.url));
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
