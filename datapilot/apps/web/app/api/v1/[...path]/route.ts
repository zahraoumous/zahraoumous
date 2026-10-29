import type { NextRequest } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

async function proxy(request: NextRequest, context: { params: Promise<{path: string[]}> }) {
  const {path} = await context.params;
  const upstream = process.env.DATAPILOT_API_URL || "http://127.0.0.1:8000";
  const url = new URL("/api/v1/" + path.map(encodeURIComponent).join("/"), upstream);
  url.search = request.nextUrl.search;
  const headers = new Headers();
  for (const name of ["content-type", "cookie", "origin", "content-length"]) {
    const value = request.headers.get(name);
    if (value) headers.set(name, value);
  }
  const init: RequestInit & {duplex?: "half"} = {
    method: request.method, headers, redirect: "manual", cache: "no-store",
    signal: AbortSignal.timeout(180_000),
  };
  if (!["GET", "HEAD"].includes(request.method)) {
    init.body = request.body;
    init.duplex = "half";
  }
  try {
    const response = await fetch(url, init);
    const outgoing = new Headers({"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"});
    for (const name of ["content-type", "content-disposition", "x-request-id", "retry-after"]) {
      const value = response.headers.get(name);
      if (value) outgoing.set(name, value);
    }
    for (const cookie of response.headers.getSetCookie()) outgoing.append("set-cookie", cookie);
    return new Response(response.body, {status: response.status, headers: outgoing});
  } catch {
    return Response.json({detail: "The API is unavailable. Check that the service stack is running."}, {status: 503});
  }
}
export const GET = proxy;
export const POST = proxy;
export const PUT = proxy;
