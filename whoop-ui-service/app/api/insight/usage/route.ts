import { handleRoute } from "@/lib/apiError";
import { getUsage } from "@/lib/insightClient";
import { requireSession } from "@/lib/session";

export async function GET() {
  return handleRoute(() => getUsage(requireSession()));
}
