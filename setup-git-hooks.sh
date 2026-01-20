#!/bin/bash

# ============================================================
# Git Hooks 설정 스크립트
# Jira 티켓 번호 자동 커밋 메시지 추가
# ============================================================

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo ""
echo "=========================================="
echo "  Git Hooks 설정"
echo "  OARIA 프로젝트"
echo "=========================================="
echo ""
echo "이 스크립트는 Jira 티켓 번호를 커밋 메시지에"
echo "자동으로 추가하는 Git Hook을 설정합니다."
echo ""

# Git 저장소 확인
if [ ! -d "$SCRIPT_DIR/.git" ]; then
    echo -e "${YELLOW}[경고]${NC} Git 저장소가 아닙니다."
    exit 1
fi

# .githooks 폴더 확인
if [ ! -d "$SCRIPT_DIR/.githooks" ]; then
    echo -e "${YELLOW}[경고]${NC} .githooks 폴더가 없습니다."
    exit 1
fi

echo -e "${BLUE}[1/3]${NC} Git hooks 경로 설정..."
git config core.hooksPath .githooks
echo -e "  ${GREEN}✓${NC} core.hooksPath = .githooks"

echo ""
echo -e "${BLUE}[2/3]${NC} Hook 파일 실행 권한 설정..."
chmod +x "$SCRIPT_DIR/.githooks/"*
echo -e "  ${GREEN}✓${NC} 실행 권한 부여 완료"

echo ""
echo -e "${BLUE}[3/3]${NC} 설정 확인..."
HOOKS_PATH=$(git config --get core.hooksPath)
echo -e "  ${GREEN}✓${NC} 현재 hooks 경로: $HOOKS_PATH"

echo ""
echo -e "${GREEN}${BOLD}=========================================="
echo "  설정 완료!"
echo "==========================================${NC}"
echo ""
echo "사용 방법:"
echo ""
echo "  1. Jira 티켓 번호가 포함된 브랜치 생성"
echo -e "     ${BLUE}git checkout -b feature/OAR-52-streamlit-setup${NC}"
echo ""
echo "  2. 일반적으로 커밋"
echo -e "     ${BLUE}git commit -m \"초기 설정 완료\"${NC}"
echo ""
echo "  3. 자동으로 변환됨"
echo -e "     ${GREEN}OAR-52 초기 설정 완료${NC}"
echo ""
echo "브랜치 명명 규칙:"
echo "  - feature/OAR-52-기능설명"
echo "  - fix/OAR-53-버그설명"
echo "  - hotfix/OAR-54-긴급수정"
echo ""
