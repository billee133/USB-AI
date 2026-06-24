#!/usr/bin/env bash
# =============================================
#  USB-AI — 树莓派一键部署脚本
#  用法: bash pideploy.sh
#        bash pideploy.sh --service  (安装为开机自启服务)
# =============================================

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
NC='\033[0m'

banner() {
    echo -e "${CYAN}"
    echo "============================================"
    echo "  USB-AI -> 树莓派部署"
    echo "============================================"
    echo -e "${NC}"
}

check_pi() {
    # Detect if running on Raspberry Pi
    if [ -f /proc/device-tree/model ]; then
        echo -e "${GREEN}[OK]${NC} 检测到: $(cat /proc/device-tree/model)"
    else
        echo -e "${YELLOW}[!]${NC} 未检测到树莓派硬件，将按通用Linux部署"
    fi

    # Check Python 3
    if command -v python3 &>/dev/null; then
        echo -e "${GREEN}[OK]${NC} Python: $(python3 --version)"
    else
        echo -e "${YELLOW}[!]${NC} Python 3 未安装，正在安装..."
        sudo apt update && sudo apt install -y python3
    fi

    # Check network
    IP=$(hostname -I 2>/dev/null | awk '{print $1}')
    if [ -n "$IP" ]; then
        echo -e "${GREEN}[OK]${NC} 网络IP: $IP"
        echo "           其他设备访问: http://$IP:8820"
    else
        echo -e "${YELLOW}[!]${NC} 未检测到网络，请确保已连接"
        IP="localhost"
    fi
}

install_service() {
    echo ""
    echo "正在安装 systemd 开机自启服务..."

    SERVICE_FILE="/etc/systemd/system/portable-ai.service"
    sudo tee "$SERVICE_FILE" > /dev/null << EOF
[Unit]
Description=USB-AI服务器
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$SCRIPT_DIR
ExecStart=$(which python3) $SCRIPT_DIR/server.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

    sudo systemctl daemon-reload
    sudo systemctl enable portable-ai
    sudo systemctl start portable-ai

    echo -e "${GREEN}[OK]${NC} 服务已安装并启动"
    echo "  查看状态: sudo systemctl status portable-ai"
    echo "  查看日志: sudo journalctl -u portable-ai -f"
    echo "  停止服务: sudo systemctl stop portable-ai"
    echo "  禁用自启: sudo systemctl disable portable-ai"
}

test_server() {
    echo ""
    echo "正在测试服务器..."
    sleep 2
    if curl -s -o /dev/null -w "%{http_code}" http://localhost:8820/ | grep -q 200; then
        echo -e "${GREEN}[OK]${NC} 服务器运行正常!"
        echo "  Pi本地访问:  http://localhost:8820"
        echo "  局域网访问:  http://$IP:8820"
    else
        echo -e "${YELLOW}[!]${NC} 服务器可能未启动，请检查: python3 server.py"
    fi
}

# ============ Main ============
banner
check_pi

echo ""
echo "文件检查..."
for f in server.py index.html; do
    if [ -f "$f" ]; then
        echo -e "  ${GREEN}[OK]${NC} $f"
    else
        echo -e "  ${YELLOW}[MISSING]${NC} $f"
    fi
done

echo ""
echo -e "${CYAN}部署完成!${NC}"
echo ""
echo "启动方式:"
echo "  手动启动:  bash start.sh"
echo "  直接运行:  python3 server.py"
echo "  后台运行:  nohup python3 server.py &"
echo ""

case "${1:-}" in
    --service|-s)
        install_service
        test_server
        ;;
    *)
        echo "可选: bash pideploy.sh --service  (安装为开机自启服务)"
        echo ""
        # Quick start
        read -p "是否现在启动服务器? [Y/n] " answer
        if [[ "$answer" != "n" && "$answer" != "N" ]]; then
            echo ""
            echo "启动服务器 (Ctrl+C 停止)..."
            python3 server.py
        fi
        ;;
esac
