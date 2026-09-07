import type { EventListQuery } from "./types";

export type VisitorFilters = EventListQuery & { selectedEventId?: string };

const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;

function validDate(value: string | null): string | undefined {
  if (!value || !ISO_DATE.test(value)) return undefined;
  const parsed = new Date(`${value}T00:00:00Z`);
  return Number.isNaN(parsed.getTime()) ? undefined : value;
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
  return {
    ...(query ? { query } : {}),
    ...(startDate ? { start_date: startDate } : {}),
    ...(endDate ? { end_date: endDate } : {}),
    ...(areaCode ? { area_code: areaCode } : {}),
    sort: "start_date",
    page: 1,
    page_size: 20,
  };
}

export function filtersToSearchParams(filters: VisitorFilters): URLSearchParams {
  const params = new URLSearchParams();
  if (filters.query?.trim()) params.set("query", filters.query.trim());
  if (filters.start_date) params.set("start_date", filters.start_date);
  if (filters.end_date) params.set("end_date", filters.end_date);
  if (filters.area_code?.trim()) params.set("region_code", filters.area_code.trim());
  if (filters.selectedEventId) params.set("selected_event_id", filters.selectedEventId);
  return params;
}

export function invalidFilterMessage(params: URLSearchParams): string | undefined {
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
  return undefined;
}
