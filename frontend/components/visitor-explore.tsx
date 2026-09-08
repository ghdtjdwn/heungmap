"use client";

import Image from "next/image";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { FormEvent, useEffect, useMemo, useState } from "react";

import { AppHeader } from "@/components/app-header";
import { VisitorEventMap } from "@/components/visitor-event-map";
import { ApiError, listEvents } from "@/lib/api";
import type { EventListQuery, EventSummary } from "@/lib/types";
import { filtersToSearchParams, invalidFilterMessage, parseFiltersFromSearchParams } from "@/lib/visitor-filters";

type LoadState =
  | { status: "loading"; items: EventSummary[] }
  | { status: "ready"; items: EventSummary[]; page: number; pageSize: number; totalCount: number }
  | { status: "error"; items: EventSummary[]; message: string; retryable: boolean };

function formatDateRange(event: EventSummary): string {
  const start = new Intl.DateTimeFormat("ko-KR", { month: "short", day: "numeric", weekday: "short" }).format(new Date(`${event.start_date}T00:00:00`));
  const end = new Intl.DateTimeFormat("ko-KR", { month: "short", day: "numeric", weekday: "short" }).format(new Date(`${event.end_date}T00:00:00`));
  return event.start_date === event.end_date ? start : `${start} – ${end}`;
}

function filterSummary(filters: EventListQuery): string {
  const parts = [
    filters.query && `검색어 “${filters.query}”`,
    filters.start_date && filters.end_date && `${filters.start_date}~${filters.end_date}`,
    filters.area_code && `지역코드 ${filters.area_code}`,
  ].filter(Boolean);
  return parts.length ? parts.join(" · ") : "오늘부터 90일 이내 · 전국";
}

