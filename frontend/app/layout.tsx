import type { Metadata } from "next";
import "./globals.css";
import { SessionProvider } from "@/components/session-provider";

const siteUrl = "https://heungmap.vercel.app";
const title = "흥할지도 · 만드는 즐거움, 찾아가는 설렘";
const description = "한국관광공사 TourAPI와 지역 방문자 데이터로 축제 기간 방문수요를 예측해 기획자와 방문객에게 보여 주는 서비스";

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title,
  description,
  openGraph: {
    title,
    description,
    url: "/",
    siteName: "흥할지도",
    locale: "ko_KR",
    type: "website",
    images: [{ url: "/assets/heungmap-logo.png", width: 900, height: 269, alt: "흥할지도" }],
  },
  twitter: {
    card: "summary_large_image",
    title,
    description,
    images: ["/assets/heungmap-logo.png"],
  },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ko" data-scroll-behavior="smooth">
      <body><SessionProvider>{children}</SessionProvider></body>
    </html>
  );
}
