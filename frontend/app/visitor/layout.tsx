import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "흥할지도 · 방문객",
  description: "TourAPI 축제를 목록과 지도에서 찾고 상세 정보를 확인하는 방문객 도구",
};

export default function VisitorLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return children;
}
