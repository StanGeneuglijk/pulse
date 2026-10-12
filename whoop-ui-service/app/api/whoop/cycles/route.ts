import { handleRoute } from "@/lib/apiError";
import { requireSession } from "@/lib/session";
import { getCycles } from "@/lib/whoopClient";

export async function GET() {
  return handleRoute(() => getCycles(requireSession()));
}
