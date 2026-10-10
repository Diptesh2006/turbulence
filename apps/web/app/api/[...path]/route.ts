import { NextRequest, NextResponse } from "next/server";

type RouteContext = { params: Promise<{ path: string[] }> };

async function proxy(request: NextRequest, context: RouteContext) {
  const apiUrl = process.env.TURBULENCE_API_URL;
  const apiToken = process.env.TURBULENCE_API_TOKEN;
  if (!apiUrl || !apiToken) {
    return NextResponse.json({ detail: "API proxy is not configured" }, { status: 503 });
  }

  const { path: segments } = await context.params;
  const path = segments.map(encodeURIComponent).join("/");
  const target = new URL(`/api/${path}${request.nextUrl.search}`, apiUrl);
  const headers = new Headers({ "X-Internal-API-Token": apiToken });
  for (const name of ["accept", "content-type", "idempotency-key", "last-event-id"]) {
    const value = request.headers.get(name);
    if (value) headers.set(name, value);
  }

  const hasBody = request.method !== "GET" && request.method !== "HEAD";
  const upstream = await fetch(target, {
    method: request.method,
    headers,
    body: hasBody ? await request.arrayBuffer() : undefined,
    cache: "no-store",
    signal: request.signal,
  });

  const responseHeaders = new Headers();
  for (const name of ["content-type", "cache-control", "retry-after"]) {
    const value = upstream.headers.get(name);
    if (value) responseHeaders.set(name, value);
  }
  if (responseHeaders.get("content-type")?.includes("text/event-stream")) {
    responseHeaders.set("cache-control", "no-cache, no-transform");
  }

  return new Response(upstream.body, {
    status: upstream.status,
    headers: responseHeaders,
  });
}

export const GET = proxy;
export const POST = proxy;
export const PUT = proxy;
export const DELETE = proxy;
