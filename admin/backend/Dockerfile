# ==============================================
# Stage 1: Builder
# ==============================================
FROM node:20-alpine AS builder

WORKDIR /app

# 패키지 파일 복사 (캐싱 최적화)
COPY package.json package-lock.json* ./

# 모든 의존성 설치 (빌드에 devDependencies 필요)
RUN npm ci

# 소스 코드 복사
COPY . .

# NestJS 빌드
RUN npm run build

# ==============================================
# Stage 2: Production Dependencies
# ==============================================
FROM node:20-alpine AS deps

WORKDIR /app

COPY package.json package-lock.json* ./

# 프로덕션 의존성만 설치
RUN npm ci --omit=dev && npm cache clean --force

# ==============================================
# Stage 3: Runner (Production)
# ==============================================
FROM node:20-alpine AS runner

WORKDIR /app

# 프로덕션 환경 설정
ENV NODE_ENV=production

# 보안: non-root user 생성
RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nestjs

# 프로덕션 의존성 복사
COPY --from=deps /app/node_modules ./node_modules

# 빌드된 파일 복사
COPY --from=builder --chown=nestjs:nodejs /app/dist ./dist
COPY --from=builder /app/package.json ./

# non-root user로 전환
USER nestjs

EXPOSE 13000
ENV PORT=13000

# 헬스체크
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:13000/system/health || exit 1

CMD ["node", "dist/main"]
