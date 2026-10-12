import { handleRoute } from "@/lib/apiError";
import { requireSession } from "@/lib/session";
import { getSyncs } from "@/lib/whoopClient";

export async function GET() {
  return handleRoute(() => getSyncs(requireSession()));
}
