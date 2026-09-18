"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { AppHeader } from "./app-header";
import { MyPublications } from "./my-publications";
import { getModelStatus } from "@/lib/api";
import type { ModelStatus } from "@/lib/types";
import { optionLabel } from "@/lib/options";
import { importLegacyDrafts, readDrafts, removeDraft, sampleDraft, saveDraft } from "@/lib/drafts";
import type { DraftRecord } from "@/lib/types";

function formatDate(value: string) {
  return new Intl.DateTimeFormat("ko-KR", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }).format(new Date(value));
}

function attendanceText(value: number | undefined) {
  return value === undefined ? "목표 미정" : `목표 ${value.toLocaleString("ko-KR")}명`;
}

export function PlannerDashboard() {
  const router = useRouter();
  const [drafts, setDrafts] = useState<DraftRecord[]>([]);
  const [ready, setReady] = useState(false);
  const [importMessage, setImportMessage] = useState("");
  function importPrevious() {
    if (!window.confirm("로그인 기능 도입 전에 이 브라우저에 저장한 초안을 현재 계정으로 복사할까요? 원본은 유지됩니다.")) return;
    try { setImportMessage(importLegacyDrafts() + "개 초안을 가져왔습니다."); setDrafts(readDrafts()); }
    catch { setImportMessage("이전 초안을 읽거나 저장하지 못했습니다."); }
  }

  useEffect(() => {
    const frame = window.requestAnimationFrame(() => {
      setDrafts(readDrafts());
      setReady(true);
    });
    return () => window.cancelAnimationFrame(frame);
  }, []);

  function startSample(kind: "independent" | "large") {
    const draft = saveDraft(sampleDraft(kind));
    router.push(`/planner/new?draft=${draft.id}`);
  }

  function deleteDraft(id: string) {
    if (!window.confirm("이 기기에 저장된 초안을 삭제할까요? 삭제하면 되돌릴 수 없습니다.")) return;
    removeDraft(id);
    setDrafts(readDrafts());
  }

  const analyzed = drafts.filter((draft) => draft.status === "analyzed").length;

  return (
    <main className="page-shell planner-dashboard-shell">
      <AppHeader />
      <section className="workspace-heading compact-heading planner-dashboard-hero">
        <div className="planner-hero-copy">
          <p className="eyebrow">PLANNING WORKSPACE · 나의 기획실</p>
          <h1>떠오른 아이디어를<br /><em>근거 있는 행사로.</em></h1>
          <p>조건을 하나씩 정리하고 지역 방문수요·장소·운영 위험을 같은 기준으로 점검하세요.</p>
        </div>
        <div className="planner-hero-action">
          <span>새로운 아이디어가 있나요?</span>
          <Link href="/planner/new" className="button primary">새 기획 시작 <b aria-hidden="true">↗</b></Link>
        </div>
      </section>

      <section className="status-grid" aria-label="기획 진행 현황">
        <article className="metric-card"><span><i aria-hidden="true">01</i> 작성 중</span><strong>{drafts.length - analyzed}<small>개</small></strong><p>이 브라우저에 저장된 초안</p></article>
        <article className="metric-card"><span><i aria-hidden="true">02</i> 분석 완료</span><strong>{analyzed}<small>개</small></strong><p>수요 범위와 기획 보고서 생성</p></article>
        <ModelStatusCard />
      </section>

      <section className="planner-storage-row" aria-label="초안 저장 안내">
        <div><span aria-hidden="true">⌁</span><p><strong>초안은 현재 브라우저에 자동 저장됩니다.</strong><small>로그인 전에 만든 초안이 있다면 현재 계정으로 복사할 수 있어요.</small></p></div>
        <button className="text-button" onClick={importPrevious}>이전 초안 가져오기 <span aria-hidden="true">→</span></button>
      </section>
      {importMessage && <p className="planner-inline-status" role="status">{importMessage}</p>}
      <MyPublications />

      {!ready ? (
        <section className="panel loading-panel" aria-live="polite">저장한 기획을 확인하고 있습니다.</section>
      ) : drafts.length === 0 ? (
        <section className="panel empty-panel planner-empty-panel">
          <div className="planner-empty-main">
            <span className="planner-empty-index">YOUR FIRST PLAN</span>
            <div className="empty-icon" aria-hidden="true">＋</div>
            <h2>첫 번째 행사를<br />기획해 볼까요?</h2>
            <p>아직 모든 조건을 몰라도 괜찮아요. 7단계 질문을 따라가며 아이디어부터 정리할 수 있습니다.</p>
            <Link href="/planner/new" className="button primary">빈 기획으로 시작 <span aria-hidden="true">↗</span></Link>
          </div>
          <div className="planner-starters">
            <header><span>QUICK START</span><strong>예시로 먼저 둘러보기</strong></header>
            <button onClick={() => startSample("independent")}><span aria-hidden="true">✦</span><div><strong>소규모 독립 행사</strong><small>적은 예산·작은 팀으로 시작</small></div><b aria-hidden="true">→</b></button>
            <button onClick={() => startSample("large")}><span aria-hidden="true">⌖</span><div><strong>대형 지역 축제</strong><small>수요·장소·운영 위험 점검</small></div><b aria-hidden="true">→</b></button>
          </div>
        </section>
      ) : (
        <section className="draft-section">
          <div className="section-heading">
            <div><p className="eyebrow">SAVED PLANS</p><h2>이어갈 기획</h2></div>
            <span>{drafts.length}개의 기획</span>
          </div>
          <div className="draft-grid">
            {drafts.map((draft) => (
              <article className="draft-card" key={draft.id}>
                <div className="card-topline">
                  <span className={`status-pill ${draft.status}`}>{draft.status === "analyzed" ? `분석 v${draft.version}` : `작성 ${draft.current_step + 1}/7`}</span>
                  <button className="text-button danger-text" onClick={() => deleteDraft(draft.id)} aria-label={`${draft.event.working_title || "이름 없는 기획"} 삭제`}>삭제</button>
                </div>
                <h3>{draft.event.working_title || "이름 없는 기획"}</h3>
                <p>{optionLabel(draft.event.event_type)} · {draft.event.region?.display_name || "지역 미정"} · {attendanceText(draft.event.target_attendance)}</p>
                <div className="draft-progress" aria-label={`작성 진행 ${draft.status === "analyzed" ? 7 : draft.current_step + 1}/7`}><span style={{ width: `${((draft.status === "analyzed" ? 7 : draft.current_step + 1) / 7) * 100}%` }} /></div>
                <small>마지막 저장 {formatDate(draft.updated_at)}</small>
                <div className="card-actions">
                  <Link className="button secondary" href={`/planner/new?draft=${draft.id}`}>수정하기</Link>
                  {draft.analysis && <Link className="button primary" href={`/planner/result?draft=${draft.id}`}>결과 보기</Link>}
                </div>
              </article>
            ))}
          </div>
          <div className="sample-strip">
            <div><strong>예시 기획으로 빠르게 둘러보기</strong><span>가상 입력으로 분석·보고서 흐름을 확인합니다.</span></div>
            <button className="text-button" onClick={() => startSample("independent")}>소규모 예시 추가</button>
            <button className="text-button" onClick={() => startSample("large")}>대형 예시 추가</button>
          </div>
        </section>
      )}
    </main>
  );
}

