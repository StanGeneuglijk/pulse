import { NextRequest, NextResponse } from "next/server";
import { attachDemoCookie, getSession } from "@/lib/session";
import { publicUrl } from "@/lib/url";

/**
 * "Try the demo": starts a demo session for a visitor without WHOOP. Never
 * over a real session — a signed-in user just goes to their own dashboard,
 * so the two identities can't mix. The `demo=started` marker lets `/` tell
 * "the cookie didn't stick" (cookies blocked) apart from "no session".
 */
export function GET(request: NextRequest) {
  if (getSession()) {
    return NextResponse.redirect(publicUrl(request, "/"));
  }
  const response = NextResponse.redirect(publicUrl(request, "/?demo=started"));
  attachDemoCookie(response);
  return response;
}
