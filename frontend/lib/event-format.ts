import type { EventSummary } from "@/lib/types";

/** 목록·지도가 같은 문구를 쓰도록 행사 표시 형식을 한 곳에 모았다. */

export function formatDateRange(event: Pick<EventSummary, "start_date" | "end_date">): string {
  // 올해가 아니거나 해를 넘기는 기간은 연도를 붙여 "11월 1일"이 몇 년도인지 헷갈리지 않게 한다.
  const thisYear = String(new Date().getFullYear());
  const withYear = event.start_date.slice(0, 4) !== thisYear || event.end_date.slice(0, 4) !== thisYear;
  const options: Intl.DateTimeFormatOptions = { ...(withYear ? { year: "numeric" } : {}), month: "short", day: "numeric", weekday: "short" };
  const start = new Intl.DateTimeFormat("ko-KR", options).format(new Date(`${event.start_date}T00:00:00`));
  const end = new Intl.DateTimeFormat("ko-KR", options).format(new Date(`${event.end_date}T00:00:00`));
  return event.start_date === event.end_date ? start : `${start} – ${end}`;
}

export function statusLabel(status: EventSummary["event_status"]): string {
  return status === "ongoing" ? "진행 중" : status === "scheduled" ? "예정" : "일정 확인";
}

/** 외부(TourAPI) 이미지 주소는 http(s)만 허용한다. javascript: 같은 주소가 섞여 들어오지 않게 한다. */
export function safeImageUrl(url: string | undefined): string | undefined {
  if (!url) return undefined;
  try {
    const parsed = new URL(url, window.location.origin);
    return parsed.protocol === "http:" || parsed.protocol === "https:" ? parsed.href : undefined;
  } catch {
    return undefined;
  }
}
