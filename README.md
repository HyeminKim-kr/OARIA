# OARIA

AI Bootcamp - OARIA Team

## Tech Stack

- **Frontend**: Next.js 15.5.7, React 19, TypeScript, Tailwind CSS
- **Backend**: Python 3.11, FastAPI, Pydantic

## Project Structure

```
oaria/
├── frontend/          # Next.js 프론트엔드
│   ├── src/
│   │   ├── app/       # App Router
│   │   └── ...
│   └── package.json
├── backend/           # Python 백엔드
│   ├── app/
│   │   └── main.py    # FastAPI 엔트리포인트
│   └── pyproject.toml
└── README.md
```

## Getting Started

### Prerequisites

- Node.js 18+
- Python 3.11
- uv (Python package manager)

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend runs at `http://localhost:3000`

### Backend

```bash
cd backend
uv sync
uv run uvicorn app.main:app --reload
```

Backend runs at `http://localhost:8000`

---

## Development Conventions

### Git Commit Convention

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types:**
- `feat`: 새로운 기능
- `fix`: 버그 수정
- `docs`: 문서 변경
- `style`: 코드 포맷팅 (세미콜론 등)
- `refactor`: 코드 리팩토링
- `test`: 테스트 추가/수정
- `chore`: 빌드, 설정 파일 변경

**Examples:**
```
feat(auth): add user login API
fix(frontend): resolve hydration error on dashboard
docs: update README with setup instructions
```

### Branch Naming

```
<type>/<issue-number>-<short-description>
```

**Examples:**
```
feat/12-user-authentication
fix/34-dashboard-loading
```

### Code Style

#### Frontend (TypeScript/React)

- ESLint + Prettier 사용
- 함수형 컴포넌트 + hooks 사용
- 파일명: PascalCase (컴포넌트), camelCase (유틸리티)
- 절대 경로 import (`@/`) 사용

```typescript
// Good
import { Button } from '@/components/ui/Button';

// Bad
import { Button } from '../../../components/ui/Button';
```

#### Backend (Python)

- Ruff 또는 Black + isort 사용 권장
- Type hints 필수
- 함수/변수: snake_case
- 클래스: PascalCase
- 상수: UPPER_SNAKE_CASE

```python
# Good
async def get_user_by_id(user_id: int) -> User:
    ...

# Bad
async def getUserById(userId):
    ...
```

### API Design

- RESTful 규칙 준수
- 응답 형식 통일 (JSON)
- HTTP 상태 코드 적절히 사용
- 버전 관리: `/api/v1/...`

### File Organization

#### Frontend

```
src/
├── app/              # App Router pages
├── components/       # 재사용 컴포넌트
│   ├── ui/           # 기본 UI 컴포넌트
│   └── features/     # 기능별 컴포넌트
├── hooks/            # Custom hooks
├── lib/              # 유틸리티, API 클라이언트
├── types/            # TypeScript 타입 정의
└── styles/           # 글로벌 스타일
```

#### Backend

```
app/
├── main.py           # FastAPI 앱 엔트리포인트
├── api/              # API 라우터
│   └── v1/
├── core/             # 설정, 보안
├── models/           # Pydantic 모델
├── services/         # 비즈니스 로직
└── utils/            # 유틸리티 함수
```

### PR Guidelines

1. PR 제목은 commit convention 따르기
2. 관련 이슈 번호 연결
3. 변경 사항 요약 작성
4. 스크린샷 첨부 (UI 변경 시)
5. 리뷰어 최소 1명 승인 필요

### Environment Variables

- `.env` 파일은 gitignore에 포함
- `.env.example` 파일로 필요한 변수 문서화
- 민감한 정보는 절대 커밋하지 않기
