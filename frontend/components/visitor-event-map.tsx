"use client";

import { useEffect, useMemo, useRef, useState, useSyncExternalStore } from "react";

import type { EventSummary } from "@/lib/types";

type MapEvent = {
  eventId: string;
  title: string;
  latitude: number;
  longitude: number;
};
type KakaoMarker = {
  setMap(map: unknown | null): void;
  setOpacity(opacity: number): void;
  setZIndex(zIndex: number): void;
};
type KakaoMaps = {
  load(callback: () => void): void;
  LatLng: new (latitude: number, longitude: number) => unknown;
  Map: new (container: HTMLElement, options: { center: unknown; level: number }) => { relayout(): void; setCenter(point: unknown): void };
  Marker: new (options: { map: unknown; position: unknown; title: string }) => KakaoMarker;
  event: { addListener(target: unknown, eventName: string, handler: () => void): void };
};
type KakaoWindow = { kakao?: { maps: KakaoMaps }; __HEUNGMAP_E2E_KAKAO_MAP_KEY__?: string };

function getKakao() {
  return (window as unknown as KakaoWindow).kakao;
}

function getRuntimeKakaoMapKey(): string | undefined {
  if (process.env.NODE_ENV === "production") return undefined;
  return (window as unknown as KakaoWindow).__HEUNGMAP_E2E_KAKAO_MAP_KEY__?.trim() || undefined;
}

function subscribeToRuntimeConfig(): () => void {
  return () => undefined;
}

export function VisitorEventMap({
  events,
  selectedEventId,
  onSelect,
}: {
  events: EventSummary[];
  selectedEventId?: string;
  onSelect: (eventId: string) => void;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<{ relayout(): void; setCenter(point: unknown): void } | null>(null);
  const markersRef = useRef<Array<{ eventId: string; marker: KakaoMarker; point: MapEvent }>>([]);
  const onSelectRef = useRef(onSelect);
  const [state, setState] = useState<"loading" | "ready" | "missing_key" | "failed">("loading");
  const runtimeKey = useSyncExternalStore(subscribeToRuntimeConfig, getRuntimeKakaoMapKey, () => undefined);
  const key = process.env.NEXT_PUBLIC_KAKAO_JAVASCRIPT_KEY?.trim() || runtimeKey;
  const points = useMemo<MapEvent[]>(() => events.flatMap((event) => {
    const coordinates = event.venue?.coordinates;
    return coordinates ? [{
      eventId: event.event_id,
      title: event.title,
      latitude: coordinates.latitude,
      longitude: coordinates.longitude,
    }] : [];
  }), [events]);
  const missingCoordinateCount = events.length - points.length;

  useEffect(() => {
    onSelectRef.current = onSelect;
  }, [onSelect]);

  useEffect(() => {
    if (!key || !containerRef.current || points.length === 0) return;
    let disposed = false;
    const render = () => getKakao()?.maps.load(() => {
      const kakao = getKakao();
      if (disposed || !containerRef.current || !kakao) return;
      const maps = kakao.maps;
      const center = new maps.LatLng(points[0].latitude, points[0].longitude);
      const map = new maps.Map(containerRef.current, { center, level: 8 });
      mapRef.current = map;
      markersRef.current = points.map((point) => {
        const marker = new maps.Marker({
          map,
          position: new maps.LatLng(point.latitude, point.longitude),
          title: point.title,
        });
        maps.event.addListener(marker, "click", () => onSelectRef.current(point.eventId));
        return { eventId: point.eventId, marker, point };
      });
      setState("ready");
      window.requestAnimationFrame(() => {
        if (disposed) return;
        map.relayout();
        map.setCenter(center);
      });
    });

    if (getKakao()?.maps) {
      render();
    } else {
      const existing = document.querySelector<HTMLScriptElement>('script[data-heungmap-kakao-map]');
      const script = existing ?? document.createElement("script");
      if (!existing) {
        script.dataset.heungmapKakaoMap = "true";
        script.src = `https://dapi.kakao.com/v2/maps/sdk.js?appkey=${encodeURIComponent(key)}&autoload=false`;
        document.head.appendChild(script);
      }
      script.addEventListener("load", render, { once: true });
      script.addEventListener("error", () => !disposed && setState("failed"), { once: true });
    }
    return () => {
      disposed = true;
      markersRef.current.forEach(({ marker }) => marker.setMap(null));
      markersRef.current = [];
      mapRef.current = null;
    };
  }, [key, points]);

  useEffect(() => {
    for (const entry of markersRef.current) {
      const selected = entry.eventId === selectedEventId;
      entry.marker.setOpacity(selectedEventId && !selected ? 0.55 : 1);
      entry.marker.setZIndex(selected ? 10 : 1);
      const kakao = getKakao();
      if (selected && kakao && mapRef.current) {
        mapRef.current.setCenter(new kakao.maps.LatLng(entry.point.latitude, entry.point.longitude));
      }
    }
  }, [selectedEventId, state]);

  if (points.length === 0) {
    return <div className="map-fallback"><strong>지도에 표시할 좌표가 없습니다</strong><p>행사 목록은 계속 확인할 수 있습니다.</p></div>;
  }

  const visibleState = key ? state : "missing_key";
  return (
    <div className="visitor-map">
      <div ref={containerRef} className={`map-canvas ${visibleState === "missing_key" || visibleState === "failed" ? "hidden" : ""}`} aria-label="검색된 축제 위치 지도" />
      {visibleState === "loading" && <div className="map-fallback" role="status">축제 위치 지도를 불러오는 중…</div>}
      {visibleState === "missing_key" && <div className="map-fallback"><strong>지도 SDK 키 미설정</strong><p>목록 탐색은 계속 사용할 수 있습니다. Kakao JavaScript 키를 설정하면 위치가 표시됩니다.</p></div>}
      {visibleState === "failed" && <div className="map-fallback" role="status"><strong>지도를 표시하지 못했습니다</strong><p>TourAPI 행사 목록에서 축제를 계속 선택할 수 있습니다.</p></div>}
      <div className="map-point-list" aria-label="지도에 표시된 행사 목록">
        {points.map((point) => (
          <button key={point.eventId} type="button" className={selectedEventId === point.eventId ? "selected" : ""} onClick={() => onSelect(point.eventId)}>
            <strong>{point.title}</strong><span>축제 위치</span>
          </button>
        ))}
      </div>
      {missingCoordinateCount > 0 && <p className="map-coordinate-note">좌표 없는 행사 {missingCoordinateCount}건은 지도에 표시되지 않습니다.</p>}
      <small className="map-source">행사·좌표: 한국관광공사 TourAPI · 지도: Kakao Maps</small>
    </div>
  );
}
