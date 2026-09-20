"use client";

import { useCallback, useEffect, useMemo, useRef, useState, useSyncExternalStore } from "react";

import type { EventSummary } from "@/lib/types";
import { formatDateRange, safeImageUrl, statusLabel } from "@/lib/event-format";

type MapEvent = {
  eventId: string;
  title: string;
  latitude: number;
  longitude: number;
  status: string;
  period: string;
  place: string;
  thumbnailUrl?: string;
  thumbnailAlt?: string;
};
type KakaoMarker = {
  setMap(map: unknown | null): void;
  setOpacity(opacity: number): void;
  setZIndex(zIndex: number): void;
};
type KakaoMaps = {
  load(callback: () => void): void;
  LatLng: new (latitude: number, longitude: number) => unknown;
  LatLngBounds: new () => { extend(point: unknown): void };
  Map: new (container: HTMLElement, options: { center: unknown; level: number }) => KakaoMap;
  Marker: new (options: { map: unknown; position: unknown; title: string }) => KakaoMarker;
  CustomOverlay: new (options: { position: unknown; content: HTMLElement; yAnchor?: number; zIndex?: number }) => KakaoOverlay;
  event: { addListener(target: unknown, eventName: string, handler: () => void): void };
};
type KakaoMap = {
  relayout(): void;
  setBounds(bounds: unknown): void;
  setCenter(point: unknown): void;
  panBy(dx: number, dy: number): void;
};
type KakaoOverlay = {
  setMap(map: unknown | null): void;
  setPosition(position: unknown): void;
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

/** 마커를 누르면 뜨는 말풍선. 외부 문자열은 textContent로만 넣는다(마크업 주입 방지). */
function buildPopup(point: MapEvent, onClose: () => void): HTMLElement {
  const root = document.createElement("div");
  root.className = "map-popup";

  const close = document.createElement("button");
  close.type = "button";
  close.className = "map-popup-close";
  close.setAttribute("aria-label", "닫기");
  close.textContent = "×";
  close.addEventListener("click", onClose);
  root.appendChild(close);

  if (point.thumbnailUrl) {
    const image = document.createElement("img");
    image.className = "map-popup-image";
    image.src = point.thumbnailUrl;
    image.alt = point.thumbnailAlt ?? point.title;
    image.loading = "lazy";
    // 사진을 못 받아도 말풍선은 그대로 뜨게 한다.
    image.addEventListener("error", () => image.remove(), { once: true });
    root.appendChild(image);
  }

  const body = document.createElement("div");
  body.className = "map-popup-body";

  const status = document.createElement("span");
  status.className = "map-popup-status";
  status.textContent = point.status;
  body.appendChild(status);

  const title = document.createElement("strong");
  title.textContent = point.title;
  body.appendChild(title);

  for (const text of [point.period, point.place]) {
    const line = document.createElement("small");
    line.textContent = text;
    body.appendChild(line);
  }

  const link = document.createElement("a");
  link.className = "map-popup-link";
  link.href = `/visitor/${encodeURIComponent(point.eventId)}`;
  link.textContent = "상세 보기 →";
  body.appendChild(link);

  root.appendChild(body);
  return root;
}

export function VisitorEventMap({
  events,
  selectedEventId,
  onSelect,
  focus = false,
}: {
  events: EventSummary[];
  selectedEventId?: string;
  onSelect: (eventId: string) => void;
  focus?: boolean;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<KakaoMap | null>(null);
  const popupRef = useRef<HTMLElement | null>(null);
  const markersRef = useRef<Array<{ eventId: string; marker: KakaoMarker; point: MapEvent }>>([]);
  const overlayRef = useRef<KakaoOverlay | null>(null);
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
      status: statusLabel(event.event_status),
      period: formatDateRange(event),
      place: event.venue?.address ?? event.venue?.name ?? event.region.display_name,
      thumbnailUrl: safeImageUrl(event.thumbnail?.url),
      thumbnailAlt: event.thumbnail?.alt ?? event.title,
    }] : [];
  }), [events]);
  const missingCoordinateCount = events.length - points.length;

  useEffect(() => {
    onSelectRef.current = onSelect;
  }, [onSelect]);

  // 마커를 화면 중앙에 두더라도 말풍선은 위로 뻗어 지도 밖으로 잘릴 수 있다.
  // 넘친 만큼 지도를 밀어 말풍선 전체가 보이게 한다.
  const keepPopupInView = useCallback(() => {
    const container = containerRef.current;
    const popup = popupRef.current;
    const map = mapRef.current;
    if (!container || !popup || !map || !popup.isConnected) return;
    const edge = 12;
    const box = container.getBoundingClientRect();
    const bubble = popup.getBoundingClientRect();
    let dx = 0;
    let dy = 0;
    if (bubble.top < box.top + edge) dy = bubble.top - (box.top + edge);
    else if (bubble.bottom > box.bottom - edge) dy = bubble.bottom - (box.bottom - edge);
    if (bubble.left < box.left + edge) dx = bubble.left - (box.left + edge);
    else if (bubble.right > box.right - edge) dx = bubble.right - (box.right - edge);
    if (dx || dy) map.panBy(dx, dy);
  }, []);

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
      const closePopup = () => {
        overlayRef.current?.setMap(null);
        overlayRef.current = null;
        popupRef.current = null;
      };
      const openPopup = (point: MapEvent) => {
        closePopup();
        const content = buildPopup(point, closePopup);
        const overlay = new maps.CustomOverlay({
          position: new maps.LatLng(point.latitude, point.longitude),
          content,
          yAnchor: 1.3,
          zIndex: 30,
        });
        overlay.setMap(map);
        overlayRef.current = overlay;
        popupRef.current = content;
        // 사진이 늦게 로드돼 높이가 커지는 경우까지 반영하려면 배치가 끝난 뒤에 재어야 한다.
        window.requestAnimationFrame(keepPopupInView);
        content.querySelector("img")?.addEventListener("load", keepPopupInView, { once: true });
      };
      // 빈 곳을 누르면 닫는다.
      maps.event.addListener(map, "click", closePopup);
      markersRef.current = points.map((point) => {
        const marker = new maps.Marker({
          map,
          position: new maps.LatLng(point.latitude, point.longitude),
          title: point.title,
        });
        maps.event.addListener(marker, "click", () => {
          openPopup(point);
          onSelectRef.current(point.eventId);
        });
        return { eventId: point.eventId, marker, point };
      });
      setState("ready");
      window.requestAnimationFrame(() => {
        if (disposed) return;
        map.relayout();
        if (points.length === 1) {
          map.setCenter(center);
        } else {
          const bounds = new maps.LatLngBounds();
          points.forEach((point) => bounds.extend(new maps.LatLng(point.latitude, point.longitude)));
          map.setBounds(bounds);
        }
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
      overlayRef.current?.setMap(null);
      overlayRef.current = null;
      markersRef.current.forEach(({ marker }) => marker.setMap(null));
      markersRef.current = [];
      mapRef.current = null;
    };
  }, [key, points, keepPopupInView]);

  useEffect(() => {
    for (const entry of markersRef.current) {
      const selected = entry.eventId === selectedEventId;
      entry.marker.setOpacity(selectedEventId && !selected ? 0.55 : 1);
      entry.marker.setZIndex(selected ? 10 : 1);
      const kakao = getKakao();
      if (selected && kakao && mapRef.current) {
        mapRef.current.setCenter(new kakao.maps.LatLng(entry.point.latitude, entry.point.longitude));
        window.requestAnimationFrame(keepPopupInView);
      }
    }
  }, [selectedEventId, state, keepPopupInView]);

  if (points.length === 0) {
    return <div className="map-fallback"><strong>지도에 표시할 좌표가 없습니다</strong><p>행사 목록은 계속 확인할 수 있습니다.</p></div>;
  }

  const visibleState = key ? state : "missing_key";
  return (
    <div className={`visitor-map ${focus ? "visitor-map-focus" : ""}`}>
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
