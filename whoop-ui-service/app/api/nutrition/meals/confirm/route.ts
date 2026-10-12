import { NextRequest } from "next/server";
import { handleRoute } from "@/lib/apiError";
import { confirmMeal } from "@/lib/nutritionClient";
import { requireSession } from "@/lib/session";

export async function POST(request: NextRequest) {
  const body = await request.json().catch(() => ({}));
  const conversationId = body.conversationId as string;
  return handleRoute(() => confirmMeal(requireSession(), conversationId));
}
