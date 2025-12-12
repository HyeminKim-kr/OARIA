/**
 * API Proxy Handler with Clean Error Logging
 * 
 * Next.js rewrites의 에러를 한 줄로 압축하여 출력
 * 백엔드 연결 실패 시 간단한 메시지만 표시
 */

import type { NextApiRequest, NextApiResponse } from 'next';

const BACKEND_URL = process.env.INTERNAL_API_URL || process.env.NEXT_PUBLIC_API_URL || 'http://backend:8000';

// 마지막 에러 시간 (중복 로그 방지)
let lastErrorLog = 0;

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse
) {
  const { path, ...queryParams } = req.query;
  const pathArray = path as string[];
  
  // Query string 빌드 (path 제외한 모든 파라미터)
  const queryString = Object.entries(queryParams)
    .filter(([_, value]) => value !== undefined && value !== '')
    .map(([key, value]) => {
      if (Array.isArray(value)) {
        return value.map(v => `${encodeURIComponent(key)}=${encodeURIComponent(v)}`).join('&');
      }
      return `${encodeURIComponent(key)}=${encodeURIComponent(value as string)}`;
    })
    .join('&');
  
  const targetUrl = `${BACKEND_URL}/api/${pathArray.join('/')}${queryString ? '?' + queryString : ''}`;

  try {
    // POST/PUT/PATCH 요청의 body 준비
    let body: string | undefined = undefined;
    if (req.method !== 'GET' && req.method !== 'HEAD' && req.body) {
      body = typeof req.body === 'string' ? req.body : JSON.stringify(req.body);
    }

    const response = await fetch(targetUrl, {
      method: req.method,
      headers: {
        'Content-Type': 'application/json',
        // 다른 헤더는 전달하지 않음 (host, content-length 등 충돌 방지)
      },
      body,
    });

    // JSON 응답이 아닐 수 있으므로 먼저 text로 받음
    const text = await response.text();
    try {
      const data = JSON.parse(text);
      res.status(response.status).json(data);
    } catch {
      // JSON이 아니면 텍스트로 반환
      res.status(response.status).send(text);
    }
  } catch (error: any) {
    const now = Date.now();
    
    // 30초마다 한 번만 간단한 에러 로그 출력
    if (now - lastErrorLog > 30000) {
      console.warn(`⚠️ Backend unavailable: ${BACKEND_URL}`);
      lastErrorLog = now;
    }

    res.status(503).json({ 
      error: 'Backend unavailable',
      message: 'Service temporarily unavailable'
    });
  }
}
