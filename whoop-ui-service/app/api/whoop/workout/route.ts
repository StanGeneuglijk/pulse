import { handleRoute } from "@/lib/apiError";
import { requireSession } from "@/lib/session";
import { getWorkout } from "@/lib/whoopClient";

export async function GET() {
  return handleRoute(() => getWorkout(requireSession()));
}
