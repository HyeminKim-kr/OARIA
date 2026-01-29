import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // Docker 배포용 standalone 출력
  output: "standalone",
  // CI 빌드 시 ESLint 경고로 인한 실패 방지
  eslint: {
    ignoreDuringBuilds: true,
  },
  // 3D Force Graph 관련 패키지 transpile
  transpilePackages: [
    "3d-force-graph",
    "three-forcegraph",
    "react-force-graph-3d",
    "three-spritetext",
  ],
};

export default nextConfig;
