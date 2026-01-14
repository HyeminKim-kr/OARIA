#!/bin/bash

# ============================================================
# Git Commit Workflow Script
# 인터랙티브하게 스테이징, 커밋, 머지까지 한 번에 처리
#
# 사용법:
#   ./scripts/git-commit.sh           # 전체 워크플로우
#   ./scripts/git-commit.sh --no-merge # 커밋만 (머지 안함)
# ============================================================

set -e

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

# 프로젝트 루트
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# 옵션
NO_MERGE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --no-merge)
            NO_MERGE=true
            shift
            ;;
        -h|--help)
            echo "사용법: ./scripts/git-commit.sh [옵션]"
            echo ""
            echo "옵션:"
            echo "  --no-merge    커밋만 하고 머지 안함"
            echo "  -h, --help    도움말"
            exit 0
            ;;
        *)
            shift
            ;;
    esac
done

print_header() {
    echo ""
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${CYAN}  $1${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

print_step() {
    echo ""
    echo -e "${BOLD}${BLUE}[$1]${NC} $2"
    echo ""
}

# ============================================================
# Step 1: 브랜치 확인
# ============================================================
check_branch() {
    print_header "Git Commit Workflow"

    CURRENT_BRANCH=$(git symbolic-ref --short HEAD 2>/dev/null)

    if [ -z "$CURRENT_BRANCH" ]; then
        echo -e "${RED}[ERROR] Git 저장소가 아니거나 detached HEAD 상태입니다.${NC}"
        exit 1
    fi

    print_step "1/5" "브랜치 확인"

    echo -e "  현재 브랜치: ${BOLD}${MAGENTA}$CURRENT_BRANCH${NC}"
    echo ""

    # dev, main에서 직접 커밋 경고
    if [ "$CURRENT_BRANCH" = "dev" ] || [ "$CURRENT_BRANCH" = "main" ]; then
        echo -e "  ${YELLOW}⚠ 경고: $CURRENT_BRANCH 브랜치에서 직접 작업 중입니다!${NC}"
        echo ""
        echo -e "  ${DIM}보통은 feature 브랜치에서 작업하는 것이 권장됩니다.${NC}"
        echo ""

        echo "  선택하세요:"
        echo -e "    ${GREEN}1)${NC} 이대로 진행 (${CURRENT_BRANCH}에 커밋)"
        echo -e "    ${GREEN}2)${NC} 새 브랜치 생성 후 진행"
        echo -e "    ${GREEN}q)${NC} 취소"
        echo ""
        read -p "  선택 (1/2/q): " branch_choice

        case $branch_choice in
            1)
                echo -e "\n  ${GREEN}✓${NC} ${CURRENT_BRANCH} 브랜치에서 계속합니다."
                ;;
            2)
                create_new_branch
                ;;
            *)
                echo "  취소되었습니다."
                exit 0
                ;;
        esac
    else
        read -p "  이 브랜치에서 작업하는 게 맞나요? (Y/n): " confirm
        if [[ $confirm =~ ^[Nn]$ ]]; then
            echo ""
            echo "  선택하세요:"
            echo -e "    ${GREEN}1)${NC} 다른 브랜치로 전환"
            echo -e "    ${GREEN}2)${NC} 새 브랜치 생성"
            echo -e "    ${GREEN}q)${NC} 취소"
            echo ""
            read -p "  선택 (1/2/q): " branch_action

            case $branch_action in
                1)
                    switch_branch
                    ;;
                2)
                    create_new_branch
                    ;;
                *)
                    echo "  취소되었습니다."
                    exit 0
                    ;;
            esac
        fi
    fi
}

switch_branch() {
    echo ""
    echo "  최근 브랜치 목록:"

    # 최근 브랜치 5개 표시
    local branches=($(git for-each-ref --sort=-committerdate refs/heads/ --format='%(refname:short)' | head -10))
    local i=1
    for branch in "${branches[@]}"; do
        if [ "$branch" != "$CURRENT_BRANCH" ]; then
            echo -e "    ${GREEN}$i)${NC} $branch"
            ((i++))
        fi
        if [ $i -gt 5 ]; then
            break
        fi
    done
    echo -e "    ${GREEN}0)${NC} 직접 입력"
    echo ""

    read -p "  선택: " branch_num

    if [ "$branch_num" = "0" ]; then
        read -p "  브랜치 이름: " target_branch
    else
        # 인덱스 계산 (현재 브랜치 제외)
        local idx=0
        local count=1
        for branch in "${branches[@]}"; do
            if [ "$branch" != "$CURRENT_BRANCH" ]; then
                if [ "$count" = "$branch_num" ]; then
                    target_branch="$branch"
                    break
                fi
                ((count++))
            fi
            ((idx++))
        done
    fi

    if [ -n "$target_branch" ]; then
        git checkout "$target_branch"
        CURRENT_BRANCH="$target_branch"
        echo -e "\n  ${GREEN}✓${NC} ${MAGENTA}$CURRENT_BRANCH${NC} 브랜치로 전환했습니다."
    fi
}

