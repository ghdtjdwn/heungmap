import Link from "next/link";

export function AppHeader({ detail }: { detail?: string }) {
  return (
    <header className="topbar">
      <Link href="/planner" className="brand">흥할지도</Link>
      <span className="mode-chip">기획자 모드</span>
      {detail && <span className="header-detail">{detail}</span>}
      <span className="local-note">로그인 없이 이 기기에만 저장</span>
    </header>
  );
}
