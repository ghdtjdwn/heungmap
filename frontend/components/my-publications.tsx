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
  return <section className="panel publication-panel"><h2>공개한 행사</h2><p>이 서버에 저장된 공개 행사입니다. 초안을 삭제해도 공개 상태는 유지되므로 여기서 별도로 철회할 수 있습니다.</p>
    {items.length ? items.map(item => <div className="button-row" key={item.event_id}><Link href={"/visitor/" + item.event_id}>{item.title}</Link><button className="text-button" onClick={() => void withdraw(item.event_id)}>공개 철회</button></div>) : <p>현재 공개한 행사가 없습니다.</p>}
    {message && <p role="status">{message}</p>}
  </section>;
}
