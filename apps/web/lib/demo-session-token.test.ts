import { describe, expect, it } from "vitest";
import { createDemoSessionToken, verifyDemoSessionToken } from "./demo-session-token";

const secret = "session-secret-for-demo-tests-0123456789";

describe("demo session tokens", () => {
  it("accepts a valid unexpired signature", async () => {
    const token = await createDemoSessionToken(secret, 2_000);

    await expect(verifyDemoSessionToken(token, secret, 1_000)).resolves.toBe(true);
  });

  it("rejects expired, modified, and incorrectly signed tokens", async () => {
    const token = await createDemoSessionToken(secret, 2_000);
    const modified = `${token.slice(0, -1)}${token.endsWith("a") ? "b" : "a"}`;

    await expect(verifyDemoSessionToken(token, secret, 2_000)).resolves.toBe(false);
    await expect(verifyDemoSessionToken(modified, secret, 1_000)).resolves.toBe(false);
    await expect(verifyDemoSessionToken(token, `${secret}-wrong`, 1_000)).resolves.toBe(false);
  });
});