function VisitorExploreView({ searchParamsValue, selectedEventId }: { searchParamsValue: string; selectedEventId?: string }) {
  const router = useRouter();
  const rawParams = useMemo(() => new URLSearchParams(searchParamsValue), [searchParamsValue]);
  const filters = useMemo(() => parseFiltersFromSearchParams(rawParams), [rawParams]);
  const urlWarning = invalidFilterMessage(rawParams);
  const [draft, setDraft] = useState({
    query: filters.query ?? "",
    start_date: filters.start_date ?? "",
    end_date: filters.end_date ?? "",
    area_code: filters.area_code ?? "",
  });
  const [formError, setFormError] = useState<string>();
  const [retryKey, setRetryKey] = useState(0);
  const [result, setResult] = useState<LoadState>({ status: "loading", items: [] });

  useEffect(() => {
    let active = true;
    listEvents(filters).then((response) => {
      if (active) setResult({
        status: "ready",
        items: response.items,
        page: response.page,
        pageSize: response.page_size,
        totalCount: response.total_count ?? response.items.length,
      });
    }).catch((error: unknown) => {
      if (!active) return;
      const apiError = error instanceof ApiError ? error : undefined;
      setResult({
        status: "error",
        items: [],
        message: apiError?.message ?? "행사 목록을 불러오지 못했습니다.",
        retryable: apiError?.problem?.retryable ?? true,
      });
    });
    return () => { active = false; };
  }, [filters, retryKey]);

  function applyFilters(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (draft.start_date && draft.end_date && draft.end_date < draft.start_date) {
      setFormError("종료일은 시작일보다 빠를 수 없습니다.");
      return;
    }
    setFormError(undefined);
    const next = filtersToSearchParams({
      query: draft.query || undefined,
      start_date: draft.start_date || undefined,
      end_date: draft.end_date || undefined,
      area_code: draft.area_code || undefined,
      sort: "start_date",
      page: 1,
      page_size: 20,
    });
    router.push(next.size ? `/visitor?${next.toString()}` : "/visitor");
  }

  function resetFilters() {
    setDraft({ query: "", start_date: "", end_date: "", area_code: "" });
    setFormError(undefined);
    router.push("/visitor");
  }

  function selectEvent(eventId: string) {
    const next = filtersToSearchParams({ ...filters, selectedEventId: eventId });
    router.replace(`/visitor?${next.toString()}`, { scroll: false });
  }

  function changePage(page: number) {
    const next = filtersToSearchParams({ ...filters, page, selectedEventId: undefined });
    router.push(next.size ? `/visitor?${next.toString()}` : "/visitor");
  }

  const currentPage = result.status === "ready" ? result.page : (filters.page ?? 1);
  const totalPages = result.status === "ready" ? Math.max(1, Math.ceil(result.totalCount / result.pageSize)) : 1;
  const hasPreviousPage = result.status === "ready" && result.page > 1;
  const hasNextPage = result.status === "ready" && result.page < totalPages;

  return (
    <main className="page-shell visitor-shell">
      <AppHeader detail="TourAPI 축제 탐색" />
      <section className="workspace-heading visitor-heading">
        <div><p className="eyebrow">VISITOR MODE</p><h1>갈 만한 축제를 한눈에 찾아보세요</h1><p>검색 결과와 지도는 같은 TourAPI 행사 목록을 사용합니다.</p></div>
      </section>

      <form className="panel visitor-filter-panel" onSubmit={applyFilters} aria-label="축제 검색 필터">
        <label><span>축제명</span><input value={draft.query} onChange={(event) => setDraft({ ...draft, query: event.target.value })} placeholder="축제 이름 검색" /></label>
        <label><span>시작일</span><input type="date" value={draft.start_date} onChange={(event) => setDraft({ ...draft, start_date: event.target.value })} /></label>
        <label><span>종료일</span><input type="date" value={draft.end_date} min={draft.start_date || undefined} onChange={(event) => setDraft({ ...draft, end_date: event.target.value })} /></label>
        <label><span>지역 코드</span><input value={draft.area_code} onChange={(event) => setDraft({ ...draft, area_code: event.target.value })} placeholder="예: 1 (서울)" /></label>
        <div className="visitor-filter-actions"><button className="button primary" type="submit">검색</button><button className="button secondary" type="button" onClick={resetFilters}>초기화</button></div>
      </form>
      {(formError || urlWarning) && <p className="form-error visitor-message" role="alert">{formError || urlWarning}</p>}

      <div className="visitor-result-heading">
        <div><p className="eyebrow">TOURAPI FESTIVALS</p><h2>축제 목록과 지도</h2><span>{filterSummary(filters)}</span></div>
        {result.status === "ready" && <strong>총 {result.totalCount}건</strong>}
      </div>

      {result.status === "loading" && <section className="panel loading-panel" aria-live="polite"><strong>TourAPI 축제 결과를 불러오는 중입니다</strong><p>목록과 지도에 같은 결과를 준비하고 있어요.</p></section>}

      {result.status === "error" && (
        <section className="panel visitor-state-panel" role="alert">
          <div className="empty-icon">!</div><h2>실제 축제 정보를 불러오지 못했습니다</h2><p>{result.message}</p><p>mock 목록으로 바꾸지 않았습니다. 잠시 뒤 실제 TourAPI 상태를 다시 확인해 주세요.</p>
          <button className="button primary" type="button" onClick={() => { setResult({ status: "loading", items: [] }); setRetryKey((value) => value + 1); }}>다시 시도</button>
          {!result.retryable && <small>API 키와 서버 설정을 먼저 확인해야 할 수 있습니다.</small>}
        </section>
      )}

      {result.status === "ready" && result.items.length === 0 && (
        <section className="panel visitor-state-panel">
          <div className="empty-icon">⌕</div><h2>조건에 맞는 축제가 없습니다</h2><p>적용 필터: {filterSummary(filters)}</p><p>날짜나 지역을 넓히거나 모든 필터를 초기화해 보세요.</p><button className="button secondary" type="button" onClick={resetFilters}>필터 초기화</button>
        </section>
      )}

      {result.status === "ready" && result.items.length > 0 && (
        <div className="visitor-explore-layout">
          <section className="visitor-event-list" aria-label="검색된 축제 목록">
            {result.items.map((event) => (
              <article key={event.event_id} className={`visitor-event-card ${selectedEventId === event.event_id ? "selected" : ""}`}>
                <button type="button" className="visitor-card-select" onClick={() => selectEvent(event.event_id)} aria-pressed={selectedEventId === event.event_id}>
                  {event.thumbnail ? <Image className="visitor-card-image" src={event.thumbnail.url} alt={event.thumbnail.alt} width={180} height={120} unoptimized /> : <span className="visitor-card-image placeholder" aria-label="대표 이미지 없음">축제</span>}
                  <span className="visitor-card-body">
                    <span className="card-topline"><b>{event.event_type === "festival" ? "축제" : event.event_type}</b><small>{event.event_status === "ongoing" ? "진행 중" : event.event_status === "scheduled" ? "예정" : "일정 확인"}</small></span>
                    <strong>{event.title}</strong><span>{formatDateRange(event)}</span><span>{event.venue?.address ?? event.region.display_name}</span>
                    {!event.venue?.coordinates && <em>좌표 없음 · 목록에서만 확인 가능</em>}
                    {event.prediction_summary?.status === "available" && <em>상대 수요 지수 {event.prediction_summary.demand_score ?? "–"} · {event.prediction_summary.is_mock ? "mock" : "예측"}</em>}
                  </span>
                </button>
                <div className="visitor-card-footer"><small>출처: {event.sources.map((source) => source.provider_name).join(", ")}</small><Link className="text-button" href={`/visitor/${event.event_id}`}>상세 보기 →</Link></div>
              </article>
            ))}
          </section>
          <aside className="panel visitor-map-panel"><VisitorEventMap events={result.items} selectedEventId={selectedEventId} onSelect={selectEvent} /></aside>
        </div>
      )}

      {result.status === "ready" && (hasPreviousPage || hasNextPage) && (
        <nav className="visitor-pagination" aria-label="축제 목록 페이지">
          <button className="button secondary" type="button" disabled={!hasPreviousPage} onClick={() => changePage(currentPage - 1)}>이전 페이지</button>
          <span><strong>{currentPage}</strong> / {totalPages} 페이지</span>
          <button className="button secondary" type="button" disabled={!hasNextPage} onClick={() => changePage(currentPage + 1)}>다음 페이지</button>
        </nav>
      )}
    </main>
  );
}

export function VisitorExplore() {
  const searchParams = useSearchParams();
  const params = new URLSearchParams(searchParams.toString());
  const selectedEventId = params.get("selected_event_id") || undefined;
  params.delete("selected_event_id");
  const searchParamsValue = params.toString();
  return <VisitorExploreView key={searchParamsValue} searchParamsValue={searchParamsValue} selectedEventId={selectedEventId} />;
}
