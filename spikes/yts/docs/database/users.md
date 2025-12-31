# Auth & Users 테이블 스키마

> **사용자, 관리자, 인증 관련 테이블**
>
> **Last Updated**: 2026-01-01

---

## 개요

서비스 사용자와 관리자를 분리하고, 소셜 로그인 및 JWT refresh token을 관리하는 테이블 구조입니다.

### 소유권 분리

| 테이블 | Owner | Migration Tool | 설명 |
|--------|-------|----------------|------|
| `users` | Backend | Alembic | 서비스 사용자 |
| `social_accounts` | Backend | Alembic | 소셜 로그인 연동 |
| `user_refresh_tokens` | Backend | Alembic | 사용자 JWT refresh token |
| `admin_users` | Admin Backend | TypeORM | 관리자 |
| `admin_refresh_tokens` | Admin Backend | TypeORM | 관리자 JWT refresh token |

> **중요**: users 관련 테이블은 Alembic, admin 관련 테이블은 TypeORM에서 관리됩니다.

---

## 아키텍처

```
┌─────────────────────────────────────────────────────────────────┐
│                     Auth Architecture                            │
└─────────────────────────────────────────────────────────────────┘

  [Service Frontend]                    [Admin Frontend]
         │                                     │
         ▼                                     ▼
  ┌─────────────┐                       ┌─────────────┐
  │   Backend   │                       │Admin Backend│
  │  (FastAPI)  │                       │  (NestJS)   │
  └──────┬──────┘                       └──────┬──────┘
         │                                     │
         ▼                                     ▼
  ┌─────────────┐                       ┌─────────────┐
  │   users     │                       │ admin_users │
  │   social_   │                       │ admin_      │
  │   accounts  │                       │ refresh_    │
  │   user_     │                       │ tokens      │
  │   refresh_  │                       └─────────────┘
  │   tokens    │
  └─────────────┘
```

---

## ER 다이어그램

```
┌─────────────────┐
│     users       │
├─────────────────┤
│ id (PK)         │
│ email           │
│ name            │
│ picture         │
│ is_active       │
│ created_at      │
│ updated_at      │
│ last_login_at   │
└────────┬────────┘
         │
    ┌────┴────┐
    │ 1:N     │ 1:N
    ▼         ▼
┌─────────────────┐  ┌──────────────────────┐
│ social_accounts │  │ user_refresh_tokens  │
├─────────────────┤  ├──────────────────────┤
│ id (PK)         │  │ id (PK)              │
│ user_id (FK)    │  │ user_id (FK)         │
│ provider        │  │ token_hash           │
│ provider_id     │  │ expires_at           │
│ provider_email  │  │ device_info          │
│ ...             │  │ revoked_at           │
└─────────────────┘  └──────────────────────┘


┌─────────────────┐       ┌──────────────────────┐
│   admin_users   │──1:N──│ admin_refresh_tokens │
├─────────────────┤       ├──────────────────────┤
│ id (PK)         │       │ id (PK)              │
│ email           │       │ admin_id (FK)        │
│ password_hash   │       │ token_hash           │
│ name            │       │ expires_at           │
│ role            │       │ ...                  │
│ ...             │       └──────────────────────┘
└─────────────────┘
```

---

## users (서비스 사용자)

서비스를 이용하는 일반 사용자입니다. 소셜 로그인으로만 가입 가능합니다.

### 컬럼 정의

| 컬럼 | 타입 | Nullable | 기본값 | 설명 |
|------|------|----------|--------|------|
| **id** | `UUID` | NO | `gen_random_uuid()` | Primary Key |
| **email** | `VARCHAR(255)` | NO | - | 이메일 (Unique) |
| name | `VARCHAR(255)` | YES | - | 사용자 이름 |
| picture | `VARCHAR(512)` | YES | - | 프로필 이미지 URL |
| **is_active** | `BOOLEAN` | NO | `TRUE` | 활성화 여부 |
| **created_at** | `TIMESTAMPTZ` | NO | `NOW()` | 생성 시각 |
| **updated_at** | `TIMESTAMPTZ` | NO | `NOW()` | 수정 시각 |
| last_login_at | `TIMESTAMPTZ` | YES | - | 마지막 로그인 시각 |

### DDL

```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) NOT NULL,
    name VARCHAR(255),
    picture VARCHAR(512),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_login_at TIMESTAMPTZ
);

CREATE UNIQUE INDEX ix_users_email ON users(email);
```

---

## admin_users (관리자)

Admin 시스템을 이용하는 관리자입니다. **Google OAuth**로 로그인합니다.

### 컬럼 정의

