import { handleRoute } from "@/lib/apiError";
import { requireSession } from "@/lib/session";
import { getRecovery } from "@/lib/whoopClient";

export async function GET() {
  return handleRoute(() => getRecovery(requireSession()));
}
