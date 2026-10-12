import { handleRoute } from "@/lib/apiError";
import { requireSession } from "@/lib/session";
import { getSleep } from "@/lib/whoopClient";

export async function GET() {
  return handleRoute(() => getSleep(requireSession()));
}
