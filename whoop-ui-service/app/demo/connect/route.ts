import { NextResponse } from "next/server";
import { config } from "@/lib/config";
import { clearSessionCookie } from "@/lib/session";

/**
 * "Connect your WHOOP" from inside the demo: end the demo first, then start
 * the real connect flow, so a demo visitor never carries a demo cookie into
 * a real login.
 */
// Never prerender: the response clears a cookie, so it must run per request.
export const dynamic = "force-dynamic";

export function GET() {
  const response = NextResponse.redirect(`${config.whoopServiceUrl}/auth/login`);
  clearSessionCookie(response);
  return response;
}
