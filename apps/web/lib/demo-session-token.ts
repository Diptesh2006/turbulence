const encoder = new TextEncoder();

function encodeBase64Url(value: Uint8Array) {
  let binary = "";
  for (let index = 0; index < value.length; index += 1) {
    binary += String.fromCharCode(value[index]);
  }
  return btoa(binary).replaceAll("+", "-").replaceAll("/", "_").replace(/=+$/, "");
}

function decodeBase64Url(value: string) {
  const base64 = value.replaceAll("-", "+").replaceAll("_", "/");
  const binary = atob(base64 + "=".repeat((4 - (base64.length % 4)) % 4));
  return Uint8Array.from(binary, (character) => character.charCodeAt(0));
}

async function importSessionKey(secret: string) {
  return crypto.subtle.importKey(
    "raw",
    encoder.encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign", "verify"],
  );
}

export async function createDemoSessionToken(secret: string, expiresAt: number) {
  const payload = encodeBase64Url(encoder.encode(JSON.stringify({ expiresAt })));
  const signature = await crypto.subtle.sign("HMAC", await importSessionKey(secret), encoder.encode(payload));
  return `${payload}.${encodeBase64Url(new Uint8Array(signature))}`;
}

export async function verifyDemoSessionToken(token: string, secret: string, now = Date.now()) {
  try {
    const [payload, signature, extra] = token.split(".");
    if (!payload || !signature || extra) return false;

    const decoded = JSON.parse(new TextDecoder().decode(decodeBase64Url(payload))) as { expiresAt?: unknown };
    if (typeof decoded.expiresAt !== "number" || decoded.expiresAt <= now) return false;

    return crypto.subtle.verify(
      "HMAC",
      await importSessionKey(secret),
      decodeBase64Url(signature),
      encoder.encode(payload),
    );
  } catch {
    return false;
  }
}