| 컬럼 | 타입 | Nullable | 기본값 | 설명 |
|------|------|----------|--------|------|
| **id** | `UUID` | NO | `gen_random_uuid()` | Primary Key |
| **email** | `VARCHAR(255)` | NO | - | 이메일 (Unique) |
| **google_id** | `VARCHAR(255)` | NO | - | Google OAuth ID (Unique) |
| name | `VARCHAR(255)` | YES | - | 관리자 이름 |
| picture | `VARCHAR(512)` | YES | - | 프로필 이미지 URL |
| **status** | `VARCHAR(20)` | NO | `'pending'` | 승인 상태 |
| **role** | `VARCHAR(50)` | NO | `'admin'` | 역할 |
| approved_by | `UUID` | YES | - | 승인한 관리자 ID |
| approved_at | `TIMESTAMPTZ` | YES | - | 승인 시각 |
| rejected_reason | `TEXT` | YES | - | 거절 사유 |
| **is_active** | `BOOLEAN` | NO | `TRUE` | 활성화 여부 |
| deactivated_by | `UUID` | YES | - | 비활성화한 관리자 ID |
| deactivated_at | `TIMESTAMPTZ` | YES | - | 비활성화 시각 |
| **created_at** | `TIMESTAMPTZ` | NO | `NOW()` | 생성 시각 |
| **updated_at** | `TIMESTAMPTZ` | NO | `NOW()` | 수정 시각 |
| last_login_at | `TIMESTAMPTZ` | YES | - | 마지막 로그인 시각 |

### 상태 (status)

| 값 | 설명 |
|----|------|
| `pending` | 승인 대기 (최초 가입 시) |
| `approved` | 승인됨 (로그인 가능) |
| `rejected` | 거절됨 (로그인 불가) |

### 역할 (role)

| 값 | 설명 | 권한 |
|----|------|------|
| `super_admin` | 최고 관리자 | 모든 권한, 관리자 승인/비활성화 |
| `admin` | 일반 관리자 | 논문 관리, 배치 작업 실행 |
| `viewer` | 뷰어 | 조회만 가능 |

### DDL

```sql
CREATE TABLE admin_users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) NOT NULL,
    google_id VARCHAR(255) NOT NULL,
    name VARCHAR(255),
    picture VARCHAR(512),
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    role VARCHAR(50) NOT NULL DEFAULT 'admin',
    approved_by UUID REFERENCES admin_users(id),
    approved_at TIMESTAMPTZ,
    rejected_reason TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    deactivated_by UUID REFERENCES admin_users(id),
    deactivated_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_login_at TIMESTAMPTZ
);

CREATE UNIQUE INDEX ix_admin_users_email ON admin_users(email);
CREATE UNIQUE INDEX ix_admin_users_google_id ON admin_users(google_id);
CREATE INDEX ix_admin_users_status ON admin_users(status);
CREATE INDEX ix_admin_users_role ON admin_users(role);
```

---

## social_accounts (소셜 로그인)

사용자의 소셜 로그인 연동 정보입니다. 한 사용자가 여러 소셜 계정을 연동할 수 있습니다.

### 컬럼 정의

| 컬럼 | 타입 | Nullable | 기본값 | 설명 |
|------|------|----------|--------|------|
| **id** | `UUID` | NO | `gen_random_uuid()` | Primary Key |
| **user_id** | `UUID` | NO | - | FK → users.id |
| **provider** | `VARCHAR(50)` | NO | - | 소셜 프로바이더 |
| **provider_id** | `VARCHAR(255)` | NO | - | 프로바이더 내 고유 ID |
| provider_email | `VARCHAR(255)` | YES | - | 소셜 계정 이메일 |
| provider_name | `VARCHAR(255)` | YES | - | 소셜 계정 이름 |
| provider_picture | `VARCHAR(512)` | YES | - | 소셜 계정 프로필 이미지 |
| access_token | `TEXT` | YES | - | OAuth access token (암호화) |
| refresh_token | `TEXT` | YES | - | OAuth refresh token (암호화) |
| token_expires_at | `TIMESTAMPTZ` | YES | - | access token 만료 시각 |
| **created_at** | `TIMESTAMPTZ` | NO | `NOW()` | 연동 시각 |
| **updated_at** | `TIMESTAMPTZ` | NO | `NOW()` | 수정 시각 |

### 프로바이더 (provider)

| 값 | 설명 |
|----|------|
| `google` | Google OAuth |
| `kakao` | 카카오 로그인 |
| `naver` | 네이버 로그인 |
| `apple` | Apple 로그인 |

### DDL

```sql
CREATE TABLE social_accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    provider VARCHAR(50) NOT NULL,
    provider_id VARCHAR(255) NOT NULL,
    provider_email VARCHAR(255),
    provider_name VARCHAR(255),
    provider_picture VARCHAR(512),
    access_token TEXT,
    refresh_token TEXT,
    token_expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE(provider, provider_id)
);

CREATE INDEX ix_social_accounts_user_id ON social_accounts(user_id);
CREATE INDEX ix_social_accounts_provider ON social_accounts(provider);
```

