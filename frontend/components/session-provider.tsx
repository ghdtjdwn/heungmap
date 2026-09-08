"use client";

import { Fragment, createContext, useCallback, useContext, useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { setDraftOwner } from "@/lib/drafts";

type Role = "planner" | "visitor";
type User = { id: string; name: string; role: Role | null; provider: "mock" | "google" };
type Session = { user: User | null; mode: "mock" | "google" };
const Context = createContext<{
  session: Session | null; login: () => Promise<void>; chooseRole: (role: Role) => Promise<void>;
  logout: () => Promise<void>;
} | null>(null);

async function request(path: string, body?: object): Promise<Session> {
  const response = await fetch("/api/v1/auth/" + path, {
    method: body ? "POST" : "GET", credentials: "same-origin", cache: "no-store",
    headers: body ? { "Content-Type": "application/json" } : {},
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!response.ok) throw new Error(response.status === 401 ? "세션이 만료되었습니다. 다시 로그인해 주세요." : "로그인 서버에 연결하지 못했습니다. 잠시 뒤 다시 시도해 주세요.");
  return response.json();
}

export function SessionProvider({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [error, setError] = useState("");
  const pathname = usePathname();
  const router = useRouter();
  const accept = useCallback((next: Session) => {
    setDraftOwner(next.user?.id ?? null);
    setSession(next);
    setError("");
  }, []);
  const refresh = useCallback(() => request("session").then(accept).catch((e: Error) => setError(e.message)), [accept]);
  useEffect(() => {
    void refresh();
    const onFocus = () => { void refresh(); };
    window.addEventListener("focus", onFocus);
    return () => window.removeEventListener("focus", onFocus);
  }, [refresh]);
  const protectedPage = pathname.startsWith("/planner") || pathname.startsWith("/visitor") || pathname === "/onboarding";
  useEffect(() => {
    if (!session) return;
    if (protectedPage && !session.user) router.replace("/");
    else if (session.user && !session.user.role && pathname !== "/onboarding") router.replace("/onboarding");
  }, [session, pathname, protectedPage, router]);
  async function login() {
    if (session?.user) { router.push(session.user.role ? "/" + session.user.role : "/onboarding"); return; }
    // A full navigation is required for the backend OAuth redirect (not a Next.js page).
    // eslint-disable-next-line @next/next/no-location-assign-relative-destination
    if (session?.mode === "google") { window.location.assign("/api/v1/auth/google"); return; }
    const next = await request("mock", {});
    accept(next);
    router.push(next.user?.role ? "/" + next.user.role : "/onboarding");
  }
  async function chooseRole(role: Role) {
    const next = await request("role", { role });
    accept(next);
    router.push("/" + role);
  }
  async function logout() {
    await request("logout", {});
    accept({ user: null, mode: session?.mode ?? "mock" });
    router.replace("/");
  }
  if (error) return <main className="page-shell"><section className="panel empty-panel" role="alert"><h1>연결을 확인해 주세요</h1><p>{error}</p><button className="button primary" onClick={() => void refresh()}>다시 시도</button></section></main>;
  if (!session || (protectedPage && !session.user) || (session.user && !session.user.role && pathname !== "/onboarding")) return <main className="page-shell" role="status">로그인 상태를 확인하고 있습니다…</main>;
  return <Context.Provider value={{ session, login, chooseRole, logout }}><Fragment key={session.user?.id ?? "guest"}>{children}</Fragment></Context.Provider>;
}

export function useSession() {
  const context = useContext(Context);
  if (!context) throw new Error("SessionProvider is required");
  return context;
}
