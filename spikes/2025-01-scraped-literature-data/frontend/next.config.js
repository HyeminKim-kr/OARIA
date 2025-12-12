/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // API 프록시 설정
  // Docker 환경: NEXT_PUBLIC_API_URL=http://backend:8000
  // 로컬 환경: NEXT_PUBLIC_API_URL=http://localhost:8000
  async rewrites() {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
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

