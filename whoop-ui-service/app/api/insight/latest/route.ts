import { NextRequest } from "next/server";
import { handleRoute } from "@/lib/apiError";
import { getLatestInsight } from "@/lib/insightClient";
import { requireSession } from "@/lib/session";
import type { InsightPeriod } from "@/lib/types";

export async function GET(request: NextRequest) {
  const period = (request.nextUrl.searchParams.get("period") ?? "weekly") as InsightPeriod;
  return handleRoute(() => getLatestInsight(requireSession(), period));
}
