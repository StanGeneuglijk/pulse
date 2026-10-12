import type { NextRequest } from "next/server";

/**
 * An absolute URL on this app's public origin. Behind Render's proxy,
 * `request.url` carries the container's own address (localhost:10000), so
 * redirects built from it send the browser nowhere; the forwarded headers
 * carry the host the browser actually used.
 */
export function publicUrl(request: NextRequest, path: string): URL {
  const host = request.headers.get("x-forwarded-host") ?? request.headers.get("host");
  const proto = request.headers.get("x-forwarded-proto") ?? request.nextUrl.protocol.replace(":", "");
  const origin = host ? `${proto}://${host}` : request.nextUrl.origin;
  return new URL(path, origin);
}
