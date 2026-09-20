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
  async rewrites() {
    // 목적지는 빌드 시점에 확정된다. 환경변수가 비면 호스트가 사라져 Vercel이 DNS_HOSTNAME_EMPTY를 낸다.
    // 그래서 빈 문자열까지 걸러 내고(|| 사용), 배포 환경에서는 환경변수가 없어도 동작하도록 기본값을 둔다.
    // 로컬 개발에서는 그대로 127.0.0.1 백엔드를 본다.
    const DEPLOYED_BACKEND = "https://ssumcp.tail5e04bc.ts.net";
    const backend = (
      process.env.HEUNGMAP_BACKEND_URL ||
      (process.env.VERCEL ? DEPLOYED_BACKEND : "http://127.0.0.1:8000")
    ).replace(/\/+$/, "");
    return [
      {
        source: "/api/v1/:path*",
        destination: backend + "/api/v1/:path*",
      },
    ];
  },
};

export default nextConfig;
