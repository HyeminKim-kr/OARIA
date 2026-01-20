#!/bin/bash

# ============================================================
# Git Merge Script (Rebase + No-FF Merge)
# 스파이크 브랜치를 dev에 머지하는 스크립트
# --no-ff 옵션으로 브랜치 히스토리가 그래프에 시각적으로 남음
#
# 사용법:
#   ./git-merge.sh              # 현재 브랜치를 dev에 머지
#   ./git-merge.sh -d           # 머지 후 브랜치 삭제
#   ./git-merge.sh --dry-run    # 실제 실행 없이 미리보기
# ============================================================

set -e

# 색상 정의
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

# 옵션 파싱
DELETE_BRANCH=false
DRY_RUN=false

while [[ $# -gt 0 ]]; do
    case $1 in
        -d|--delete)
            DELETE_BRANCH=true
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        -h|--help)
            echo "사용법: ./scripts/git-merge.sh [옵션]"
            echo ""
            echo "옵션:"
            echo "  -d, --delete    머지 후 브랜치 삭제"
            echo "  --dry-run       실제 실행 없이 미리보기"
            echo "  -h, --help      도움말 출력"
            exit 0
            ;;
        *)
            echo -e "${RED}[ERROR] 알 수 없는 옵션: $1${NC}"
            exit 1
            ;;
    esac
done

echo ""
echo "=========================================="
echo "  Git Merge (Rebase + No-FF)"
echo "=========================================="
echo ""

# 현재 브랜치 확인
CURRENT_BRANCH=$(git symbolic-ref --short HEAD 2>/dev/null)

if [ -z "$CURRENT_BRANCH" ]; then
    echo -e "${RED}[ERROR] Git 저장소가 아니거나 detached HEAD 상태입니다.${NC}"
    exit 1
fi

echo -e "현재 브랜치: ${BOLD}${BLUE}$CURRENT_BRANCH${NC}"
echo ""

# dev, main 브랜치에서 실행 방지
if [ "$CURRENT_BRANCH" = "dev" ] || [ "$CURRENT_BRANCH" = "main" ]; then
    echo -e "${RED}[ERROR] dev 또는 main 브랜치에서는 실행할 수 없습니다.${NC}"
    echo ""
    echo "머지할 브랜치로 먼저 이동하세요:"
    echo -e "  ${BLUE}git checkout spike/your-branch${NC}"
    exit 1
fi

# 작업 중인 변경사항 확인
if ! git diff --quiet || ! git diff --cached --quiet; then
    echo -e "${RED}[ERROR] 커밋되지 않은 변경사항이 있습니다.${NC}"
    echo ""
    echo "먼저 커밋하거나 stash 하세요:"
    echo -e "  ${BLUE}git stash${NC}"
    echo -e "  ${BLUE}git commit -am \"작업 내용\"${NC}"
    exit 1
fi

# 실행 계획 출력
echo -e "${BOLD}실행 계획:${NC}"
echo -e "  1. origin/dev 최신화 (fetch)"
echo -e "  2. ${BLUE}$CURRENT_BRANCH${NC}를 dev 위로 rebase"
echo -e "  3. dev로 전환 후 --no-ff 머지 (브랜치 히스토리 보존)"
echo -e "  4. origin/dev에 push"
if [ "$DELETE_BRANCH" = true ]; then
    echo -e "  5. ${BLUE}$CURRENT_BRANCH${NC} 브랜치 삭제"
fi
echo ""

if [ "$DRY_RUN" = true ]; then
    echo -e "${YELLOW}[DRY-RUN] 미리보기 모드 - 실제 실행하지 않습니다.${NC}"
    exit 0
fi

read -p "계속 진행할까요? (Y/n): " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Nn]$ ]]; then
    echo "취소되었습니다."
    exit 0
fi

echo ""

# Step 1: Fetch
echo -e "${BOLD}[1/4] origin/dev 최신화...${NC}"
git fetch origin dev
echo -e "  ${GREEN}✓${NC} fetch 완료"
echo ""

# Step 2: Rebase
echo -e "${BOLD}[2/4] $CURRENT_BRANCH를 dev 위로 rebase...${NC}"

if ! git rebase origin/dev; then
    echo ""
    echo -e "${RED}[ERROR] Rebase 중 충돌이 발생했습니다.${NC}"
    echo ""
    echo "해결 방법:"
    echo "  1. 충돌 파일 수정"
    echo "  2. git add <파일>"
    echo "  3. git rebase --continue"
    echo ""
    echo "또는 rebase 취소:"
    echo -e "  ${BLUE}git rebase --abort${NC}"
    exit 1
fi
echo -e "  ${GREEN}✓${NC} rebase 완료"
echo ""

# Step 3: Checkout dev and merge
echo -e "${BOLD}[3/4] dev로 전환 후 --no-ff 머지...${NC}"
git checkout dev
git pull origin dev --ff-only 2>/dev/null || true

if ! git merge "$CURRENT_BRANCH" --no-ff -m "Merge branch '$CURRENT_BRANCH' into dev"; then
    echo ""
    echo -e "${RED}[ERROR] 머지 실패${NC}"
    echo ""
    echo "충돌이 발생했을 수 있습니다."
    echo "브랜치로 돌아가서 다시 rebase 하세요:"
    echo -e "  ${BLUE}git merge --abort${NC}"
    echo -e "  ${BLUE}git checkout $CURRENT_BRANCH${NC}"
    echo -e "  ${BLUE}git rebase origin/dev${NC}"
    exit 1
fi
echo -e "  ${GREEN}✓${NC} 머지 완료 (--no-ff, 브랜치 히스토리 보존)"
echo ""

# Step 4: Push
echo -e "${BOLD}[4/4] origin/dev에 push...${NC}"
git push origin dev
echo -e "  ${GREEN}✓${NC} push 완료"
echo ""

# Optional: Delete branch
if [ "$DELETE_BRANCH" = true ]; then
    echo -e "${BOLD}[5/5] 브랜치 삭제...${NC}"
    git branch -d "$CURRENT_BRANCH"
    echo -e "  ${GREEN}✓${NC} 로컬 브랜치 삭제 완료"

    # 원격 브랜치도 삭제할지 확인
    read -p "원격 브랜치도 삭제할까요? (y/N): " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        git push origin --delete "$CURRENT_BRANCH" 2>/dev/null || echo -e "  ${YELLOW}원격 브랜치가 없거나 이미 삭제됨${NC}"
        echo -e "  ${GREEN}✓${NC} 원격 브랜치 삭제 완료"
    fi
    echo ""
fi

# 완료 메시지
echo "=========================================="
echo -e "${GREEN}${BOLD}  머지 완료!${NC}"
echo "=========================================="
echo ""
echo -e "브랜치 ${BLUE}$CURRENT_BRANCH${NC}가 dev에 머지되었습니다."
echo ""
echo "Git 그래프 확인:"
echo -e "  ${BLUE}git log --oneline --graph -10${NC}"
echo ""