---

## user_refresh_tokens (사용자 JWT Refresh Token)

서비스 사용자의 JWT refresh token을 관리합니다. Token rotation과 revocation을 지원합니다.

### 컬럼 정의

| 컬럼 | 타입 | Nullable | 기본값 | 설명 |
|------|------|----------|--------|------|
| **id** | `UUID` | NO | `gen_random_uuid()` | Primary Key |
| **user_id** | `UUID` | NO | - | FK → users.id |
| **token_hash** | `VARCHAR(64)` | NO | - | refresh token SHA256 해시 |
| **expires_at** | `TIMESTAMPTZ` | NO | - | 만료 시각 |
| device_info | `VARCHAR(255)` | YES | - | User-Agent 또는 디바이스 정보 |
| ip_address | `VARCHAR(45)` | YES | - | 발급 시 IP (IPv6 지원) |
| revoked_at | `TIMESTAMPTZ` | YES | - | 폐기 시각 (NULL=유효) |
| revoked_reason | `VARCHAR(100)` | YES | - | 폐기 사유 |
| **created_at** | `TIMESTAMPTZ` | NO | `NOW()` | 발급 시각 |
| last_used_at | `TIMESTAMPTZ` | YES | - | 마지막 사용 시각 |

### Revoke 사유 (revoked_reason)

| 값 | 설명 |
|----|------|
| `logout` | 사용자 로그아웃 |
| `token_rotation` | 토큰 갱신으로 인한 폐기 |
| `security` | 보안상 폐기 |
| `admin_action` | 관리자에 의한 폐기 |
| `expired` | 만료 |

### DDL

```sql
CREATE TABLE user_refresh_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash VARCHAR(64) NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    device_info VARCHAR(255),
    ip_address VARCHAR(45),
    revoked_at TIMESTAMPTZ,
    revoked_reason VARCHAR(100),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_used_at TIMESTAMPTZ
);

CREATE INDEX ix_user_refresh_tokens_user_id ON user_refresh_tokens(user_id);
CREATE INDEX ix_user_refresh_tokens_token_hash ON user_refresh_tokens(token_hash);
CREATE INDEX ix_user_refresh_tokens_valid ON user_refresh_tokens(user_id, expires_at)
    WHERE revoked_at IS NULL;
```

---

## admin_refresh_tokens (관리자 JWT Refresh Token)

관리자의 JWT refresh token을 관리합니다. 구조는 user_refresh_tokens와 동일합니다.

### 컬럼 정의

| 컬럼 | 타입 | Nullable | 기본값 | 설명 |
|------|------|----------|--------|------|
| **id** | `UUID` | NO | `gen_random_uuid()` | Primary Key |
| **admin_id** | `UUID` | NO | - | FK → admin_users.id |
| **token_hash** | `VARCHAR(64)` | NO | - | refresh token SHA256 해시 |
| **expires_at** | `TIMESTAMPTZ` | NO | - | 만료 시각 |
| device_info | `VARCHAR(255)` | YES | - | User-Agent 또는 디바이스 정보 |
| ip_address | `VARCHAR(45)` | YES | - | 발급 시 IP |
| revoked_at | `TIMESTAMPTZ` | YES | - | 폐기 시각 |
| revoked_reason | `VARCHAR(100)` | YES | - | 폐기 사유 |
| **created_at** | `TIMESTAMPTZ` | NO | `NOW()` | 발급 시각 |
| last_used_at | `TIMESTAMPTZ` | YES | - | 마지막 사용 시각 |

### DDL

```sql
CREATE TABLE admin_refresh_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    admin_id UUID NOT NULL REFERENCES admin_users(id) ON DELETE CASCADE,
    token_hash VARCHAR(64) NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    device_info VARCHAR(255),
    ip_address VARCHAR(45),
    revoked_at TIMESTAMPTZ,
    revoked_reason VARCHAR(100),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_used_at TIMESTAMPTZ
);

CREATE INDEX ix_admin_refresh_tokens_admin_id ON admin_refresh_tokens(admin_id);
CREATE INDEX ix_admin_refresh_tokens_token_hash ON admin_refresh_tokens(token_hash);
CREATE INDEX ix_admin_refresh_tokens_valid ON admin_refresh_tokens(admin_id, expires_at)
    WHERE revoked_at IS NULL;
```

---

## 인증 흐름

### 서비스 사용자 (소셜 로그인)

