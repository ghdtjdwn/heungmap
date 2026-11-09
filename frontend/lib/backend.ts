/**
 * 백엔드 주소를 한 곳에서 정한다.
 *
 * 환경변수가 **빈 문자열**로 들어오는 경우가 있어 `??`로는 걸러지지 않는다. 그러면 주소에서
 * 호스트가 사라져 Vercel 리라이트는 DNS_HOSTNAME_EMPTY를, 라우트 핸들러의 fetch는 예외를 낸다.
 * 그래서 `||`로 빈 값까지 걸러 낸다. 배포 환경(VERCEL)에서는 HEUNGMAP_BACKEND_URL을 프로젝트
 * 환경변수로 반드시 넣어야 하며, 없으면 바로 예외를 낸다(next.config.ts의 rewrites와 같은 규칙).
 * 로컬 개발에서는 그대로 127.0.0.1 백엔드를 본다.
 */
export function backendBaseUrl(): string {
  const configured = process.env.HEUNGMAP_BACKEND_URL || "";
  if (!configured && process.env.VERCEL) {
    throw new Error("HEUNGMAP_BACKEND_URL이 비어 있습니다. Vercel 프로젝트 환경변수에 백엔드 공개 주소를 넣어 주세요.");
  }
  return (configured || "http://127.0.0.1:8000").replace(/\/+$/, "");
}
