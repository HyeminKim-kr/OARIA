백엔드 실행 방법

  # 1. 백엔드 디렉토리로 이동
  cd spikes/yts/backend

  # 2. 의존성 설치 (이미 되어 있으면 생략)
  uv sync

  # 3. .env 파일 설정 (Google OAuth 키 필요)
  # GOOGLE_CLIENT_ID=your_client_id
  # GOOGLE_CLIENT_SECRET=your_client_secret

  # 4. DB 마이그레이션 (PostgreSQL 실행 필요)
  uv run alembic upgrade head

  # 5. 서버 실행
  uv run uvicorn app.main:app --reload --port 8000