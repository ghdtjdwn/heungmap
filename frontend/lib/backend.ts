/**
 * 백엔드 주소를 한 곳에서 정한다.
 *
 * 환경변수가 **빈 문자열**로 들어오는 경우가 있어 `??`로는 걸러지지 않는다. 그러면 주소에서
 * 호스트가 사라져 Vercel 리라이트는 DNS_HOSTNAME_EMPTY를, 라우트 핸들러의 fetch는 예외를 낸다.
 * 그래서 `||`로 빈 값까지 걸러 내고, 배포 환경에서는 환경변수가 없어도 동작하도록 기본값을 둔다.
 * 로컬 개발에서는 그대로 127.0.0.1 백엔드를 본다.
 */
export const DEPLOYED_BACKEND = "https://ssumcp.tail5e04bc.ts.net";

export function backendBaseUrl(): string {
  const configured = process.env.HEUNGMAP_BACKEND_URL;
  const fallback = process.env.VERCEL ? DEPLOYED_BACKEND : "http://127.0.0.1:8000";
  return (configured || fallback).replace(/\/+$/, "");
}
