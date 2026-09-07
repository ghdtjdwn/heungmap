"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export function AppHeader({ detail }: { detail?: string }) {
  const pathname = usePathname();
  const isVisitor = pathname.startsWith("/visitor");
  return (
    <header className="topbar">
      <Link href={isVisitor ? "/visitor" : "/planner"} className="brand">흥할지도</Link>
      <span className="mode-chip">{isVisitor ? "방문객 모드" : "기획자 모드"}</span>
      {detail && <span className="header-detail">{detail}</span>}
      <span className="local-note">{isVisitor ? "한국관광공사 TourAPI 행사 정보" : "로그인 없이 이 기기에만 저장"}</span>
      <Link href={isVisitor ? "/planner" : "/visitor"} className="mode-switch">{isVisitor ? "기획자 모드로" : "방문객 모드로"}</Link>
    </header>
  );
}
