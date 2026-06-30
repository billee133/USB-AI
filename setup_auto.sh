#!/usr/bin/env bash
# USB-AI — 桌面自动化依赖安装 (Mac/Linux)
echo "============================================"
echo "  USB-AI — 安装桌面自动化依赖"
echo "============================================"
echo ""
echo "将安装: pyautogui pillow"
echo ""
read -p "是否继续? [Y/n] " answer
if [[ "$answer" == "n" || "$answer" == "N" ]]; then
    echo "已跳过"
    exit 0
fi

# On Linux, xclip may be needed for clipboard operations
if [[ "$(uname)" == "Linux" ]]; then
    echo "[提示] Linux 下可能需要 xclip: sudo apt install xclip"
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WHEEL_DIR="$SCRIPT_DIR/runtime/auto-deps"

# Check for offline wheels first
if ls "$WHEEL_DIR"/*.whl 2>/dev/null | head -1 > /dev/null; then
    echo "[检测] 发现本地 whl 包，离线安装..."
    python3 -m pip install "$WHEEL_DIR"/*.whl --quiet --no-index && \
        echo "[OK] 安装成功！在 USB-AI 设置中开启桌面自动化即可使用" || \
        echo "[错误] 安装失败"
else
    python3 -m pip install pyautogui pillow --quiet && \
        echo "[OK] 安装成功！在 USB-AI 设置中开启桌面自动化即可使用" || \
        echo "[错误] 安装失败，请手动执行: pip install pyautogui pillow"
fi
