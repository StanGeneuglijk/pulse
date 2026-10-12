import { NextRequest } from "next/server";
import { handleRoute } from "@/lib/apiError";
import { sendChatAudio } from "@/lib/nutritionClient";
import { requireSession } from "@/lib/session";

export async function POST(request: NextRequest) {
  const form = await request.formData();
  const audio = form.get("audio");
  const conversationId = form.get("conversationId");
  if (!(audio instanceof Blob)) {
    return handleRoute(async () => {
      throw new Error("Missing audio file");
    });
  }
  return handleRoute(() =>
    sendChatAudio(
      requireSession(),
      typeof conversationId === "string" ? conversationId : null,
      audio,
      "recording.webm"
    )
  );
}
