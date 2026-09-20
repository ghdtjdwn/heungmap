"use client";

import { useEffect, useRef, useState } from "react";
import { BrandLink } from "./brand-link";
import { useSession } from "./session-provider";
import { ArrowDownIcon, ArrowUpRightIcon, PinIcon, SparkleIcon } from "./icons";

function useReveal(deps: unknown[]) {
  const rootRef = useRef<HTMLElement>(null);
  useEffect(() => {
    const root = rootRef.current;
    if (!root) return;
    const els = root.querySelectorAll<HTMLElement>("[data-reveal]");
    const io = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) { entry.target.classList.add("is-visible"); io.unobserve(entry.target); }
      });
    }, { threshold: 0.15, rootMargin: "0px 0px -60px 0px" });
    els.forEach((el) => io.observe(el));
    return () => io.disconnect();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  return rootRef;
}


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
  const rootRef = useReveal([onboarding]);
  if (onboarding) return <main className="welcome-shell onboarding-shell" ref={rootRef}>
    <header className="onboarding-nav"><BrandLink /><span>나에게 맞는 시작점 고르기</span></header>
    <section className="welcome-heading"><h1>오늘 시작할 흥을<br />선택하세요</h1><p>행사를 만들거나, 다음에 즐길 축제를 찾아보세요.<br />선택은 서비스 안에서 언제든 바꿀 수 있습니다.</p></section>
    <div className="role-grid onboarding-role-grid">
      <button disabled={busy} data-reveal style={{ transitionDelay: "0ms" }} className="role-card planner-role" onClick={() => void run(() => chooseRole("planner"))}><span className="role-card-number">01</span><span className="role-card-kicker">기획자</span><span className="role-card-symbol" aria-hidden="true"><SparkleIcon /></span><h2>행사를 기획하고 싶어요</h2><p>아이디어를 단계별로 정리하고, 지역 방문수요와 장소 근거를 함께 비교합니다.</p><strong>기획자로 시작 <span aria-hidden="true"><ArrowUpRightIcon /></span></strong></button>
      <button disabled={busy} data-reveal style={{ transitionDelay: "90ms" }} className="role-card visitor-role" onClick={() => void run(() => chooseRole("visitor"))}><span className="role-card-number">02</span><span className="role-card-kicker">방문객</span><span className="role-card-symbol" aria-hidden="true"><PinIcon /></span><h2>즐길 행사를 찾고 있어요</h2><p>날짜와 지역으로 축제를 찾고, 지도·달력과 주변 관광정보를 한 번에 살펴봅니다.</p><strong>방문객으로 시작 <span aria-hidden="true"><ArrowUpRightIcon /></span></strong></button>
    </div>{error && <p className="welcome-error" role="alert">{error}</p>}
  </main>;
  return <main className="welcome-shell welcome-home" ref={rootRef}>
    <header className="welcome-nav"><BrandLink /><nav aria-label="소개 페이지"><a href="#flow">이용 방법</a><a href="#services">서비스</a></nav><span className="welcome-data-chip">출처 ⓒ한국관광공사</span><button className="button primary" disabled={busy} onClick={() => void run(login)}>{session?.user ? "내 서비스로 이동" : "로그인"}</button></header>
    <section className="welcome-hero">
      <div className="welcome-copy" data-reveal><h1>지역의 흐름을 읽고,<br /><em>다음 흥을 만듭니다.</em></h1><p className="welcome-description">행사를 만드는 사람과 즐기는 사람이 같은 데이터를 보고 계획하고 발견합니다.</p><div className="welcome-actions"><button className="button primary welcome-cta" disabled={busy} onClick={() => void run(session?.user?.role ? () => chooseRole(session.user!.role!) : login)}>{busy ? "연결 중…" : "흥할지도 시작하기"}<span aria-hidden="true"><ArrowUpRightIcon /></span></button><a href="#services" className="welcome-text-link">두 가지 서비스 보기 <span aria-hidden="true"><ArrowDownIcon /></span></a></div><p className="welcome-caption">{session?.mode === "mock" ? "계정 없이 로그인·역할 선택 흐름을 체험할 수 있어요." : "Google 계정으로 시작하세요."}</p></div>
      <div className="welcome-art" data-reveal style={{ transitionDelay: "120ms" }} aria-label="지역 방문수요와 축제 위치를 표현한 지도 그래픽"><div className="art-grid" /><div className="art-route" /><span className="art-pin pin-one"><i aria-hidden="true" />서울 · 기획 중</span><span className="art-pin pin-two"><i aria-hidden="true" />부산 · 이번 주말</span><div className="art-center"><span>지역의 흐름 위에</span><strong>흥</strong><small>HEUNGMAP</small></div><div className="art-data-card"><span>D-30 지역 방문수요</span><strong>방문자-일 범위 제공</strong><small>특정 축제 관람객 수가 아닙니다</small></div><span className="art-label">데이터로 보는 축제</span></div>
    </section>
    {error && <p className="welcome-error" role="alert">{error}</p>}
    <section className="welcome-proof" aria-label="흥할지도 핵심 근거"><div data-reveal style={{ transitionDelay: "0ms" }}><span>01</span><strong>한국관광공사 관광정보</strong><small>축제·관광정보의 기준 데이터</small></div><div data-reveal style={{ transitionDelay: "80ms" }}><span>02</span><strong>D-30 지역 방문수요</strong><small>시군구 방문자-일 예측 범위</small></div><div data-reveal style={{ transitionDelay: "160ms" }}><span>03</span><strong>기획에서 탐색까지</strong><small>공개한 행사를 방문객 화면으로 연결</small></div></section>
    <section id="flow" className="welcome-flow"><header data-reveal><h2>하나의 행사가<br />두 사람의 경험이 되기까지</h2></header><ol><li data-reveal style={{ transitionDelay: "0ms" }}><span>01</span><div><strong>조건을 정리하고</strong><p>지역·일정·규모와 아직 모르는 조건을 단계별로 입력합니다.</p></div></li><li data-reveal style={{ transitionDelay: "90ms" }}><span>02</span><div><strong>근거를 확인하고</strong><p>한국관광공사 장소 정보와 지역 방문수요 범위, 해석 한계를 함께 봅니다.</p></div></li><li data-reveal style={{ transitionDelay: "180ms" }}><span>03</span><div><strong>세상에 공개합니다</strong><p>확정한 행사만 공개해 방문객의 목록·지도·달력으로 이어집니다.</p></div></li></ol></section>
    <section id="services" className="welcome-services"><header data-reveal><h2>만들고 싶은 사람도,<br />찾아가고 싶은 사람도.</h2></header><div className="role-grid">
      <article data-reveal style={{ transitionDelay: "0ms" }} className="role-card planner-role"><span className="role-card-kicker">기획자용</span><span className="role-card-symbol" aria-hidden="true"><SparkleIcon /></span><h3>막연한 아이디어를<br />구체적인 기획으로</h3><p>단계별 입력, 장소 탐색, 수요 범위와 기획 보고서를 한 흐름에서 확인합니다.</p><ul><li>7단계 기획 입력</li><li>지역 방문수요 근거</li><li>행사 공개·갱신</li></ul></article>
      <article data-reveal style={{ transitionDelay: "100ms" }} className="role-card visitor-role"><span className="role-card-kicker">방문객용</span><span className="role-card-symbol" aria-hidden="true"><PinIcon /></span><h3>이번 주말의 즐거움을<br />지도와 달력에서</h3><p>한국관광공사 축제와 기획자가 공개한 행사를 날짜·지역별로 발견합니다.</p><ul><li>목록·지도·달력</li><li>주변 관광·숙박</li><li>출처와 수요 범위</li></ul></article>
    </div></section>
    <section className="welcome-final-cta" data-reveal><h2>다음 흥을<br />여기서 시작하세요.</h2><button className="button primary welcome-cta" disabled={busy} onClick={() => void run(session?.user?.role ? () => chooseRole(session.user!.role!) : login)}>지금 시작하기 <span aria-hidden="true"><ArrowUpRightIcon /></span></button></section>
    <footer className="welcome-footer"><BrandLink /><div><p>행사·관광정보: 출처 ⓒ한국관광공사 · 지도: Kakao Maps</p><small>수요 지표는 한국관광공사 지역별 방문자 데이터로 학습·검증한 행사기간 시군구 방문자-일 예측이며 특정 축제 관람객·티켓 수요·실제 혼잡이 아닙니다.</small></div><span>2026 Tourism Data Contest · Task 9</span></footer>
  </main>;
}