create_new_branch() {
    echo ""
    echo "  브랜치 타입을 선택하세요:"
    echo -e "    ${GREEN}1)${NC} feat/    (새 기능)"
    echo -e "    ${GREEN}2)${NC} fix/     (버그 수정)"
    echo -e "    ${GREEN}3)${NC} refactor/(리팩토링)"
    echo -e "    ${GREEN}4)${NC} docs/    (문서)"
    echo -e "    ${GREEN}5)${NC} spike/   (스파이크/실험)"
    echo -e "    ${GREEN}0)${NC} 직접 입력"
    echo ""
    read -p "  선택: " type_choice

    case $type_choice in
        1) prefix="feat/" ;;
        2) prefix="fix/" ;;
        3) prefix="refactor/" ;;
        4) prefix="docs/" ;;
        5) prefix="spike/" ;;
        0) prefix="" ;;
        *) prefix="feat/" ;;
    esac

    echo ""
    read -p "  브랜치 이름 (${prefix}): " branch_name

    local new_branch="${prefix}${branch_name}"

    git checkout -b "$new_branch"
    CURRENT_BRANCH="$new_branch"
    echo -e "\n  ${GREEN}✓${NC} ${MAGENTA}$CURRENT_BRANCH${NC} 브랜치를 생성하고 전환했습니다."
}

# ============================================================
# Step 2: 변경사항 확인 및 스테이징
# ============================================================
stage_files() {
    print_step "2/5" "파일 스테이징"

    # 변경된 파일 목록 가져오기
    local modified_files=($(git diff --name-only 2>/dev/null))
    local untracked_files=($(git ls-files --others --exclude-standard 2>/dev/null))
    local staged_files=($(git diff --cached --name-only 2>/dev/null))

    local total_modified=${#modified_files[@]}
    local total_untracked=${#untracked_files[@]}
    local total_staged=${#staged_files[@]}

    if [ $total_modified -eq 0 ] && [ $total_untracked -eq 0 ] && [ $total_staged -eq 0 ]; then
        echo -e "  ${YELLOW}변경된 파일이 없습니다.${NC}"
        exit 0
    fi

    # 이미 스테이징된 파일 표시
    if [ $total_staged -gt 0 ]; then
        echo -e "  ${GREEN}이미 스테이징된 파일 ($total_staged개):${NC}"
        for file in "${staged_files[@]}"; do
            echo -e "    ${GREEN}✓${NC} $file"
        done
        echo ""
    fi

    # 수정된 파일과 새 파일 합치기
    local all_unstaged=("${modified_files[@]}" "${untracked_files[@]}")
    local total_unstaged=${#all_unstaged[@]}

    if [ $total_unstaged -eq 0 ]; then
        echo -e "  ${DIM}추가로 스테이징할 파일이 없습니다.${NC}"
        return
    fi

    echo "  스테이징할 파일을 선택하세요:"
    echo ""
    echo -e "    ${GREEN}a)${NC} 전체 선택"
    echo -e "    ${GREEN}s)${NC} 개별 선택"
    echo -e "    ${GREEN}n)${NC} 선택 안함 (이미 스테이징된 것만 커밋)"
    echo ""
    read -p "  선택 (a/s/n): " stage_choice

    case $stage_choice in
        a|A)
            git add -A
            echo -e "\n  ${GREEN}✓${NC} 모든 파일을 스테이징했습니다."
            ;;
        s|S)
            select_files_to_stage "${all_unstaged[@]}"
            ;;
        n|N)
            if [ $total_staged -eq 0 ]; then
                echo -e "\n  ${RED}스테이징된 파일이 없습니다. 취소합니다.${NC}"
                exit 0
            fi
            echo -e "\n  ${GREEN}✓${NC} 기존 스테이징 유지"
            ;;
        *)
            git add -A
            echo -e "\n  ${GREEN}✓${NC} 모든 파일을 스테이징했습니다."
            ;;
    esac
}

