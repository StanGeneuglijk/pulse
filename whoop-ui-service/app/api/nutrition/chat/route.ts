import { NextRequest } from "next/server";
import { handleRoute } from "@/lib/apiError";
import { sendChatMessage } from "@/lib/nutritionClient";
import { requireSession } from "@/lib/session";

export async function POST(request: NextRequest) {
  const body = await request.json().catch(() => ({}));
  const conversationId = (body.conversationId ?? null) as string | null;
  const message = (body.message ?? "") as string;
  return handleRoute(() => sendChatMessage(requireSession(), conversationId, message));
}
