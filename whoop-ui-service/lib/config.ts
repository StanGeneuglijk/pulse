/**
 * Server-only endpoint config, read once per process. No secrets live
 * here anymore — the per-user credential (a `read_token`) comes from
 * `lib/session.ts`'s cookie on every request instead of a fixed
 * operator key baked in at boot, since this app now serves whoever is
 * actually logged in rather than one config-pinned `WHOOP_USER_ID`.
 * Still only ever imported by `app/api/*` route handlers and
 * `lib/*Client.ts` — same boundary as before, just narrower now that
 * there's no key to leak.
 */

function required(name: string): string {
  const value = process.env[name];
  if (!value) {
    throw new Error(`Missing required env var: ${name} (see .env.example)`);
  }
  return value;
}

export const config = {
  whoopServiceUrl: required("WHOOP_SERVICE_URL"),
  insightServiceUrl: required("INSIGHT_SERVICE_URL"),
  nutritionServiceUrl: required("NUTRITION_SERVICE_URL"),
};