select_files_to_stage() {
    local files=("$@")
    local selected=()

    echo ""
    echo "  파일 목록 (번호로 선택, 완료 시 엔터):"
    echo ""

    local i=1
    for file in "${files[@]}"; do
        # 새 파일인지 수정된 파일인지 표시
        if git ls-files --others --exclude-standard | grep -q "^$file$"; then
            echo -e "    ${GREEN}$i)${NC} ${CYAN}[NEW]${NC} $file"
        else
            echo -e "    ${GREEN}$i)${NC} ${YELLOW}[MOD]${NC} $file"
        fi
        ((i++))
    done

    echo ""
    echo -e "  ${DIM}예: 1 3 5 또는 1-5 또는 all${NC}"
    read -p "  선택: " selection

    if [ "$selection" = "all" ]; then
        git add "${files[@]}"
        echo -e "\n  ${GREEN}✓${NC} 모든 파일을 스테이징했습니다."
        return
    fi

    # 범위 선택 처리 (예: 1-5)
    if [[ $selection =~ ^([0-9]+)-([0-9]+)$ ]]; then
        local start=${BASH_REMATCH[1]}
        local end=${BASH_REMATCH[2]}
        for ((j=start; j<=end; j++)); do
            local idx=$((j-1))
            if [ $idx -ge 0 ] && [ $idx -lt ${#files[@]} ]; then
                git add "${files[$idx]}"
                echo -e "  ${GREEN}+${NC} ${files[$idx]}"
            fi
        done
    else
        # 개별 번호 선택
        for num in $selection; do
            local idx=$((num-1))
            if [ $idx -ge 0 ] && [ $idx -lt ${#files[@]} ]; then
                git add "${files[$idx]}"
                echo -e "  ${GREEN}+${NC} ${files[$idx]}"
            fi
        done
    fi

    echo -e "\n  ${GREEN}✓${NC} 선택한 파일을 스테이징했습니다."
}

# ============================================================
# Step 3: Jira 티켓 확인
# ============================================================
get_jira_ticket() {
    print_step "3/5" "Jira 티켓"

    # 브랜치 이름에서 티켓 번호 추출 시도 (예: feat/OAR-123-something)
    local ticket_from_branch=$(echo "$CURRENT_BRANCH" | grep -oE '[A-Z]+-[0-9]+' | head -1)

    if [ -n "$ticket_from_branch" ]; then
        echo -e "  브랜치에서 티켓 감지: ${CYAN}$ticket_from_branch${NC}"
        read -p "  이 티켓을 사용할까요? (Y/n): " use_detected

        if [[ ! $use_detected =~ ^[Nn]$ ]]; then
            JIRA_TICKET="$ticket_from_branch"
            return
        fi
    fi

    echo "  Jira 티켓을 커밋에 추가할까요?"
    echo ""
    echo -e "    ${GREEN}1)${NC} 티켓 번호 입력 (예: OAR-123)"
    echo -e "    ${GREEN}2)${NC} 티켓 없이 진행"
    echo ""
    read -p "  선택 (1/2): " ticket_choice

    case $ticket_choice in
        1)
            read -p "  티켓 번호: " JIRA_TICKET
            JIRA_TICKET=$(echo "$JIRA_TICKET" | tr '[:lower:]' '[:upper:]')
            echo -e "\n  ${GREEN}✓${NC} 티켓: ${CYAN}$JIRA_TICKET${NC}"
            ;;
        *)
            JIRA_TICKET=""
            echo -e "\n  ${DIM}티켓 없이 진행합니다.${NC}"
            ;;
    esac
}

# ============================================================
# Step 4: 커밋 메시지 작성
# ============================================================
create_commit() {
    print_step "4/5" "커밋 메시지"

    # 스테이징된 파일 미리보기
    echo "  스테이징된 변경사항:"
    echo -e "  ${DIM}────────────────────────────────────${NC}"
    git diff --cached --stat | head -20 | sed 's/^/  /'
    echo -e "  ${DIM}────────────────────────────────────${NC}"
    echo ""

    # 커밋 타입 선택
    echo "  커밋 타입을 선택하세요:"
    echo ""
    echo -e "    ${GREEN}1)${NC} feat     새 기능"
    echo -e "    ${GREEN}2)${NC} fix      버그 수정"
    echo -e "    ${GREEN}3)${NC} refactor 리팩토링"
    echo -e "    ${GREEN}4)${NC} docs     문서"
    echo -e "    ${GREEN}5)${NC} style    스타일 (포맷팅 등)"
    echo -e "    ${GREEN}6)${NC} test     테스트"
    echo -e "    ${GREEN}7)${NC} chore    기타"
    echo -e "    ${GREEN}0)${NC} 직접 입력"
    echo ""
    read -p "  선택: " type_num

    case $type_num in
        1) COMMIT_TYPE="feat" ;;
        2) COMMIT_TYPE="fix" ;;
        3) COMMIT_TYPE="refactor" ;;
        4) COMMIT_TYPE="docs" ;;
        5) COMMIT_TYPE="style" ;;
        6) COMMIT_TYPE="test" ;;
        7) COMMIT_TYPE="chore" ;;
        0)
            read -p "  커밋 타입: " COMMIT_TYPE
            ;;
        *) COMMIT_TYPE="feat" ;;
    esac

    # 스코프 (선택)
    echo ""
    read -p "  스코프 (선택, 예: admin, backend, frontend): " COMMIT_SCOPE

    # 커밋 메시지
    echo ""
    read -p "  커밋 메시지: " COMMIT_MSG

    # 메시지 조합
    if [ -n "$COMMIT_SCOPE" ]; then
        FULL_MSG="${COMMIT_TYPE}(${COMMIT_SCOPE}): ${COMMIT_MSG}"
    else
        FULL_MSG="${COMMIT_TYPE}: ${COMMIT_MSG}"
    fi

    # Jira 티켓 추가
    if [ -n "$JIRA_TICKET" ]; then
        FULL_MSG="${FULL_MSG}

