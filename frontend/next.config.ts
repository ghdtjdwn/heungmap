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
    return [
      {
        source: "/api/v1/:path*",
        destination: "http://127.0.0.1:8000/api/v1/:path*",
      },
    ];
  },
};

export default nextConfig;
