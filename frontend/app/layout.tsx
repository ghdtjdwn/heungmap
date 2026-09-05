import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "흥할지도 · 기획자",
  description: "근거를 확인하며 행사 조건을 비교하는 기획자 도구",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ko">
      <body>{children}</body>
    </html>
  );
}
