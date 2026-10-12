import { NextRequest } from "next/server";
import { handleRoute } from "@/lib/apiError";
import { getGoal, setGoal } from "@/lib/nutritionClient";
import { requireSession } from "@/lib/session";
import type { SetGoalBody } from "@/lib/types";

export async function GET() {
  return handleRoute(() => getGoal(requireSession()));
}

export async function PUT(request: NextRequest) {
  const body = (await request.json().catch(() => ({}))) as SetGoalBody;
  return handleRoute(() => setGoal(requireSession(), body));
}
