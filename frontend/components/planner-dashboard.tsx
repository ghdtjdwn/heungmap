"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { AppHeader } from "./app-header";
import { optionLabel } from "@/lib/options";
import { readDrafts, removeDraft, sampleDraft, saveDraft } from "@/lib/drafts";
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
    <main className="page-shell">
      <AppHeader />
      <section className="workspace-heading compact-heading">
        <div>
          <p className="eyebrow">PLANNING WORKSPACE</p>
          <h1>내 행사 기획</h1>
          <p>조건을 입력하고 수요·장소·운영 위험을 같은 기준으로 점검합니다.</p>
        </div>
        <Link href="/planner/new" className="button primary">새 기획 시작</Link>
      </section>

      <section className="status-grid" aria-label="기획 진행 현황">
        <article className="metric-card"><span>작성 중</span><strong>{drafts.length - analyzed}</strong><small>이 브라우저의 초안</small></article>
        <article className="metric-card"><span>분석 완료</span><strong>{analyzed}</strong><small>규칙 진단 포함</small></article>
        <article className="metric-card warning"><span>수요 모델</span><strong>Mock</strong><small>학습 모델 연결 전</small></article>
      </section>

      {!ready ? (
        <section className="panel loading-panel" aria-live="polite">저장한 기획을 확인하고 있습니다.</section>
      ) : drafts.length === 0 ? (
        <section className="panel empty-panel">
          <div className="empty-icon" aria-hidden="true">＋</div>
          <h2>아직 저장한 기획이 없습니다</h2>
          <p>빈 기획으로 시작하거나 대표 시나리오를 불러와 전체 흐름을 확인하세요.</p>
          <div className="button-row">
            <Link href="/planner/new" className="button primary">빈 기획 시작</Link>
            <button className="button secondary" onClick={() => startSample("independent")}>소규모 행사 예시</button>
            <button className="button secondary" onClick={() => startSample("large")}>대형 축제 예시</button>
          </div>
        </section>
      ) : (
        <section className="draft-section">
          <div className="section-heading">
            <h2>저장한 기획</h2>
            <span>{drafts.length}개</span>
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
                <small>마지막 저장 {formatDate(draft.updated_at)}</small>
                <div className="card-actions">
                  <Link className="button secondary" href={`/planner/new?draft=${draft.id}`}>수정하기</Link>
                  {draft.analysis && <Link className="button primary" href={`/planner/result?draft=${draft.id}`}>결과 보기</Link>}
                </div>
              </article>
            ))}
          </div>
          <div className="sample-strip">
            <div><strong>빠른 검토</strong><span>가상 데이터로 대표 흐름을 확인합니다.</span></div>
            <button className="text-button" onClick={() => startSample("independent")}>소규모 예시 추가</button>
            <button className="text-button" onClick={() => startSample("large")}>대형 예시 추가</button>
          </div>
        </section>
      )}
    </main>
  );
}
