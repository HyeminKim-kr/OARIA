/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // API 프록시는 src/pages/api/[...path].ts 에서 처리
  // 에러 시 간결한 로그 출력
};

module.exports = nextConfig;
