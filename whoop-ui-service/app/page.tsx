import { redirect } from "next/navigation";
import { Dashboard } from "@/components/Dashboard";
import { getCaller } from "@/lib/session";

export default function Page({ searchParams }: { searchParams: { demo?: string } }) {
  const caller = getCaller();
  if (!caller) {
    // Just came from /demo/start but no cookie arrived: the browser blocks cookies.
    redirect(searchParams.demo === "started" ? "/login?error=cookies_blocked" : "/login");
  }
  return caller.kind === "demo" ? <Dashboard demo /> : <Dashboard />;
}
