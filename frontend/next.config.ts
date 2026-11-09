import type { NextConfig } from "next";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const projectRoot = path.dirname(fileURLToPath(import.meta.url));

function rootEnvValue(name: string): string {
  if (process.env.HEUNGMAP_SKIP_ROOT_ENV === "true") return "";
  try {
    const content = fs.readFileSync(path.resolve(projectRoot, "../.env"), "utf8");
    const line = content.split(/\r?\n/).find((entry) => entry.startsWith(`${name}=`));
    return line?.slice(name.length + 1).trim().replace(/^(['"])(.*)\1$/, "$2") ?? "";
  } catch {
    return "";
  }
}

const nextConfig: NextConfig = {
  agentRules: false,
  allowedDevOrigins: ["127.0.0.1"],
  reactStrictMode: true,
  env: {
    NEXT_PUBLIC_KAKAO_JAVASCRIPT_KEY: process.env.KAKAO_JAVASCRIPT_KEY ?? rootEnvValue("KAKAO_JAVASCRIPT_KEY"),
  },
  turbopack: {
    root: projectRoot,
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
        ],
      },
    ];
  },
  async rewrites() {
    // 목적지는 빌드 시점에 확정된다. 환경변수가 빈 문자열이면 호스트가 사라져 Vercel이 DNS_HOSTNAME_EMPTY를 내므로
    // ||로 빈 값까지 걸러 낸다. 배포 환경(VERCEL)에서는 HEUNGMAP_BACKEND_URL을 프로젝트 환경변수로 반드시 넣고,
    // 없으면 잘못된 주소로 배포되기 전에 빌드를 멈춘다. 로컬 개발에서는 127.0.0.1 백엔드를 본다.
    // lib/backend.ts 와 같은 규칙. next.config는 번들 밖에서 실행돼 import를 피한다.
    const configured = process.env.HEUNGMAP_BACKEND_URL || "";
    if (!configured && process.env.VERCEL) {
      throw new Error("HEUNGMAP_BACKEND_URL이 비어 있습니다. Vercel 프로젝트 환경변수에 백엔드 공개 주소를 넣어 주세요.");
    }
    const backend = (configured || "http://127.0.0.1:8000").replace(/\/+$/, "");
    return [
      {
        source: "/api/v1/:path*",
        destination: backend + "/api/v1/:path*",
      },
    ];
  },
};

export default nextConfig;
