import type { EventListQuery } from "./types";

export type VisitorView = "list" | "map";
export type VisitorFilters = EventListQuery & { view?: VisitorView; selectedEventId?: string };

const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;

function validDate(value: string | null): string | undefined {
  if (!value || !ISO_DATE.test(value)) return undefined;
  const parsed = new Date(`${value}T00:00:00Z`);
  return Number.isNaN(parsed.getTime()) ? undefined : value;
}

function validInteger(value: string | null, fallback: number, maximum?: number): number {
  if (!value || !/^\d+$/.test(value)) return fallback;
  const parsed = Number(value);
  if (!Number.isSafeInteger(parsed) || parsed < 1 || (maximum !== undefined && parsed > maximum)) return fallback;
  return parsed;
}

export function parseFiltersFromSearchParams(params: URLSearchParams): EventListQuery {
  const query = params.get("query")?.trim() || undefined;
  let startDate = validDate(params.get("start_date"));
  let endDate = validDate(params.get("end_date"));
  if (startDate && endDate && endDate < startDate) {
    startDate = undefined;
    endDate = undefined;
  }
  const areaCode = params.get("region_code")?.trim() || undefined;
  const page = validInteger(params.get("page"), 1);
  const pageSize = validInteger(params.get("page_size"), 20, 100);
  return {
    ...(query ? { query } : {}),
    ...(startDate ? { start_date: startDate } : {}),
    ...(endDate ? { end_date: endDate } : {}),
    ...(areaCode ? { area_code: areaCode } : {}),
    sort: "start_date",
    page,
    page_size: pageSize,
  };
}

export function parseVisitorView(params: URLSearchParams): VisitorView {
  return params.get("view") === "map" ? "map" : "list";
}

export function filtersToSearchParams(filters: VisitorFilters): URLSearchParams {
  const params = new URLSearchParams();
  if (filters.view) params.set("view", filters.view);
  if (filters.query?.trim()) params.set("query", filters.query.trim());
  if (filters.start_date) params.set("start_date", filters.start_date);
  if (filters.end_date) params.set("end_date", filters.end_date);
  if (filters.area_code?.trim()) params.set("region_code", filters.area_code.trim());
  if ((filters.page ?? 1) > 1) params.set("page", String(filters.page));
  if ((filters.page_size ?? 20) !== 20) params.set("page_size", String(filters.page_size));
  if (filters.selectedEventId) params.set("selected_event_id", filters.selectedEventId);
  return params;
}

export function invalidFilterMessage(params: URLSearchParams): string | undefined {
  const rawView = params.get("view");
  if (rawView && rawView !== "list" && rawView !== "map") {
    return "URL의 보기 방식이 올바르지 않아 목록 보기로 표시합니다.";
  }
  const rawStart = params.get("start_date");
  const rawEnd = params.get("end_date");
  const start = validDate(rawStart);
  const end = validDate(rawEnd);
  if ((rawStart && !start) || (rawEnd && !end)) {
    return "URL의 날짜 형식이 올바르지 않아 해당 값을 제외했습니다.";
  }
  if (start && end && end < start) {
    return "종료일이 시작일보다 빨라 날짜 필터를 적용하지 않았습니다.";
  }
  const rawPage = params.get("page");
  const rawPageSize = params.get("page_size");
  if ((rawPage && validInteger(rawPage, 0) === 0) || (rawPageSize && validInteger(rawPageSize, 0, 100) === 0)) {
    return "URL의 페이지 값이 올바르지 않아 첫 페이지 기준으로 표시합니다.";
  }
  return undefined;
}
