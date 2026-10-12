/**
 * The sole module that talks to whoop-nutrition-service — same "one
 * narrow client per external dependency" role as whoopClient.ts /
 * insightClient.ts.
 */
import { UpstreamApiError, fetchJson } from "./apiError";
import { config } from "./config";
import type { Session } from "./session";
import type {
  ChatResponse,
  NutritionGoal,
  NutritionLogRecord,
  SetGoalBody,
} from "./types";

function authHeaders(session: Session): HeadersInit {
  return { Authorization: `Bearer ${session.readToken}` };
}

export async function sendChatMessage(
  session: Session,
  conversationId: string | null,
  message: string
): Promise<ChatResponse> {
  return fetchJson<ChatResponse>(
    "whoop-nutrition-service",
    `${config.nutritionServiceUrl}/nutrition/chat/${session.userId}`,
    {
      method: "POST",
      headers: { ...authHeaders(session), "Content-Type": "application/json" },
      body: JSON.stringify({ conversationId, message }),
    }
  );
}

/**
 * Multipart forward — can't go through fetchJson, which always sends
 * JSON. Mirrors services/nutrition/router.py's chat_audio's own field
 * names exactly: `audio` (the file) and `conversation_id` (a plain Form
 * field, not a CamelModel, so it stays snake_case on the wire).
 */
export async function sendChatAudio(
  session: Session,
  conversationId: string | null,
  audio: Blob,
  filename: string
): Promise<ChatResponse> {
  const form = new FormData();
  form.append("audio", audio, filename);
  if (conversationId) {
    form.append("conversation_id", conversationId);
  }
  const response = await fetch(
    `${config.nutritionServiceUrl}/nutrition/chat/${session.userId}/audio`,
    { method: "POST", headers: authHeaders(session), body: form, cache: "no-store" }
  );
  if (!response.ok) {
    const body = await response.text().catch(() => "");
    throw new UpstreamApiError("whoop-nutrition-service", response.status, body);
  }
  return (await response.json()) as ChatResponse;
}

// Keyed by conversation_id, not user_id — the backend's
// require_conversation_owner resolves ownership from the token itself,
// but the token still has to come from somewhere, hence `session` here.
export async function confirmMeal(
  session: Session,
  conversationId: string
): Promise<NutritionLogRecord> {
  return fetchJson<NutritionLogRecord>(
    "whoop-nutrition-service",
    `${config.nutritionServiceUrl}/nutrition/meals/confirm/${conversationId}`,
    { method: "POST", headers: authHeaders(session) }
  );
}

export async function discardMeal(session: Session, conversationId: string): Promise<void> {
  await fetchJson<void>(
    "whoop-nutrition-service",
    `${config.nutritionServiceUrl}/nutrition/meals/discard/${conversationId}`,
    { method: "POST", headers: authHeaders(session) }
  );
}

export async function listMeals(session: Session, days: number): Promise<NutritionLogRecord[]> {
  return fetchJson<NutritionLogRecord[]>(
    "whoop-nutrition-service",
    `${config.nutritionServiceUrl}/nutrition/meals/${session.userId}?days=${days}`,
    { headers: authHeaders(session) }
  );
}

export async function getGoal(session: Session): Promise<NutritionGoal | null> {
  return fetchJson<NutritionGoal | null>(
    "whoop-nutrition-service",
    `${config.nutritionServiceUrl}/nutrition/goals/${session.userId}`,
    { headers: authHeaders(session) }
  );
}

export async function setGoal(session: Session, body: SetGoalBody): Promise<NutritionGoal> {
  return fetchJson<NutritionGoal>(
    "whoop-nutrition-service",
    `${config.nutritionServiceUrl}/nutrition/goals/${session.userId}`,
    {
      method: "PUT",
      headers: { ...authHeaders(session), "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }
  );
}

export async function checkNutritionHealth(): Promise<boolean> {
  try {
    const res = await fetch(`${config.nutritionServiceUrl}/health`, { cache: "no-store" });
    return res.ok;
  } catch {
    return false;
  }
}
