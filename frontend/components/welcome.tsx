"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useSession } from "./session-provider";

export function Welcome({ onboarding = false }: { onboarding?: boolean }) {
  const { session, login, chooseRole } = useSession();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    if (new URLSearchParams(window.location.search).has("auth_error")) {
      const frame = window.requestAnimationFrame(() => setError("로그인을 완료하지 못했습니다. 취소했거나 요청이 만료되었을 수 있습니다. 다시 시도해 주세요."));
      return () => window.cancelAnimationFrame(frame);
    }
  }, []);
  async function run(action: () => Promise<void>) {
    setBusy(true); setError("");
    try { await action(); } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }
  if (onboarding) return <main className="welcome-shell">
    <Link href="/" className="brand">흥할지도</Link>
    <section className="welcome-heading"><p className="eyebrow">YOUR NEXT EXPERIENCE</p><h1>어떤 흥을 찾고 있나요?</h1><p>선택한 서비스로 다음 로그인부터 바로 안내해 드려요.<br />서비스는 언제든 바꿀 수 있습니다.</p></section>
    <div className="role-grid">
      <button disabled={busy} className="role-card" onClick={() => void run(() => chooseRole("planner"))}><span>01 · PLANNER</span><h2>행사를 기획하고 싶어요</h2><p>아이디어를 정리하고 장소와 조건을 비교하며,<br />근거 있는 기획안을 완성해 보세요.</p><strong>기획자로 시작 →</strong></button>
      <button disabled={busy} className="role-card visitor-role" onClick={() => void run(() => chooseRole("visitor"))}><span>02 · VISITOR</span><h2>즐길 행사를 찾고 있어요</h2><p>날짜와 지역에 맞는 축제를 찾고,<br />주변 즐길 거리까지 한 번에 살펴보세요.</p><strong>사용자로 시작 →</strong></button>
    </div>{error && <p role="alert">{error}</p>}
  </main>;
  return <main className="welcome-shell">
    <header className="welcome-nav"><Link href="/" className="brand">흥할지도</Link><a href="#services">서비스 소개</a><button className="button primary" disabled={busy} onClick={() => void run(login)}>{session?.user ? "내 서비스로 이동" : "로그인"}</button></header>
    <section className="welcome-hero">
      <div><p className="eyebrow">계획하는 설렘부터, 함께하는 즐거움까지</p><h1>여기서 시작하는<br /><em>우리의 다음 흥.</em></h1><p className="welcome-description">행사를 만드는 사람과 즐기는 사람을 잇는 지도.<br />관광 데이터와 함께 더 나은 계획, 더 즐거운 하루를 찾아보세요.</p><button className="button primary" disabled={busy} onClick={() => void run(session?.user?.role ? () => chooseRole(session.user!.role!) : login)}>{busy ? "연결 중…" : "흥할지도 시작하기 →"}</button><p className="welcome-caption">{session?.mode === "mock" ? "지금은 계정 없이 로그인 흐름을 체험할 수 있어요." : "Google 계정으로 시작하세요."}</p></div>
      <div className="welcome-art" aria-label="기획과 방문을 잇는 행사 지도"><div className="art-orbit" /><span className="art-pin pin-one">만드는 즐거움</span><strong>흥</strong><span className="art-pin pin-two">찾아가는 설렘</span><span className="art-label">PLAN · DISCOVER · CONNECT</span></div>
    </section>
    {error && <p role="alert">{error}</p>}
    <section id="services" className="role-grid">
      <article className="role-card"><span>FOR PLANNERS</span><h2>막연한 아이디어를<br />구체적인 기획으로</h2><p>단계별 기획 입력, 장소 탐색, 조건 비교와 기획 보고서까지. 완성한 행사 정보를 사용자에게 소개하세요.</p></article>
      <article className="role-card visitor-role"><span>FOR VISITORS</span><h2>이번 주말의 즐거움을<br />지도와 달력에서</h2><p>한국관광공사 축제 정보와 기획자가 공개한 행사를 찾아보세요. 일정, 장소, 주변 관광정보를 함께 확인할 수 있어요.</p></article>
    </section>
    <footer className="welcome-footer"><strong>흥할지도</strong><p>행사·관광정보: 한국관광공사 TourAPI · 지도: Kakao Maps</p><small>수요 지표는 현재 시연용 상대지수이며 실제 관람객 수나 검증된 예측이 아닙니다.</small></footer>
  </main>;
}
