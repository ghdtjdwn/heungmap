import { Suspense } from "react";

import { VisitorExplore } from "@/components/visitor-explore";

export default function VisitorHome() {
  return <Suspense fallback={<main className="page-shell"><section className="panel loading-panel">축제 탐색 화면을 준비하는 중…</section></main>}><VisitorExplore /></Suspense>;
}
