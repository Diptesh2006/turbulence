import { NextRequest } from "next/server";
import { afterEach, describe, expect, it, vi } from "vitest";
import { POST } from "./route";
import { verifyDemoSessionToken } from "../../../lib/demo-session-token";

const inviteCode = "invite-code-for-tests-0123456789abcdef";
const sessionSecret = "session-secret-for-tests-0123456789abcdef";
const origin = "https://demo.example";

function request(code: string, requestOrigin = origin) {
  return new NextRequest(`${origin}/api/demo-session`, {
    method: "POST",
    headers: { origin: requestOrigin, "content-type": "application/json" },
    body: JSON.stringify({ code }),
  });
}

afterEach(() => vi.unstubAllEnvs());

describe("demo session endpoint", () => {
  it("sets a signed session cookie for a valid invite", async () => {
    vi.stubEnv("DEMO_ACCESS_CODE", inviteCode);
    vi.stubEnv("DEMO_SESSION_SECRET", sessionSecret);
    vi.stubEnv("VERCEL", "");

    const response = await POST(request(inviteCode));
    const cookie = response.cookies.get("turbulence_demo_access");
    const token = cookie?.value;

    expect(response.status).toBe(200);
    expect(token).toBeTruthy();
    expect(token).not.toBe(inviteCode);
    expect(cookie?.httpOnly).toBe(true);
    expect(cookie?.sameSite).toBe("strict");
    await expect(verifyDemoSessionToken(token!, `${sessionSecret}:${inviteCode}`)).resolves.toBe(true);
    await expect(verifyDemoSessionToken(token!, `${sessionSecret}:rotated-code`)).resolves.toBe(false);
  });

  it("rejects invalid codes and cross-origin requests", async () => {
    vi.stubEnv("DEMO_ACCESS_CODE", inviteCode);
    vi.stubEnv("DEMO_SESSION_SECRET", sessionSecret);
    vi.stubEnv("VERCEL", "");

    expect((await POST(request("wrong-code"))).status).toBe(401);
    expect((await POST(request(inviteCode, "https://attacker.example"))).status).toBe(403);
  });
});
