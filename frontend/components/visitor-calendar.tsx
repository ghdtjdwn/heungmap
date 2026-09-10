"use client";
import Link from "next/link";
import type { EventSummary } from "@/lib/types";

type VisitorCalendarProps = {
  events: EventSummary[];
  month: string;
  selectedDate?: string;
  onMonth: (month: string) => void;
  onDate: (date: string) => void;
};

export function VisitorCalendar({ events, month, selectedDate, onMonth, onDate }: VisitorCalendarProps) {
  const [year, monthNumber] = month.split("-").map(Number);
  const start = new Date(year, monthNumber - 1, 1);
  const days = new Date(year, monthNumber, 0).getDate();
  function move(offset: number) {
    const next = new Date(year, monthNumber - 1 + offset, 1);
    onMonth(next.getFullYear() + "-" + String(next.getMonth() + 1).padStart(2, "0"));
  }
  return <section className="panel calendar-panel" aria-label="행사 캘린더">
    <div className="calendar-toolbar"><button className="button secondary" onClick={() => move(-1)}>이전 달</button><h2>{year}년 {monthNumber}월</h2><button className="button secondary" onClick={() => move(1)}>다음 달</button></div>
    <div className="calendar-grid">{["일", "월", "화", "수", "목", "금", "토"].map(day => <strong key={day}>{day}</strong>)}
      {Array.from({ length: start.getDay() }, (_, i) => <div key={"blank" + i} />)}
      {Array.from({ length: days }, (_, i) => {
        const day = i + 1;
        const date = month + "-" + String(day).padStart(2, "0");
        const selected = selectedDate === date;
        return <div className={`calendar-day ${selected ? "selected" : ""}`} data-date={date} key={date}>
          <button type="button" className="calendar-date-button" aria-label={`${year}년 ${monthNumber}월 ${day}일 선택`} aria-pressed={selected} onClick={() => onDate(date)}>
            <time dateTime={date}>{day}</time>
          </button>
          {events.filter(e => e.start_date <= date && e.end_date >= date).map(event => <Link key={event.event_id} href={"/visitor/" + event.event_id}>{event.title}</Link>)}
        </div>;
      })}
    </div>
    <p>여러 날 열리는 행사는 해당 기간의 각 날짜에 표시합니다. 페이지가 여러 개면 아래에서 나머지 행사를 확인할 수 있습니다.</p>
  </section>;
}
