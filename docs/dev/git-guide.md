# Git 가이드

프로젝트에서 사용하는 Git 브랜치 전략과 실무 가이드입니다.

---

## 핵심 원칙

> **"Jira는 Jira답게, Git은 Git답게"**

- Jira의 계층 구조(Epic → Task → Sub-task)를 Git 브랜치에 그대로 반영하지 않습니다
- Git 브랜치는 **단순하게** 유지합니다
- **커밋 메시지의 이슈 키**가 Git과 Jira를 연결하는 유일한 고리입니다

---

## 브랜치 전략

### 브랜치 구조

```
main (프로덕션)
  └── dev (개발 통합)
        ├── feature/OAR-XX-설명 (기능 개발)
        ├── fix/OAR-XX-설명 (버그 수정)
        ├── hotfix/OAR-XX-설명 (프로덕션 긴급 수정)
        └── spike/주제-이니셜 (실험/검증)
```

**이게 전부입니다.** Epic 브랜치, Task 브랜치 같은 중간 계층은 만들지 않습니다.

### 브랜치별 역할

| 브랜치 | 용도 | 어디서 분기 | 어디로 머지 |
|--------|------|------------|------------|
| `main` | 프로덕션 배포 | - | - |
| `dev` | 개발 통합 | main | main |
| `feature/*` | 새 기능 개발 | dev | dev |
| `fix/*` | 버그 수정 | dev | dev |
| `hotfix/*` | 프로덕션 긴급 수정 | main | main → dev |
| `spike/*` | 실험/PoC | dev | dev |

### 브랜치 네이밍

**일반 작업:**
```
<type>/OAR-<이슈번호>-<short-description>
```

예시:
```bash
feature/OAR-18-pubmed-api
fix/OAR-34-login-error
hotfix/OAR-56-payment-crash
```

**스파이크 (팀 스파이크 포함):**
```
spike/<주제>-<이니셜>
```

예시:
```bash
spike/pubmed-api-tsy
spike/embedding-kjh
spike/vectordb-plk
```

---

## Jira 연동

### 핵심: 커밋 메시지에 이슈 키 포함

```bash
git commit -m "OAR-50 PubMed API requests 기반 구현"
```

- 이슈 키는 **대문자** 사용 (OAR-50 ✅, oar-50 ❌)
- 커밋 메시지 **맨 앞**에 배치
- 이것만으로 Jira에서 커밋, 브랜치, PR이 자동 추적됩니다

### Jira 계층과 Git 매핑

Jira에서 복잡한 계층이 있어도 Git은 단순하게:

```
Jira 구조:
Epic OAR-9 (암 논문 자동 BATCH 수집기)
├── Task OAR-18 (PubMed API 연동)
│   ├── Sub-task OAR-50 (tsy 구현)
│   ├── Sub-task OAR-51 (kjh 구현)
│   └── Sub-task OAR-52 (plk 구현)

Git 브랜치:
dev
├── spike/pubmed-api-tsy    (OAR-50 커밋)
├── spike/pubmed-api-kjh    (OAR-51 커밋)
└── spike/pubmed-api-plk    (OAR-52 커밋)
```

**계층은 Jira에서 관리, Git은 flat하게 유지**

---

## 작업 흐름

### 일반 기능 개발

```bash
# 1. dev 최신화
git checkout dev
git pull origin dev

# 2. 기능 브랜치 생성
git checkout -b feat/12-user-login

# 3. 작업 & 커밋
git add .
git commit -m "feat(auth): 로그인 API 구현"

# 4. dev 변경사항 반영 (rebase로 깔끔하게)
git fetch origin dev
git rebase origin/dev

# 5. 푸시 & PR
git push origin feat/12-user-login
# GitHub에서 PR 생성: feat/12-user-login → dev
```

### 핫픽스 (프로덕션 긴급 수정)

```bash
# 1. main에서 분기
git checkout main
git pull origin main
git checkout -b hotfix/56-payment-crash

# 2. 수정 & 커밋
git commit -m "hotfix(payment): 결제 오류 수정"

# 3. main에 머지
git checkout main
git merge hotfix/56-payment-crash
git push origin main

# 4. dev에도 반영
git checkout dev
git merge hotfix/56-payment-crash
git push origin dev

# 5. 브랜치 삭제
git branch -d hotfix/56-payment-crash
```

### 스파이크 (실험)

```bash
# dev에서 분기
git checkout dev
git checkout -b spike/embedding-test

# 실험 진행...
# 결과가 좋으면 dev에 PR, 아니면 브랜치 삭제
```

---

## Rebase vs Merge

### 언제 Rebase?

**개인 브랜치**에서 dev/main 최신 변경사항 가져올 때:

```bash
# feat 브랜치에서 dev 최신화
git fetch origin dev
git rebase origin/dev
```

결과: 깔끔한 일직선 히스토리
```
* 내 커밋 3
* 내 커밋 2
* 내 커밋 1
* dev 최신 커밋
```

### 언제 Merge?

**공유 브랜치**(dev, main)에 기능 브랜치 합칠 때:

```bash
# PR 머지 또는
git checkout dev
git merge feat/user-login
```

