import { NextRequest } from "next/server";
import { handleRoute } from "@/lib/apiError";
import { generateInsight } from "@/lib/insightClient";
import { requireSession } from "@/lib/session";
import type { InsightPeriod } from "@/lib/types";

export async function POST(request: NextRequest) {
  const body = await request.json().catch(() => ({}));
  const period = (body.period ?? "weekly") as InsightPeriod;
  return handleRoute(() => generateInsight(requireSession(), period));
}
