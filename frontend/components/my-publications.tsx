"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import type { EventDetail } from "@/lib/types";

export function MyPublications() {
  const [items, setItems] = useState<EventDetail[]>([]);
  const [message, setMessage] = useState("");
  useEffect(() => {
    let active = true;
    fetch("/api/v1/planner/publications", { cache: "no-store" }).then(async response => {
      if (!response.ok) throw new Error("공개 행사 목록을 불러오지 못했습니다.");
      const data = await response.json();
      if (active) setItems(data);
    }).catch((e: Error) => { if (active) setMessage(e.message); });
    return () => { active = false; };
  }, []);
  async function withdraw(id: string) {
    if (!window.confirm("이 행사를 사용자 목록에서 내릴까요?")) return;
    try {
      const response = await fetch("/api/v1/planner/publications/" + id, { method: "DELETE" });
      if (!response.ok) throw new Error("공개 철회에 실패했습니다. 다시 시도해 주세요.");
      setItems(current => current.filter(item => item.event_id !== id));
      setMessage("행사 공개를 철회했습니다.");
    } catch (e) { setMessage((e as Error).message); }
  }
  return <section className="panel publication-panel planner-publication-panel"><header><div><h2>방문객에게 공개한 행사</h2></div><span className="publication-count">{items.length}개 공개 중</span></header><p>공개 행사는 방문객 목록·지도·달력에 표시됩니다. 초안 삭제와 공개 철회는 별도로 관리됩니다.</p>
    {items.length ? <div className="publication-list">{items.map(item => <div className="button-row" key={item.event_id}><Link href={"/visitor/" + item.event_id}>{item.title}<span aria-hidden="true">↗</span></Link><button className="text-button" onClick={() => void withdraw(item.event_id)}>공개 철회</button></div>)}</div> : <div className="publication-empty"><span aria-hidden="true">◎</span><p><strong>아직 공개한 행사가 없습니다.</strong><small>분석 결과에서 공개할 정보를 확인한 뒤 방문객 화면에 소개할 수 있어요.</small></p></div>}
    {message && <p role="status">{message}</p>}
  </section>;
}
