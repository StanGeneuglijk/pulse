import { NextRequest, NextResponse } from "next/server";
import { publicUrl } from "@/lib/url";
import { attachSessionCookie } from "@/lib/session";

/**
 * Local development only: start a session from a user id + read token, so a
 * seeded test user can be viewed without a real WHOOP login (not the public
 * demo, which is /demo/start). It grants nothing
 * the token itself doesn't — every backend call re-validates it. 404 in production.
 */
export async function GET(request: NextRequest) {
  if (process.env.NODE_ENV === "production") {
    return new NextResponse(null, { status: 404 });
  }
  const userId = request.nextUrl.searchParams.get("userId");
  const readToken = request.nextUrl.searchParams.get("readToken");
  if (!userId || !readToken) {
    return NextResponse.json({ error: "userId and readToken are required" }, { status: 400 });
  }
  const response = NextResponse.redirect(publicUrl(request, "/"));
  attachSessionCookie(response, { userId, readToken });
  return response;
}