결과: 머지 커밋으로 히스토리 보존
```
*   Merge pull request #12
|\
| * feat: 로그인 구현
|/
* 이전 커밋
```

### 요약

| 상황 | 방법 | 이유 |
|------|------|------|
| 내 브랜치에 dev 반영 | `rebase` | 깔끔한 히스토리 |
| dev에 내 브랜치 합치기 | `merge` (PR) | 작업 단위 보존 |
| main에 dev 합치기 | `merge` | 배포 히스토리 보존 |

---

## 자주 겪는 상황 해결

### 1. "안 이쁜" 그래프 방지

**문제**: `git pull`이 merge 커밋을 만들어서 그래프가 지저분해짐

```
*   Merge branch 'dev' into feat/my-feature
|\
| * 다른 사람 커밋
* | 내 커밋
|/
```

**해결**: rebase로 pull

```bash
git pull origin dev --rebase
```

결과:
```
* 내 커밋
* 다른 사람 커밋
```

### 2. Rebase 중 충돌

```bash
# 충돌 발생 시
git status                    # 충돌 파일 확인
# 파일 수정 후
git add .
git rebase --continue

# 포기하고 원래대로
git rebase --abort
```

### 3. 이미 푸시한 브랜치 rebase 후 푸시

```bash
# rebase 후에는 force push 필요 (개인 브랜치만!)
git push origin feat/my-feature --force-with-lease
```

**주의**: `main`, `dev` 같은 공유 브랜치에는 절대 force push 금지

### 4. 잘못된 브랜치에서 작업함

```bash
# 아직 커밋 안 했으면
git stash
git checkout 올바른-브랜치
git stash pop

# 이미 커밋했으면
git log --oneline -3          # 커밋 해시 확인
git checkout 올바른-브랜치
git cherry-pick <커밋해시>
git checkout 잘못된-브랜치
git reset --hard HEAD~1       # 잘못된 커밋 제거
```

### 5. 커밋 메시지 수정

```bash
# 마지막 커밋 메시지 수정
git commit --amend -m "새로운 메시지"

# 이미 푸시했으면 force push 필요
git push --force-with-lease
```

### 6. dev가 많이 앞서갔을 때

```bash
# 내 브랜치에서
git fetch origin dev
git rebase origin/dev

# 충돌 많으면 하나씩 해결
# 너무 복잡하면 새 브랜치 따서 변경사항만 옮기는 것도 방법
```

---

## 커밋 메시지 상세 가이드

### 형식

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Type 종류

| Type | 설명 | 예시 |
|------|------|------|
| `feat` | 새 기능 | `feat(auth): 소셜 로그인 추가` |
| `fix` | 버그 수정 | `fix(api): 토큰 만료 오류 수정` |
| `docs` | 문서 변경 | `docs: README 업데이트` |
| `style` | 코드 포맷팅 | `style: 들여쓰기 수정` |
| `refactor` | 리팩토링 | `refactor(user): 서비스 레이어 분리` |
| `test` | 테스트 | `test(auth): 로그인 테스트 추가` |
| `chore` | 빌드/설정 | `chore: 패키지 업데이트` |
| `hotfix` | 긴급 수정 | `hotfix(payment): 결제 오류 수정` |

### 좋은 커밋 메시지

```bash
# Good - 무엇을 왜 했는지 명확
feat(search): 논문 검색에 필터 기능 추가

암종, 연도별 필터링 지원
PubMed API 쿼리 파라미터 확장

# Bad - 모호함
fix: 버그 수정
update: 코드 업데이트
```

---

## PR 가이드

### PR 생성 전 체크리스트

- [ ] dev에서 rebase 했는가?
- [ ] 로컬에서 빌드/테스트 통과하는가?
- [ ] 커밋 메시지가 명확한가?
- [ ] 불필요한 파일(`.env`, `node_modules` 등) 포함 안 됐는가?

### PR 제목

커밋 컨벤션과 동일:
```
feat(auth): 사용자 인증 기능 구현
fix(api): 응답 시간 초과 오류 수정
```

### PR 본문 템플릿

```markdown
## 변경 사항
- 로그인 API 구현
- JWT 토큰 발급 로직 추가

## 테스트
- [ ] 로컬 테스트 완료
- [ ] API 테스트 완료

## 관련 이슈
Closes #12
```

---

## 유용한 Git 명령어

```bash
# 브랜치 목록 (로컬 + 리모트)
git branch -a

# 브랜치 삭제
git branch -d 브랜치명              # 로컬
git push origin --delete 브랜치명   # 리모트

# 최근 커밋 히스토리
git log --oneline -10

# 그래프로 보기
git log --oneline --graph --all

# 변경사항 확인
git diff                           # 스테이징 전
git diff --staged                  # 스테이징 후

# 특정 커밋으로 파일 복구
git checkout <커밋해시> -- 파일경로

# 작업 임시 저장
git stash
git stash pop
git stash list
```

---

## 금지 사항

1. **`main`, `dev`에 직접 푸시 금지** → PR로만 머지
2. **공유 브랜치에 force push 금지**
3. **`.env`, 시크릿 파일 커밋 금지**
4. **대용량 파일(데이터셋, 모델 등) 커밋 금지** → Git LFS 또는 외부 저장소 사용