const STALE_WARNING_DAYS = 14;

function shortDate(value?: string): string {
  if (!value) return "-";
  const [, month, day] = value.split("-");
  return `${Number(month)}/${Number(day)}`;
}

/** 채택 수요 모델의 자료 기준일과 예측 가능 기간. 만료가 가까우면 재학습 안내를 보여 준다. */
function ModelStatusCard() {
  const [status, setStatus] = useState<ModelStatus | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let active = true;
    getModelStatus().then((value) => { if (active) setStatus(value); }).catch(() => { if (active) setFailed(true); });
    return () => { active = false; };
  }, []);
  const label = <span><i aria-hidden="true">03</i> 수요 모델</span>;
  if (failed || status?.status === "unavailable") {
    return <article className="metric-card model-card warning">{label}<strong>확인 불가</strong><p>{status?.reason ?? "모델 상태를 불러오지 못했습니다. 기획 분석은 계속할 수 있습니다."}</p></article>;
  }
  if (!status) return <article className="metric-card model-card">{label}<strong>D-30</strong><p>시군구 방문자-일 예측 · 상태 확인 중</p></article>;
  const soon = status.status === "stale" || (status.days_until_stale ?? 0) <= STALE_WARNING_DAYS;
  return <article className={`metric-card model-card ${soon ? "warning" : ""}`}>
    {label}
    <strong>{status.status === "stale" ? "갱신 필요" : `~${shortDate(status.last_predictable_target_date)}`}{status.status !== "stale" && <small>예측</small>}</strong>
    <p>{status.status === "stale"
      ? "자료가 오래돼 예측을 제공하지 않습니다. 서버 재학습 상태를 확인하세요."
      : `D-30 시군구 방문자-일 · 관람객 수 아님 · 자료 ${shortDate(status.data_end)}까지, ${status.days_until_stale}일 뒤 갱신${soon ? " (곧 만료)" : ""} · 시군구 ${status.regions ?? "-"}곳`}</p>
  </article>;
}
