"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { useSession } from "./session-provider";

export function AppHeader({ detail }: { detail?: string }) {
  const pathname = usePathname();
  const isVisitor = pathname.startsWith("/visitor");
  const { session, chooseRole, logout } = useSession();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function run(action: () => Promise<void>) {
    setBusy(true); setError("");
    try { await action(); } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }
  return (
    <header className="topbar">
      <Link href="/" className="brand">흥할지도</Link>
      <span className="mode-chip">{isVisitor ? "방문객 모드" : "기획자 모드"}</span>
      {detail && <span className="header-detail">{detail}</span>}
      <span className="local-note">{session?.user?.provider === "mock" ? "체험 계정" : session?.user?.name} · 초안은 이 브라우저에 저장</span>
      <button disabled={busy} onClick={() => void run(() => chooseRole(isVisitor ? "planner" : "visitor"))} className="text-button">{isVisitor ? "기획자 모드로" : "사용자 모드로"}</button>
      <button disabled={busy} onClick={() => void run(logout)} className="text-button">로그아웃</button>
      {error && <span role="alert">{error}</span>}
    </header>
  );
}
