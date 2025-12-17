# uv 가이드

**uv**는 Rust로 작성된 빠른 Python 패키지 매니저입니다. pip + venv를 대체하며, 10-100배 빠른 속도를 제공합니다.

---

## 설치

### macOS / Linux

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Windows

```powershell
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### Homebrew (macOS)

```bash
brew install uv
```

설치 확인:

```bash
uv --version
```

---

## 기본 사용법

### 프로젝트 초기화

```bash
# 새 프로젝트 생성
uv init my-project
cd my-project

# 기존 프로젝트에서 초기화
uv init
```

### 의존성 설치

```bash
# pyproject.toml 기반 의존성 설치 (가상환경 자동 생성)
uv sync

# 패키지 추가
uv add requests
uv add fastapi uvicorn

# 개발 의존성 추가
uv add --dev pytest ruff

# 패키지 제거
uv remove requests
```

### 스크립트 실행

```bash
# Python 스크립트 실행
uv run python main.py

# 모듈 실행
uv run python -m pytest

# FastAPI 서버 실행
uv run uvicorn app.main:app --reload
```

> `uv run`을 사용하면 가상환경 활성화 없이 바로 실행 가능합니다.

---

## venv + pip vs uv 비교

| 항목 | venv + pip | uv |
|------|------------|-----|
| **속도** | 느림 | 10-100배 빠름 |
| **의존성 파일** | requirements.txt | pyproject.toml |
| **락파일** | 없음 (수동 관리) | uv.lock (자동 생성) |
| **가상환경 활성화** | 필요 | 불필요 (`uv run`) |
| **Python 버전 관리** | pyenv 등 별도 도구 | 내장 지원 |

### 기존 방식 (venv + pip)

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

### uv 방식

```bash
uv sync
uv run python main.py
```

---

## Python 버전 관리

```bash
# 사용 가능한 Python 버전 확인
uv python list

# 특정 버전 설치
uv python install 3.11

# 프로젝트에서 사용할 버전 지정 (pyproject.toml에 저장됨)
uv python pin 3.11
```

---

## 주요 파일

### pyproject.toml

프로젝트 메타데이터와 의존성 정의:

```toml
[project]
name = "my-project"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn>=0.32.0",
]

[tool.uv]
dev-dependencies = [
    "pytest>=8.0.0",
    "ruff>=0.8.0",
]
```

### uv.lock

- 자동 생성되는 락파일
- 모든 의존성의 정확한 버전 고정
- **Git에 커밋해야 함** (팀원 간 동일 환경 보장)

---

## 자주 쓰는 명령어 요약

| 명령어 | 설명 |
|--------|------|
| `uv init` | 프로젝트 초기화 |
| `uv sync` | 의존성 설치 (가상환경 자동 생성) |
| `uv add <패키지>` | 패키지 추가 |
| `uv add --dev <패키지>` | 개발 의존성 추가 |
| `uv remove <패키지>` | 패키지 제거 |
| `uv run <명령>` | 가상환경에서 명령 실행 |
| `uv lock` | 락파일 갱신 |
| `uv python install <버전>` | Python 버전 설치 |

---

## 트러블슈팅

### Q: `uv: command not found`

설치 후 터미널 재시작 또는:

```bash
source ~/.bashrc  # 또는 ~/.zshrc
```

### Q: 기존 requirements.txt를 uv로 마이그레이션하려면?

```bash
uv add -r requirements.txt
```

### Q: 가상환경 위치는?

프로젝트 루트의 `.venv/` 폴더에 자동 생성됩니다.

---

## 참고 링크

- [uv 공식 문서](https://docs.astral.sh/uv/)
- [uv GitHub](https://github.com/astral-sh/uv)
