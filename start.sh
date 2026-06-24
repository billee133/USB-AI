#!/usr/bin/env bash
# =============================================
#  USB-AI — Linux/Mac 启动脚本
#  用法: bash start.sh          (服务器模式)
#        bash start.sh direct   (浏览器直连)
#        bash start.sh --help   (帮助)
# =============================================

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

PORT=8082
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

banner() {
    echo -e "${CYAN}"
    echo "╔══════════════════════════════════════════╗"
    echo "║     🤖 USB-AI                  ║"
    echo "╠══════════════════════════════════════════╣"
    echo "║  平台: $(uname -s) / $(uname -m)        ║"
    echo "╚══════════════════════════════════════════╝"
    echo -e "${NC}"
}

open_browser() {
    local url="$1"
    if command -v xdg-open &>/dev/null; then
        xdg-open "$url" &>/dev/null &
    elif command -v open &>/dev/null; then
        open "$url" &>/dev/null &
    elif command -v gnome-open &>/dev/null; then
        gnome-open "$url" &>/dev/null &
    else
        echo -e "${YELLOW}请手动打开浏览器访问: ${url}${NC}"
    fi
}

detect_python() {
    # Check for Python 3 (built into every Linux/Mac)
    if command -v python3 &>/dev/null; then
        echo "python3"
    elif command -v python &>/dev/null; then
        # On some systems python = python3
        local ver=$(python --version 2>&1)
        if [[ "$ver" == *"Python 3"* ]]; then
            echo "python"
        else
            echo ""
        fi
    else
        echo ""
    fi
}

run_server() {
    local py=$(detect_python)
    if [[ -z "$py" ]]; then
        echo -e "${RED}[错误] 未找到 Python 3${NC}"
        echo ""
        echo "  Ubuntu/Debian:  sudo apt install python3"
        echo "  CentOS/RHEL:    sudo yum install python3"
        echo "  Arch:           sudo pacman -S python"
        echo "  Mac:            brew install python3"
        echo ""
        echo "  或使用浏览器直连模式: bash start.sh direct"
        exit 1
    fi

    echo -e "${GREEN}[运行]${NC} Python: $($py --version)"
    echo -e "${GREEN}[运行]${NC} 服务器: http://localhost:${PORT}"
    echo -e "${GREEN}[运行]${NC} 按 Ctrl+C 停止"
    echo ""

    # Auto-open browser after short delay
    sleep 1 && open_browser "http://localhost:${PORT}" &
    exec "$py" server.py
}

run_direct() {
    banner
    echo -e "${YELLOW}[模式]${NC} 浏览器直连模式"
    echo ""
    echo "正在打开 index.html ..."
    echo ""
    echo "注意：联网搜索功能在 file:// 协议下可能受 CORS 限制"
    echo "      如遇到搜索失败，请使用服务器模式: bash start.sh"
    echo ""

    # Try to open in browser
    local html_path="file://${SCRIPT_DIR}/index.html"
    open_browser "$html_path"
}

show_help() {
    echo "USB-AI — Linux/Mac 使用说明"
    echo ""
    echo "用法:"
    echo "  bash start.sh             启动服务器代理模式（推荐）"
    echo "  bash start.sh direct      浏览器直连模式"
    echo "  bash start.sh --help      显示此帮助"
    echo ""
    echo "前提:"
    echo "  服务器模式需要 Python 3（Ubuntu 已内置）"
    echo "  直连模式仅需要浏览器"
    echo ""
    echo "快速开始:"
    echo "  cd USB-AI"
    echo "  bash start.sh"
    echo "  → 浏览器自动打开 → 点击 ⚙ 填入 API Key → 开始对话"
}

# ============ Main ============
banner

case "${1:-server}" in
    direct|--direct|-d)
        run_direct
        ;;
    --help|-h|help)
        show_help
        ;;
    server|*)
        echo -e "${GREEN}[模式]${NC} 服务器代理模式（完整功能）"
        echo ""
        run_server
        ;;
esac
