# Admin Backend (NestJS)
# admin/backend/Dockerfile

FROM node:20-alpine AS builder

WORKDIR /app

# 의존성 설치
COPY package*.json ./
RUN npm ci

# 소스 복사 및 빌드
COPY . .
RUN npm run build

# ─────────────────────────────────────────
# Production
# ─────────────────────────────────────────
FROM node:20-alpine AS production

WORKDIR /app

# 프로덕션 의존성만 설치
COPY package*.json ./
RUN npm ci --only=production

# 빌드 결과물 복사
COPY --from=builder /app/dist ./dist

# 환경 변수
ENV NODE_ENV=production \
    PORT=3000

EXPOSE 3000

# 헬스체크
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:3000/health || exit 1

CMD ["node", "dist/main"]
