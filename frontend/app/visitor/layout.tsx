import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "흥할지도 · 방문객",
  description: "한국관광공사 축제 정보를 목록과 지도에서 찾고 상세를 확인하는 방문객 도구",
};

export default function VisitorLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return children;
}
