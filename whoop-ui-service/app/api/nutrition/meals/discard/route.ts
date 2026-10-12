import { NextRequest } from "next/server";
import { handleRoute } from "@/lib/apiError";
import { discardMeal } from "@/lib/nutritionClient";
import { requireSession } from "@/lib/session";

export async function POST(request: NextRequest) {
  const body = await request.json().catch(() => ({}));
  const conversationId = body.conversationId as string;
  return handleRoute(() => discardMeal(requireSession(), conversationId));
}
