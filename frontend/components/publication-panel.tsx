"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import type { DraftRecord, EventDetail } from "@/lib/types";

export function PublicationPanel({ draft }: { draft: DraftRecord }) {
  const [published, setPublished] = useState<EventDetail | null>(null);
  const [description, setDescription] = useState("");
  const [consent, setConsent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [loaded, setLoaded] = useState(false);
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    let active = true;
    fetch("/api/v1/planner/publications", { cache: "no-store" }).then(async response => {
      if (!response.ok) throw new Error("공개 상태를 조회하지 못했습니다.");
      const items: EventDetail[] = await response.json();
      if (!active) return;
      const current = items.find(item => item.event_id === draft.event.event_id);
      setPublished(current ?? null);
      setDescription(current?.description ?? "");
      setLoaded(true);
    }).catch((e: Error) => { if (active) setMessage(e.message); });
    return () => { active = false; };
  }, [draft.event.event_id, retry]);
  async function send(remove = false) {
    if (remove && !window.confirm("사용자 목록에서 행사 공개를 철회할까요? 기획 초안과 분석은 유지됩니다.")) return;
    setBusy(true); setMessage("");
    try {
      const response = await fetch("/api/v1/planner/publications" + (remove ? "/" + draft.event.event_id : ""), {
        method: remove ? "DELETE" : "POST", headers: { "Content-Type": "application/json" },
        body: remove ? undefined : JSON.stringify({ analysis_id: draft.analysis?.analysis_id, description, consent }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail ?? "행사 공개 요청을 처리하지 못했습니다.");
      setPublished(remove ? null : data);
      setMessage(remove ? "공개를 철회했습니다." : "사용자 목록에 공개했습니다.");
      setConsent(false);
    } catch (e) { setMessage((e as Error).message); } finally { setBusy(false); }
  }
  return <section className="panel publication-panel no-print">
    <p className="eyebrow">CONNECT WITH VISITORS</p><h2>사용자에게 행사 소개하기</h2>
    <p>마지막으로 분석한 행사명·기간·지역·장소와 아래 소개문, 시연용 수요 점수가 공개됩니다. 예산, 내부 메모와 기획 보고서는 공개하지 않습니다.</p>
    <p><strong>{draft.analysis?.request_snapshot.working_title}</strong> · {draft.analysis?.request_snapshot.start_date ?? "일정 미정"} ~ {draft.analysis?.request_snapshot.end_date ?? "일정 미정"} · {draft.analysis?.request_snapshot.region?.display_name ?? "지역 미정"} · {draft.analysis?.request_snapshot.venue?.name ?? "장소 미정"}</p>
    {!loaded && !message && <p role="status">현재 공개 상태를 확인하고 있습니다…</p>}
    <label>공개용 행사 소개<textarea disabled={!loaded || busy} maxLength={3000} rows={3} value={description} onChange={e => setDescription(e.target.value)} placeholder="방문객에게 안내할 내용만 작성해 주세요." /></label>
    <label className="publication-consent"><input disabled={!loaded || busy} type="checkbox" checked={consent} onChange={e => setConsent(e.target.checked)} />공개할 정보와 장소 정보를 확인했습니다.</label>
    <div className="button-row"><button className="button primary" disabled={!loaded || busy || !consent || !description.trim()} onClick={() => void send()}>{published ? "공개 내용 갱신" : "행사 공개"}</button>
    {published && <><Link className="button secondary" href={"/visitor/" + published.event_id}>사용자 화면 확인</Link><button className="text-button" disabled={busy} onClick={() => void send(true)}>공개 철회</button></>}</div>
    {message && <p role="status">{message}</p>}
    {!loaded && message && <button className="text-button" onClick={() => { setMessage(""); setRetry(value => value + 1); }}>공개 상태 다시 조회</button>}
  </section>;
}
