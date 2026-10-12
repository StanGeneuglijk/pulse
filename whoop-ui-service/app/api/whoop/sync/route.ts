import { handleRoute } from "@/lib/apiError";
import { requireSession } from "@/lib/session";
import { triggerSync } from "@/lib/whoopClient";

export async function POST() {
  return handleRoute(() => triggerSync(requireSession()));
}
