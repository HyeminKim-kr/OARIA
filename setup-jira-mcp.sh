#!/bin/bash

# ============================================================
# Atlassian MCP 서버 설정 스크립트 (Docker 기반)
# OARIA 프로젝트용
# ============================================================

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m' # No Color

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SAMPLE_CONFIG="$SCRIPT_DIR/sample.mcp.json"
MCP_CONFIG="$SCRIPT_DIR/.mcp.json"

# 구분선 출력 함수
print_separator() {
    echo ""
    echo "──────────────────────────────────────────"
    echo ""
}

# 단계 출력 함수
print_step() {
    echo -e "${BOLD}${BLUE}[$1/$2]${NC} $3"
}

echo ""
echo "=========================================="
echo "  Atlassian MCP 서버 설정 (Docker)"
echo "  OARIA 프로젝트"
echo "=========================================="
echo ""
echo "이 스크립트는 Jira/Confluence 연동을 위한"
echo "MCP 서버를 설정합니다."
print_separator

# ============================================================
# STEP 1: 시작 확인
# ============================================================
print_step 1 5 "설정을 시작합니다"
echo ""
echo "필요한 것:"
echo "  - Docker Desktop 실행 중"
echo "  - Atlassian 계정 (이메일)"
echo "  - Atlassian API 토큰"
echo ""
read -p "계속 진행할까요? (Y/n): " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Nn]$ ]]; then
    echo "설정을 취소합니다."
    exit 0
fi

print_separator

# ============================================================
# STEP 2: Docker 확인
# ============================================================
print_step 2 5 "Docker 환경 확인"
echo ""

# Docker 설치 확인
if ! command -v docker &> /dev/null; then
    echo -e "${RED}[ERROR] Docker가 설치되어 있지 않습니다.${NC}"
    echo ""
    echo "Docker Desktop을 먼저 설치해주세요:"
    echo "  https://docs.docker.com/get-docker/"
    exit 1
fi
echo -e "  ${GREEN}✓${NC} Docker 설치됨"

# Docker 데몬 실행 확인
if ! docker info &> /dev/null 2>&1; then
    echo -e "${RED}[ERROR] Docker 데몬이 실행되고 있지 않습니다.${NC}"
    echo ""
    echo "Docker Desktop을 실행해주세요."
    exit 1
fi
echo -e "  ${GREEN}✓${NC} Docker 데몬 실행 중"

# sample.mcp.json 존재 확인
if [ ! -f "$SAMPLE_CONFIG" ]; then
    echo -e "${RED}[ERROR] sample.mcp.json 파일이 없습니다.${NC}"
    echo "  경로: $SAMPLE_CONFIG"
    exit 1
fi
echo -e "  ${GREEN}✓${NC} sample.mcp.json 확인됨"

echo ""
read -p "계속 진행할까요? (Y/n): " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Nn]$ ]]; then
    echo "설정을 취소합니다."
    exit 0
fi

print_separator

# ============================================================
# STEP 3: Docker 이미지 다운로드
# ============================================================
print_step 3 5 "Docker 이미지 다운로드"
echo ""
echo "MCP Atlassian 이미지를 다운로드합니다."
echo "  이미지: ghcr.io/sooperset/mcp-atlassian:latest"
echo ""
read -p "다운로드를 시작할까요? (Y/n): " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Nn]$ ]]; then
    echo "설정을 취소합니다."
    exit 0
fi

echo ""
docker pull ghcr.io/sooperset/mcp-atlassian:latest
echo ""
echo -e "  ${GREEN}✓${NC} Docker 이미지 준비 완료"

print_separator

# ============================================================
# STEP 4: 계정 정보 입력
# ============================================================
print_step 4 5 "Atlassian 계정 정보 입력"
echo ""

