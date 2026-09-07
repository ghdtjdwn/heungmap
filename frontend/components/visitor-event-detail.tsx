"use client";

import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { AppHeader } from "@/components/app-header";
import { ApiError, getEvent, getEventNearby, getEventPrediction } from "@/lib/api";
import type { EventDetail, NearbyPlaceListResponse, Prediction } from "@/lib/types";

const PLACE_LABELS: Record<string, { icon: string; label: string }> = {
  parking: { icon: "P", label: "주차" },
  lodging: { icon: "숙", label: "숙박" },
  restaurant: { icon: "식", label: "음식점" },
  cafe: { icon: "카", label: "카페" },
  tourist_attraction: { icon: "관", label: "관광지" },
  cultural_facility: { icon: "문", label: "문화시설" },
  shopping: { icon: "쇼", label: "쇼핑" },
  restroom: { icon: "화", label: "화장실" },
  transit: { icon: "교", label: "교통" },
  other: { icon: "·", label: "주변 장소" },
};

const CONFIDENCE_LABELS = { low: "낮음", medium: "보통", high: "높음" } as const;

type Resource<T> =
  | { status: "loading" }
  | { status: "ready"; data: T }
  | { status: "error"; message: string };

function formatDate(value: string): string {
  return new Intl.DateTimeFormat("ko-KR", { year: "numeric", month: "long", day: "numeric", weekday: "short" }).format(new Date(`${value}T00:00:00`));
}

function errorMessage(result: PromiseRejectedResult, fallback: string): string {
  return result.reason instanceof ApiError ? result.reason.message : fallback;
}

