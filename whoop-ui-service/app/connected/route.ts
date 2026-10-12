import { NextRequest, NextResponse } from "next/server";
import { publicUrl } from "@/lib/url";
import { attachSessionCookie } from "@/lib/session";
import { exchangeCode } from "@/lib/whoopClient";

/**
 * Where whoop-service's own `/auth/callback` sends the browser after a
 * real WHOOP OAuth login — with a one-time code in the query string, not
 * the real `read_token` (see whoop-service's own callback() docstring
 * for why). This route redeems that code server-side, writes the result
 * straight into the session cookie, and redirects to the dashboard — the
 * read_token itself never reaches client JS at any point.
 */
export async function GET(request: NextRequest) {
  const code = request.nextUrl.searchParams.get("code");
  if (!code) {
    return NextResponse.redirect(publicUrl(request, "/login?error=missing_code"));
  }

  try {
    const result = await exchangeCode(code);
    if (!result.connected || !result.readToken) {
      return NextResponse.redirect(publicUrl(request, "/login?error=exchange_failed"));
    }
    const response = NextResponse.redirect(publicUrl(request, "/"));
    attachSessionCookie(response, { userId: result.userId, readToken: result.readToken });
    return response;
  } catch {
    return NextResponse.redirect(publicUrl(request, "/login?error=exchange_failed"));
  }
}