# 기존 설정 파일 확인
if [ -f "$MCP_CONFIG" ]; then
    echo -e "${YELLOW}[주의]${NC} 기존 .mcp.json 파일이 있습니다."
    echo ""
    read -p "기존 설정을 덮어쓸까요? (y/N): " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "기존 설정을 유지합니다. 설정을 종료합니다."
        exit 0
    fi
    echo ""
fi

# 이메일 입력
echo -e "${BLUE}Atlassian 이메일 주소를 입력하세요:${NC}"
read -p "> " ATLASSIAN_EMAIL

if [ -z "$ATLASSIAN_EMAIL" ]; then
    echo -e "${RED}[ERROR] 이메일 주소가 필요합니다.${NC}"
    exit 1
fi

echo ""
echo -e "  ${GREEN}✓${NC} 이메일: $ATLASSIAN_EMAIL"

# API 토큰 입력
echo ""
echo -e "${BLUE}API 토큰을 입력하세요:${NC}"
echo ""
echo "  토큰이 없다면 아래 링크에서 생성하세요:"
echo "  https://id.atlassian.com/manage-profile/security/api-tokens"
echo ""
echo "  생성 방법:"
echo "    1. 위 링크 접속 → Atlassian 로그인"
echo "    2. 'Create API token' 클릭"
echo "    3. 라벨 입력 (예: claude-code-mcp)"
echo "    4. 생성된 토큰 복사"
echo ""
read -s -p "> " API_TOKEN
echo ""

if [ -z "$API_TOKEN" ]; then
    echo -e "${RED}[ERROR] API 토큰이 필요합니다.${NC}"
    exit 1
fi

echo -e "  ${GREEN}✓${NC} API 토큰 입력됨"

print_separator

# ============================================================
# STEP 5: 설정 파일 생성
# ============================================================
print_step 5 5 "설정 파일 생성"
echo ""
echo "sample.mcp.json을 복사하여 .mcp.json을 생성합니다."
echo ""
read -p "설정 파일을 생성할까요? (Y/n): " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Nn]$ ]]; then
    echo "설정을 취소합니다."
    exit 0
fi

# sample.mcp.json 복사
cp "$SAMPLE_CONFIG" "$MCP_CONFIG"

# 이메일 대체 (your email → 실제 이메일)
sed -i '' "s/your email/$ATLASSIAN_EMAIL/g" "$MCP_CONFIG"

# API 토큰 대체 (빈 문자열 → 실제 토큰)
# CONFLUENCE_API_TOKEN과 JIRA_API_TOKEN 모두 대체
sed -i '' "s/\"CONFLUENCE_API_TOKEN\": \"\"/\"CONFLUENCE_API_TOKEN\": \"$API_TOKEN\"/g" "$MCP_CONFIG"
sed -i '' "s/\"JIRA_API_TOKEN\": \"\"/\"JIRA_API_TOKEN\": \"$API_TOKEN\"/g" "$MCP_CONFIG"

echo ""
echo -e "  ${GREEN}✓${NC} .mcp.json 파일 생성 완료"

print_separator

# ============================================================
# 완료
# ============================================================
echo -e "${GREEN}${BOLD}=========================================="
echo "  설정 완료!"
echo "==========================================${NC}"
echo ""
echo "설정 파일: $MCP_CONFIG"
echo ""
echo -e "${YELLOW}[보안 안내]${NC}"
echo "  .mcp.json 파일에 API 토큰이 포함되어 있습니다."
echo "  .gitignore에 이미 추가되어 있어 Git에 커밋되지 않습니다."
echo ""
echo -e "${BLUE}[다음 단계]${NC}"
echo "  1. Claude Code를 재시작하거나 새 세션을 시작하세요"
echo "  2. 자연어로 Jira/Confluence 명령을 사용하세요"
echo ""
echo "사용 예시:"
echo "  - \"OARIA 프로젝트 이슈 목록 보여줘\""
echo "  - \"새 Task 이슈 만들어줘\""
echo "  - \"OAR-8 이슈 상태 변경해줘\""
echo ""
