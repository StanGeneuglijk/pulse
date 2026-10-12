import { NextRequest } from "next/server";
import { handleRoute } from "@/lib/apiError";
import { listMeals } from "@/lib/nutritionClient";
import { requireSession } from "@/lib/session";

export async function GET(request: NextRequest) {
  const days = Number(request.nextUrl.searchParams.get("days") ?? "30");
  return handleRoute(() => listMeals(requireSession(), Number.isFinite(days) ? days : 30));
}
