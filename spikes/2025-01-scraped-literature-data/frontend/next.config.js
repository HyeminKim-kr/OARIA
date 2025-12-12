/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // API 프록시 설정
  // INTERNAL_API_URL: 서버사이드 전용 (Docker 네트워크 서비스 이름)
  // 클라이언트는 NEXT_PUBLIC_API_URL="" 사용하여 이 프록시를 통해 요청
  async rewrites() {
    const apiUrl = process.env.INTERNAL_API_URL || process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    console.log(`[Next.js] API Proxy -> ${apiUrl}`);
    return [
      {
        source: '/api/:path*',
        destination: `${apiUrl}/api/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;