export function VisitorEventDetail({ eventId }: { eventId: string }) {
  const router = useRouter();
  const [event, setEvent] = useState<Resource<EventDetail>>({ status: "loading" });
  const [nearby, setNearby] = useState<Resource<NearbyPlaceListResponse>>({ status: "loading" });
  const [prediction, setPrediction] = useState<Resource<Prediction>>({ status: "loading" });
  const [retryKey, setRetryKey] = useState(0);

  useEffect(() => {
    let active = true;
    Promise.allSettled([
      getEvent(eventId),
      getEventNearby(eventId),
      getEventPrediction(eventId),
    ]).then(([eventResult, nearbyResult, predictionResult]) => {
      if (!active) return;
      setEvent(eventResult.status === "fulfilled"
        ? { status: "ready", data: eventResult.value }
        : { status: "error", message: errorMessage(eventResult, "행사 정보를 불러오지 못했습니다.") });
      setNearby(nearbyResult.status === "fulfilled"
        ? { status: "ready", data: nearbyResult.value }
        : { status: "error", message: errorMessage(nearbyResult, "주변 정보를 불러오지 못했습니다.") });
      setPrediction(predictionResult.status === "fulfilled"
        ? { status: "ready", data: predictionResult.value }
        : { status: "error", message: errorMessage(predictionResult, "수요 지표를 불러오지 못했습니다.") });
    });
    return () => { active = false; };
  }, [eventId, retryKey]);

  function retry() {
    setEvent({ status: "loading" });
    setNearby({ status: "loading" });
    setPrediction({ status: "loading" });
    setRetryKey((value) => value + 1);
  }

  if (event.status === "loading") {
    return <main className="page-shell visitor-detail-shell"><AppHeader detail="행사 불러오는 중" /><section className="panel loading-panel" aria-live="polite"><strong>행사 상세 정보를 불러오는 중입니다</strong><p>TourAPI 일정·장소와 흥할지도 수요 지표를 각각 확인하고 있어요.</p></section></main>;
  }

  if (event.status === "error") {
    return (
      <main className="page-shell visitor-detail-shell">
        <AppHeader detail="행사 없음" />
        <section className="panel visitor-detail-missing">
          <div className="empty-icon">!</div><h1>존재하지 않거나 종료된 행사입니다</h1><p>{event.message}</p>
          <div className="button-row"><Link href="/visitor" className="button primary">축제 목록으로</Link><button type="button" className="button secondary" onClick={retry}>다시 확인</button></div>
        </section>
      </main>
    );
  }

  const detail = event.data;
  const sortedNearby = nearby.status === "ready"
    ? [...nearby.data.items].sort((a, b) => (a.distance_m ?? Number.MAX_SAFE_INTEGER) - (b.distance_m ?? Number.MAX_SAFE_INTEGER))
    : [];
  const predictionData = prediction.status === "ready" ? prediction.data : undefined;

  return (
    <main className="page-shell visitor-detail-shell">
      <AppHeader detail={detail.title} />
      <div className="visitor-detail-toolbar">
        <button type="button" className="back-link" onClick={() => router.back()}>← 뒤로가기</button>
        <Link href="/visitor" className="text-button">축제 목록</Link>
      </div>

      <section className="visitor-detail-hero">
        {detail.thumbnail
          ? <Image className="visitor-detail-image" src={detail.thumbnail.url} alt={detail.thumbnail.alt} width={720} height={420} priority unoptimized />
          : <div className="visitor-detail-image placeholder" aria-label="대표 이미지 없음">흥할지도 축제</div>}
        <div className="visitor-detail-summary">
          <div className="hero-badges"><span className="status-pill analyzed">{detail.event_type === "festival" ? "축제" : detail.event_type}</span><span className="status-pill">{detail.event_status === "ongoing" ? "진행 중" : detail.event_status === "scheduled" ? "예정" : "일정 확인"}</span></div>
          <h1>{detail.title}</h1>
          <dl>
            <div><dt>기간</dt><dd>{formatDate(detail.start_date)}{detail.end_date !== detail.start_date ? ` – ${formatDate(detail.end_date)}` : ""}</dd></div>
            <div><dt>장소</dt><dd>{detail.venue?.name ?? "장소명 미제공"}</dd></div>
            <div><dt>주소</dt><dd>{detail.venue?.address ?? detail.region.display_name}</dd></div>
            {detail.price_summary && <div><dt>이용 안내</dt><dd>{detail.price_summary}</dd></div>}
          </dl>
          {detail.homepage_url && <a className="button secondary" href={detail.homepage_url} target="_blank" rel="noreferrer">공식 홈페이지 열기 ↗</a>}
        </div>
      </section>

      {(detail.description || detail.program_summary) && <section className="panel visitor-detail-description"><p className="eyebrow">EVENT INFO</p><h2>행사 소개</h2>{detail.description && <p>{detail.description}</p>}{detail.program_summary && <p><strong>프로그램</strong><br />{detail.program_summary}</p>}</section>}

      <div className="visitor-detail-grid">
        <section className="result-panel visitor-demand-card" aria-labelledby="visitor-demand-heading">
          <div className="panel-title"><div><span className="eyebrow">DEMAND INDEX</span><h2 id="visitor-demand-heading">수요 지표</h2></div>{predictionData?.status === "available" && <span className="confidence">신뢰도 {CONFIDENCE_LABELS[predictionData.confidence]}</span>}</div>
          {prediction.status === "loading" && <div className="unavailable-box" role="status">수요 지표를 불러오는 중…</div>}
          {prediction.status === "error" && <div className="unavailable-box"><strong>수요 지표 조회 실패</strong><p>{prediction.message}</p><button type="button" className="text-button" onClick={retry}>다시 시도</button></div>}
          {predictionData?.status === "unavailable" && <div className="unavailable-box"><strong>현재 예측을 제공할 수 없습니다</strong><p>{predictionData.message}</p>{predictionData.limitations.map((item) => <small key={item}>{item}</small>)}</div>}
          {predictionData?.status === "available" && <>
            <div className="visitor-score"><strong>{predictionData.primary_metric.value}</strong><span>/ 100</span></div>
            <div className="mock-alert visitor-mock-alert"><strong>{predictionData.is_mock ? "MODEL MOCK" : "예측 지표"}</strong><span>실제 관람객 수가 아니라 상대적 수요 지수{predictionData.is_mock ? "(mock)" : ""}입니다.</span></div>
            <dl className="visitor-prediction-meta"><div><dt>기준 시각</dt><dd>{new Date(predictionData.as_of).toLocaleString("ko-KR")}</dd></div><div><dt>계산 방식</dt><dd>{predictionData.method === "rules" ? "규칙 기반" : predictionData.method}</dd></div><div><dt>데이터 충분성</dt><dd>{predictionData.data_sufficiency === "limited" ? "제한적" : "충분"}</dd></div></dl>
            {predictionData.factors.length > 0 && <ul className="factor-list">{predictionData.factors.map((factor) => <li key={factor.factor_id}><span className={`direction ${factor.direction}`}>{factor.direction === "up" ? "↑" : factor.direction === "down" ? "↓" : "–"}</span><div><strong>{factor.label}</strong><p>{factor.explanation}</p></div></li>)}</ul>}
            <div className="visitor-limitations"><strong>해석 한계</strong><ul>{predictionData.limitations.map((item) => <li key={item}>{item}</li>)}</ul></div>
          </>}
        </section>

        <section className="result-panel" aria-labelledby="visitor-nearby-heading">
          <div className="panel-title"><div><span className="eyebrow">TOURAPI NEARBY</span><h2 id="visitor-nearby-heading">주변 정보</h2></div>{nearby.status === "ready" && <span className="source-state available">반경 {nearby.data.radius_m.toLocaleString("ko-KR")}m</span>}</div>
          {nearby.status === "loading" && <div className="unavailable-box" role="status">주변 관광정보를 불러오는 중…</div>}
          {nearby.status === "error" && <div className="unavailable-box"><strong>주변 정보 조회 실패</strong><p>{nearby.message}</p><p>행사 기본 정보와 수요 지표는 계속 확인할 수 있습니다.</p><button type="button" className="text-button" onClick={retry}>다시 시도</button></div>}
          {nearby.status === "ready" && (sortedNearby.length > 0 ? <ul className="visitor-nearby-list">{sortedNearby.map((place) => {
            const display = PLACE_LABELS[place.place_type] ?? PLACE_LABELS.other;
            return <li key={place.place_id}><span className="visitor-place-icon">{display.icon}</span><div><strong>{place.name}</strong><span>{display.label}{place.distance_m !== undefined ? ` · ${place.distance_m.toLocaleString("ko-KR")}m` : " · 거리 미제공"}</span>{place.address && <small>{place.address}</small>}</div></li>;
          })}</ul> : <div className="unavailable-box"><strong>표시할 주변 장소가 없습니다</strong><p>검색 반경 안에서 TourAPI 장소를 찾지 못했습니다.</p></div>)}
        </section>
      </div>

      <section className="panel visitor-source-panel">
        <p className="eyebrow">PROVENANCE</p><h2>행사 정보 출처</h2>
        <div className="source-list">{detail.sources.map((source) => <article key={source.source_id}><span className={`source-icon ${source.source_type}`}>{source.source_type === "tourapi" ? "관" : "흥"}</span><div><strong>{source.provider_name}</strong><p>{source.dataset_name}</p><small>조회 {new Date(source.retrieved_at).toLocaleString("ko-KR")}{source.source_record_id ? ` · 원본 ID ${source.source_record_id}` : ""}</small>{source.limitation && <em>{source.limitation}</em>}</div></article>)}</div>
        {detail.data_quality.warnings.length > 0 && <div className="warning-list"><strong>제공 정보 확인 필요</strong>{detail.data_quality.warnings.map((warning) => <p key={warning}>{warning}</p>)}</div>}
      </section>
    </main>
  );
}
