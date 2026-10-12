import { handleRoute } from "@/lib/apiError";
import { requireSession } from "@/lib/session";
import { getProfile } from "@/lib/whoopClient";

export async function GET() {
  return handleRoute(() => getProfile(requireSession()));
}
