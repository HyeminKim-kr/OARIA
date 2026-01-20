import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // Docker 배포용 standalone 출력
  output: 'standalone',
};

export default nextConfig;
