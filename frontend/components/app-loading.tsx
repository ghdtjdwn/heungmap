import Image from "next/image";

/**
 * 세션 확인처럼 화면 전체가 대기 상태일 때 쓰는 로딩 화면.
 * 글자만 두면 멈춘 것처럼 보여서 로고와 진행 표시를 함께 보여 준다.
 */
export function AppLoading({ message = "로그인 상태를 확인하고 있습니다" }: { message?: string }) {
  return (
    <main className="page-shell loading-shell">
      <div className="loading-card" role="status" aria-live="polite">
        <Image
          className="loading-logo"
          src="/assets/heungmap-logo.png"
          alt="흥할지도"
          width={900}
          height={269}
          priority
        />
        <div className="loading-bar" aria-hidden="true"><span /></div>
        <p className="loading-message">{message}</p>
      </div>
    </main>
  );
}
