"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import type { NearbyResult, Venue } from "@/lib/types";

type MapPoint = { id: string; name: string; category: string; distance?: number; latitude: number; longitude: number };
type KakaoMaps = {
  load(callback: () => void): void;
  LatLng: new (latitude: number, longitude: number) => unknown;
  Map: new (container: HTMLElement, options: { center: unknown; level: number }) => { setCenter(point: unknown): void };
  Marker: new (options: { map: unknown; position: unknown; title: string }) => { setMap(map: unknown | null): void };
};

declare global { interface Window { kakao?: { maps: KakaoMaps } } }

export function KakaoMapPreview({ venue, nearby }: { venue?: Venue; nearby: NearbyResult }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<{ setCenter(point: unknown): void } | null>(null);
  const markersRef = useRef<Array<{ setMap(map: unknown | null): void }>>([]);
  const [state, setState] = useState<"loading" | "ready" | "missing_key" | "failed">("loading");
  const [selectedId, setSelectedId] = useState("venue");
  const key = process.env.NEXT_PUBLIC_KAKAO_JAVASCRIPT_KEY?.trim();
  const points = useMemo(() => {
    const result: MapPoint[] = [];
    if (venue?.coordinates) result.push({ id: "venue", name: venue.name, category: "선택 행사장", latitude: venue.coordinates.latitude, longitude: venue.coordinates.longitude });
    if (nearby.status === "available") nearby.items.forEach((item) => {
      if (item.coordinates) result.push({ id: item.place_id, name: item.name, category: item.place_type, distance: item.distance_m, latitude: item.coordinates.latitude, longitude: item.coordinates.longitude });
    });
    return result;
  }, [nearby, venue]);

  useEffect(() => {
    if (!key || !containerRef.current || points.length === 0) return;
    let disposed = false;
    const render = () => window.kakao?.maps.load(() => {
      if (disposed || !containerRef.current || !window.kakao) return;
      const maps = window.kakao.maps;
      const center = new maps.LatLng(points[0].latitude, points[0].longitude);
      const map = new maps.Map(containerRef.current, { center, level: 5 });
      mapRef.current = map;
      markersRef.current = points.map((point) => new maps.Marker({ map, position: new maps.LatLng(point.latitude, point.longitude), title: point.name }));
      setState("ready");
    });
    if (window.kakao?.maps) render();
    else {
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
      markersRef.current.forEach((marker) => marker.setMap(null));
      markersRef.current = [];
    };
  }, [key, points]);

  function select(point: MapPoint) {
    setSelectedId(point.id);
    if (window.kakao && mapRef.current) mapRef.current.setCenter(new window.kakao.maps.LatLng(point.latitude, point.longitude));
  }

  if (!venue?.coordinates) return <div className="map-fallback"><strong>지도 위치 미정</strong><p>장소 주소나 좌표를 입력하면 지도와 주변 관광정보를 함께 확인할 수 있습니다.</p></div>;
  const visibleState = key ? state : "missing_key";
  return <div className="map-preview">
    <div ref={containerRef} className={`map-canvas ${visibleState !== "ready" ? "hidden" : ""}`} aria-label="선택 행사장과 주변 관광정보 지도" />
    {visibleState === "loading" && <div className="map-fallback" role="status">지도 불러오는 중…</div>}
    {visibleState === "missing_key" && <div className="map-fallback"><strong>지도 SDK 키 미설정</strong><p>목록과 거리 정보는 계속 사용할 수 있습니다. KAKAO_JAVASCRIPT_KEY와 localhost 도메인을 설정하면 지도가 표시됩니다.</p></div>}
    {visibleState === "failed" && <div className="map-fallback" role="status"><strong>지도를 표시하지 못했습니다</strong><p>아래 TourAPI 목록은 그대로 유지됩니다.</p></div>}
    <div className="map-point-list" aria-label="지도 장소 목록">{points.map((point) => <button type="button" className={selectedId === point.id ? "selected" : ""} onClick={() => select(point)} key={point.id}><strong>{point.name}</strong><span>{point.category}{point.distance !== undefined ? ` · ${point.distance.toLocaleString("ko-KR")}m` : ""}</span></button>)}</div>
    <small className="map-source">지도: Kakao Maps · 장소·거리: 한국관광공사 TourAPI</small>
  </div>;
}