${JIRA_TICKET}"
    fi

    # 미리보기
    echo ""
    echo -e "  ${BOLD}커밋 미리보기:${NC}"
    echo -e "  ${DIM}────────────────────────────────────${NC}"
    echo -e "  ${CYAN}$FULL_MSG${NC}"
    echo -e "  ${DIM}────────────────────────────────────${NC}"
    echo ""

    read -p "  이대로 커밋할까요? (Y/n): " confirm_commit

    if [[ $confirm_commit =~ ^[Nn]$ ]]; then
        echo ""
        read -p "  메시지 직접 입력: " FULL_MSG
    fi

    # 커밋 실행
    git commit -m "$FULL_MSG"

    echo ""
    echo -e "  ${GREEN}✓${NC} 커밋 완료!"
}

# ============================================================
# Step 5: Push / 머지
# ============================================================
run_push_or_merge() {
    if [ "$NO_MERGE" = true ]; then
        return
    fi

    print_step "5/5" "Push / 머지"

    # dev, main 브랜치면 push 옵션
    if [ "$CURRENT_BRANCH" = "dev" ] || [ "$CURRENT_BRANCH" = "main" ]; then
        echo "  커밋이 완료되었습니다. origin/${CURRENT_BRANCH}에 push할까요?"
        echo ""
        echo -e "    ${GREEN}1)${NC} 지금 push"
        echo -e "    ${GREEN}2)${NC} 나중에 push (스킵)"
        echo ""
        read -p "  선택 (1/2): " push_choice

        case $push_choice in
            1)
                echo ""
                echo -e "  ${YELLOW}▸${NC} origin/${CURRENT_BRANCH}에 push 중..."
                git push origin "$CURRENT_BRANCH"
                echo -e "  ${GREEN}✓${NC} push 완료!"
                ;;
            *)
                echo ""
                echo -e "  ${DIM}push를 건너뜁니다.${NC}"
                echo ""
                echo "  나중에 push하려면:"
                echo -e "    ${BLUE}git push origin ${CURRENT_BRANCH}${NC}"
                ;;
        esac
    else
        # feature 브랜치면 머지 옵션
        echo "  커밋이 완료되었습니다. 어떻게 할까요?"
        echo ""
        echo -e "    ${GREEN}1)${NC} dev에 머지 (git-merge.sh 실행)"
        echo -e "    ${GREEN}2)${NC} dev에 머지 후 브랜치 삭제"
        echo -e "    ${GREEN}3)${NC} 현재 브랜치만 push (머지는 나중에)"
        echo -e "    ${GREEN}4)${NC} 스킵 (push/머지 안함)"
        echo ""
        read -p "  선택 (1/2/3/4): " merge_choice

        case $merge_choice in
            1)
                echo ""
                "$PROJECT_ROOT/git-merge.sh"
                ;;
            2)
                echo ""
                "$PROJECT_ROOT/git-merge.sh" -d
                ;;
            3)
                echo ""
                echo -e "  ${YELLOW}▸${NC} origin/${CURRENT_BRANCH}에 push 중..."
                git push -u origin "$CURRENT_BRANCH"
                echo -e "  ${GREEN}✓${NC} push 완료!"
                echo ""
                echo "  나중에 dev에 머지하려면:"
                echo -e "    ${BLUE}./git-merge.sh${NC}"
                ;;
            *)
                echo ""
                echo -e "  ${DIM}push/머지를 건너뜁니다.${NC}"
                echo ""
                echo "  나중에 작업하려면:"
                echo -e "    ${BLUE}git push -u origin ${CURRENT_BRANCH}${NC}  # push만"
                echo -e "    ${BLUE}./git-merge.sh${NC}                        # dev에 머지"
                ;;
        esac
    fi
}

# ============================================================
# 완료 메시지
# ============================================================
show_summary() {
    echo ""
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${CYAN}  ${GREEN}✓${CYAN} 완료!${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo "  최근 커밋:"
    git log --oneline -3 | sed 's/^/    /'
    echo ""
}

# ============================================================
# 메인 실행
# ============================================================
cd "$PROJECT_ROOT"

check_branch
stage_files
get_jira_ticket
create_commit
run_push_or_merge
show_summary