```
┌─────────────┐      ┌─────────────┐      ┌─────────────┐
│   Frontend  │      │   Backend   │      │   Google    │
└──────┬──────┘      └──────┬──────┘      └──────┬──────┘
       │                    │                    │
       │  1. /auth/google   │                    │
       │ ─────────────────► │                    │
       │                    │                    │
       │  2. Redirect       │                    │
       │ ◄───────────────── │                    │
       │                    │                    │
       │  3. Google Login ──────────────────────►│
       │  4. Callback    ◄──────────────────────│
       │                    │                    │
       │  5. /auth/callback │                    │
       │ ─────────────────► │                    │
       │                    │                    │
       │                    │  6. Verify & get user info
       │                    │                    │
       │                    │  7. Upsert user + social_account
       │                    │  8. Create refresh_token in DB
       │                    │  9. Generate JWT (access + refresh)
       │                    │                    │
       │  10. { access_token, refresh_token }    │
       │ ◄───────────────── │                    │
```

### Token Refresh

```
┌─────────────┐      ┌─────────────┐      ┌─────────────┐
│   Frontend  │      │   Backend   │      │     DB      │
└──────┬──────┘      └──────┬──────┘      └──────┬──────┘
       │                    │                    │
       │  1. POST /auth/refresh                  │
       │     { refresh_token }                   │
       │ ─────────────────► │                    │
       │                    │                    │
       │                    │  2. Hash token     │
       │                    │  3. Find in DB ───►│
       │                    │  4. Validate ◄─────│
       │                    │                    │
       │                    │  5. Revoke old token (rotation)
       │                    │  6. Create new refresh_token
       │                    │  7. Generate new JWT pair
       │                    │                    │
       │  8. { access_token, refresh_token }     │
       │ ◄───────────────── │                    │
```

### 관리자 (이메일/비밀번호)

```
┌─────────────┐      ┌─────────────┐      ┌─────────────┐
│Admin Frontend     │Admin Backend │      │     DB      │
└──────┬──────┘      └──────┬──────┘      └──────┬──────┘
       │                    │                    │
       │  1. POST /auth/login                    │
       │     { email, password }                 │
       │ ─────────────────► │                    │
       │                    │                    │
       │                    │  2. Find admin ───►│
       │                    │  3. Verify pwd ◄───│
       │                    │  4. Create refresh_token
       │                    │  5. Generate JWT   │
       │                    │                    │
       │  6. { access_token, refresh_token }     │
       │ ◄───────────────── │                    │
```

---

## 보안 고려사항

### Refresh Token

- **DB 저장**: 실제 토큰이 아닌 SHA256 해시만 저장
- **Token Rotation**: refresh 시 기존 토큰 폐기 + 새 토큰 발급
- **디바이스 추적**: 로그인 디바이스별 토큰 관리
- **강제 로그아웃**: 특정 토큰 또는 전체 토큰 revoke 가능

### 비밀번호

- **bcrypt 해싱**: cost factor 12 이상 권장
- **Admin 전용**: 서비스 사용자는 소셜 로그인만

### Access Token

- **짧은 만료 시간**: 15분 ~ 1시간
- **Refresh Token**: 7일 ~ 30일

---

## 쿼리 예시

### 소셜 계정으로 사용자 찾기

```sql
SELECT u.*
FROM users u
JOIN social_accounts sa ON u.id = sa.user_id
WHERE sa.provider = 'google'
  AND sa.provider_id = '110625557621719756026';
```

### 유효한 refresh token 확인

```sql
SELECT *
FROM user_refresh_tokens
WHERE token_hash = 'sha256_hash_here'
  AND expires_at > NOW()
  AND revoked_at IS NULL;
```

### 사용자의 모든 세션 폐기 (강제 로그아웃)

```sql
UPDATE user_refresh_tokens
SET revoked_at = NOW(),
    revoked_reason = 'security'
WHERE user_id = 'xxx-xxx-xxx'
  AND revoked_at IS NULL;
```

### 관리자 목록 (역할별)

```sql
SELECT id, email, name, role, last_login_at
FROM admin_users
WHERE is_active = TRUE
ORDER BY
    CASE role
        WHEN 'super_admin' THEN 1
        WHEN 'admin' THEN 2
        ELSE 3
    END,
    name;
```

---

## 마이그레이션 순서

기존 `users` 테이블에서 새 구조로 마이그레이션하는 순서:

1. `social_accounts` 테이블 생성
2. `users.google_id` → `social_accounts`로 데이터 이전
3. `users`에서 `google_id`, `is_superuser` 컬럼 제거
4. `admin_users` 테이블 생성
5. `user_refresh_tokens` 테이블 생성
6. `admin_refresh_tokens` 테이블 생성

---

## 관련 문서

- [README.md](./README.md) - 데이터베이스 개요
- Backend Auth: `app/routers/auth.py`
- Admin Backend Auth: `admin/backend/src/modules/auth/`
