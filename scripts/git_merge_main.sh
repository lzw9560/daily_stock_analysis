#!/usr/bin/env bash
# ============================================================
# Git 合并脚本：拉取远程 main 分支并合并到当前本地分支
# ============================================================
# 功能：
#   1. 检查工作区是否干净
#   2. 从远程仓库拉取最新代码
#   3. 将 origin/main 合并到当前分支
#   4. 冲突检测：自动 abort 并输出冲突文件列表
# ============================================================

set -euo pipefail

# ---------- 配置 ----------
REMOTE_NAME="${REMOTE_NAME:-origin}"
REMOTE_BRANCH="${REMOTE_BRANCH:-main}"
PROJECT_DIR="${PROJECT_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

log_info()  { echo -e "${CYAN}[INFO]${NC}  $*"; }
log_ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }

# ---------- 工作区状态检查 ----------
check_workspace_clean() {
    log_info "检查工作区状态..."
    cd "$PROJECT_DIR"

    if ! git rev-parse --git-dir > /dev/null 2>&1; then
        log_error "当前目录不是 Git 仓库: $PROJECT_DIR"
        exit 1
    fi

    # 检查未暂存的变更
    local unstaged
    unstaged=$(git diff --name-only 2>/dev/null)
    if [[ -n "$unstaged" ]]; then
        log_error "工作区存在未暂存的变更，请先处理："
        echo "$unstaged" | sed 's/^/      /'
        echo ""
        log_info "建议: git stash 暂存变更后再执行合并"
        exit 1
    fi

    # 检查已暂存但未提交的变更
    local staged
    staged=$(git diff --cached --name-only 2>/dev/null)
    if [[ -n "$staged" ]]; then
        log_error "存在已暂存但未提交的变更，请先处理："
        echo "$staged" | sed 's/^/      /'
        exit 1
    fi

    log_ok "工作区干净，可以执行合并"
}

# ---------- 获取当前分支 ----------
get_current_branch() {
    git rev-parse --abbrev-ref HEAD 2>/dev/null
}

# ---------- 拉取远程代码 ----------
fetch_remote() {
    log_info "从远程仓库拉取最新代码 (${REMOTE_NAME}/${REMOTE_BRANCH})..."
    if git fetch "$REMOTE_NAME" "$REMOTE_BRANCH" 2>&1; then
        log_ok "远程代码拉取成功"
    else
        log_error "拉取远程代码失败，请检查网络或远程仓库配置"
        exit 1
    fi
}

# ---------- 获取冲突文件列表 ----------
get_conflict_files() {
    git diff --name-only --diff-filter=U 2>/dev/null || true
}

# ---------- 执行合并 ----------
do_merge() {
    local current_branch="$1"
    local target="${REMOTE_NAME}/${REMOTE_BRANCH}"

    log_info "当前分支: ${current_branch}"
    log_info "合并目标: ${target}"
    echo ""

    # 检查是否有需要合并的内容
    local behind_count
    behind_count=$(git rev-list --count "${current_branch}..${target}" 2>/dev/null || echo "0")

    if [[ "$behind_count" == "0" ]]; then
        log_ok "当前分支已是最新，无需合并"
        return 0
    fi

    log_info "远程分支领先 ${behind_count} 个提交，开始合并..."

    # 执行合并，使用 --no-edit 避免打开编辑器
    local merge_output
    merge_output=$(git merge --no-edit "$target" 2>&1) && merge_rc=$? || merge_rc=$?

    if [[ $merge_rc -eq 0 ]]; then
        # 合并成功
        log_ok "合并成功！${target} 已合并到 ${current_branch}"
        local merged_commits
        merged_commits=$(git log "${current_branch}@{-1}..${current_branch}" --oneline 2>/dev/null | wc -l | tr -d ' ')
        log_info "合并了 ${merged_commits} 个提交"
        return 0
    else
        # 合并冲突
        log_warn "检测到合并冲突！"

        local conflict_files
        conflict_files=$(get_conflict_files)

        echo ""
        echo -e "${RED}============================================${NC}"
        echo -e "${RED}   合并冲突：需要手动解决${NC}"
        echo -e "${RED}============================================${NC}"
        echo ""

        if [[ -n "$conflict_files" ]]; then
            echo -e "${YELLOW}冲突文件列表:${NC}"
            local i=1
            while IFS= read -r file; do
                echo -e "  ${RED}[${i}]${NC} $file"
                ((i++))
            done <<< "$conflict_files"
            echo ""
        fi

        # 自动 abort 合并，让用户先解决冲突
        log_info "已中止合并（git merge --abort），工作区恢复至合并前状态"
        git merge --abort 2>/dev/null || true

        echo ""
        echo -e "${YELLOW}建议处理步骤:${NC}"
        echo "  1. git fetch ${REMOTE_NAME} ${REMOTE_BRANCH}"
        echo "  2. git merge ${REMOTE_NAME}/${REMOTE_BRANCH}"
        echo "  3. 根据冲突标记手动编辑冲突文件"
        echo "  4. git add <已解决冲突的文件>"
        echo "  5. git commit 完成合并"
        echo ""

        return 1
    fi
}

# ---------- 主流程 ----------
main() {
    echo ""
    echo -e "${CYAN}╔══════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║       Git 合并脚本：origin/main → 当前分支        ║${NC}"
    echo -e "${CYAN}╚══════════════════════════════════════════════════╝${NC}"
    echo ""

    # 1. 工作区状态检查
    check_workspace_clean

    # 2. 获取当前分支
    local current_branch
    current_branch=$(get_current_branch)
    if [[ -z "$current_branch" ]]; then
        log_error "无法获取当前分支名"
        exit 1
    fi

    # 3. 拉取远程代码
    fetch_remote

    # 4. 执行合并
    if do_merge "$current_branch"; then
        echo ""
        echo -e "${GREEN}╔══════════════════════════════════════════════════╗${NC}"
        echo -e "${GREEN}║           合并完成 ✓                             ║${NC}"
        echo -e "${GREEN}╚══════════════════════════════════════════════════╝${NC}"
        echo ""
        exit 0
    else
        echo ""
        echo -e "${RED}╔══════════════════════════════════════════════════╗${NC}"
        echo -e "${RED}║         合并失败，存在冲突 ✗                       ║${NC}"
        echo -e "${RED}╚══════════════════════════════════════════════════╝${NC}"
        echo ""
        exit 1
    fi
}

main "$@"
