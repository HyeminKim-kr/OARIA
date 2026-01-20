# ==============================================
# Stage 1: Dependencies
# ==============================================
FROM node:20-alpine AS deps

RUN apk add --no-cache libc6-compat

WORKDIR /app

# 패키지 매니저 lock 파일 복사 (캐싱 최적화)
COPY package.json package-lock.json* ./

# 의존성 설치 (clean install for reproducibility)
RUN npm ci

# ==============================================
# Stage 2: Builder
# ==============================================
FROM node:20-alpine AS builder

WORKDIR /app

# 의존성 복사
COPY --from=deps /app/node_modules ./node_modules
COPY . .

# 빌드 시점 환경변수 (필요시)
ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL

# Next.js 빌드
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

# ==============================================
# Stage 3: Runner (Production)
# ==============================================
FROM node:20-alpine AS runner

WORKDIR /app

# 프로덕션 환경 설정
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

# 보안: non-root user 생성
RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs

# standalone 출력물 복사
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static
# public 폴더가 비어있어도 복사 (빈 폴더 허용)
COPY --from=builder --chown=nextjs:nodejs /app/public ./public

# non-root user로 전환
USER nextjs

EXPOSE 13001
ENV PORT=13001
ENV HOSTNAME="0.0.0.0"

# 헬스체크
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:13001 || exit 1

CMD ["node", "server.js"]
