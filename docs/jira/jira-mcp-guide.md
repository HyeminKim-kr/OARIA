# Jira MCP 서버 설정 가이드

Claude Code에서 Jira와 연동하여 이슈 생성, 조회, 업데이트를 자연어로 수행할 수 있습니다.

---

## 설정 방법 (Docker 기반)

OARIA 프로젝트는 Docker 기반 MCP 서버를 사용합니다.

### 자동 설정 (권장)

프로젝트 루트에서 설정 스크립트를 실행합니다:

```bash
./setup-jira-mcp.sh
```

스크립트가 단계별로 안내하며 다음을 수행합니다:
1. Docker 환경 확인
2. MCP Docker 이미지 다운로드
3. Atlassian 계정 정보 입력 (이메일, API 토큰)
4. `.mcp.json` 설정 파일 생성

### 수동 설정

1. **API 토큰 생성**
   - https://id.atlassian.com/manage-profile/security/api-tokens 접속
   - 'Create API token' 클릭
   - 라벨 입력 (예: `claude-code-mcp`)
   - 생성된 토큰 복사

2. **설정 파일 생성**

   `sample.mcp.json`을 `.mcp.json`으로 복사:
   ```bash
   cp sample.mcp.json .mcp.json
   ```

3. **값 입력**

   `.mcp.json` 파일을 열고 다음 값을 수정:
   ```json
   {
     "mcpServers": {
       "mcp-atlassian": {
         "command": "docker",
         "args": [
           "run", "--rm", "-i",
           "-e", "CONFLUENCE_URL",
           "-e", "CONFLUENCE_USERNAME",
           "-e", "CONFLUENCE_API_TOKEN",
           "-e", "JIRA_URL",
           "-e", "JIRA_USERNAME",
           "-e", "JIRA_API_TOKEN",
           "ghcr.io/sooperset/mcp-atlassian:latest"
         ],
         "env": {
           "CONFLUENCE_URL": "https://hyemink.atlassian.net/wiki",
           "CONFLUENCE_USERNAME": "your-email@example.com",
           "CONFLUENCE_API_TOKEN": "your-api-token",
           "JIRA_URL": "https://hyemink.atlassian.net",
           "JIRA_USERNAME": "your-email@example.com",
           "JIRA_API_TOKEN": "your-api-token"
         }
       }
     }
   }
   ```

4. **Claude Code 재시작**

---

## 사용 예시

### 이슈 조회

```
"OAR-8 이슈 내용 보여줘"
"현재 스프린트의 In Progress 이슈들 목록 알려줘"
"내가 담당하고 있는 이슈 목록"
```

### 이슈 생성

```
"OARIA 프로젝트에 새 이슈 만들어줘. 제목은 '로그인 페이지 UI 개선', 타입은 Task로"
"방금 작업한 버그 수정에 대한 이슈 생성해줘"
```

### 이슈 업데이트

```
"OAR-8 이슈 상태를 Done으로 변경해줘"
"OAR-8에 댓글 추가해줘: 코드 리뷰 완료했습니다"
```

### 검색

```
"이번 주에 생성된 버그 이슈들 검색해줘"
"'인증' 관련 이슈 찾아줘"
```

---

## 주요 기능 (Tools)

| 도구 | 설명 |
|------|------|
| `jira_get_issue` | 특정 이슈 상세 조회 |
| `jira_search` | JQL로 이슈 검색 |
| `jira_create_issue` | 새 이슈 생성 |
| `jira_update_issue` | 이슈 수정 |
| `jira_add_comment` | 이슈에 댓글 추가 |
| `jira_get_transitions` | 이슈 상태 전환 옵션 조회 |
| `jira_transition_issue` | 이슈 상태 변경 |
| `confluence_search` | Confluence 문서 검색 |
| `confluence_get_page` | Confluence 페이지 조회 |

---

## 요구사항

- **Docker Desktop** 실행 중
- **Atlassian Cloud** 계정 (Jira Cloud, Confluence Cloud)
- 해당 프로젝트에 대한 접근 권한
- Claude Code 최신 버전

---

## 연결 확인

설정 후 Claude Code에서 연결 상태를 확인합니다:

```bash
claude mcp list
```

정상 연결 시:
```
mcp-atlassian: docker run ... - ✓ Connected
```

---

## 트러블슈팅

### "MCP 서버에 연결할 수 없습니다"

1. Docker Desktop이 실행 중인지 확인
2. `.mcp.json` 파일이 프로젝트 루트에 있는지 확인
3. Claude Code 재시작

### "권한이 없습니다" / 401 에러

1. API 토큰이 유효한지 확인 (만료되지 않았는지)
2. 이메일 주소가 정확한지 확인
3. 해당 Jira 프로젝트에 접근 권한이 있는지 확인

### Docker 이미지 문제

```bash
# 이미지 다시 다운로드
docker pull ghcr.io/sooperset/mcp-atlassian:latest
```

### 설정 초기화

```bash
# .mcp.json 삭제 후 스크립트 재실행
rm .mcp.json
./setup-jira-mcp.sh
```

---

## 보안 주의사항

- `.mcp.json` 파일에는 API 토큰이 포함되어 있습니다
- `.gitignore`에 `.mcp.json`이 추가되어 있어 Git에 커밋되지 않습니다
- API 토큰을 타인과 공유하지 마세요
- 정기적으로 API 토큰을 갱신하는 것을 권장합니다

---

## 참고 자료

- [mcp-atlassian GitHub](https://github.com/sooperset/mcp-atlassian)
- [Atlassian API 토큰 관리](https://id.atlassian.com/manage-profile/security/api-tokens)
- [Claude Code MCP 설정 가이드](https://docs.anthropic.com/en/docs/claude-code/mcp)
