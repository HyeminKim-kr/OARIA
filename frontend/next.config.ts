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
  // Three.js WebGL 버전 강제 사용 (WebGPU 대신)
  webpack: (config, { isServer }) => {
    if (!isServer) {
      config.resolve.alias = {
        ...config.resolve.alias,
        // three/webgpu 요청을 일반 three로 리다이렉트 (WebGL 사용)
        "three/webgpu": "three",
      };
    }
    return config;
  },
};

export default nextConfig;
