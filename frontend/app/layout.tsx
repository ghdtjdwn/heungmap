import type { Metadata } from "next";
import "./globals.css";
import { SessionProvider } from "@/components/session-provider";

export const metadata: Metadata = {
  title: "흥할지도 · 만드는 즐거움, 찾아가는 설렘",
  description: "행사 기획과 축제 탐색을 잇는 흥할지도",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ko" data-scroll-behavior="smooth">
      <body><SessionProvider>{children}</SessionProvider></body>
    </html>
  );
}
