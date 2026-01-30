/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  transpilePackages: ['three'],

  // iframe 임베딩 및 CORS 허용
  async headers() {
    return [
      {
        source: '/:path*',
        headers: [
          // X-Frame-Options 제거 (CSP frame-ancestors 사용)
          // iframe 임베딩 허용 - 모든 도메인
          {
            key: 'Content-Security-Policy',
            value: "frame-ancestors *",
          },
          // CORS 허용 - 모든 도메인
          {
            key: 'Access-Control-Allow-Origin',
            value: '*',
          },
          {
            key: 'Access-Control-Allow-Methods',
            value: 'GET, POST, PUT, DELETE, OPTIONS',
          },
          {
            key: 'Access-Control-Allow-Headers',
            value: 'Content-Type, Authorization, X-Requested-With',
          },
          {
            key: 'Access-Control-Allow-Credentials',
            value: 'true',
          },
        ],
      },
    ];
  },
}

module.exports = nextConfig
