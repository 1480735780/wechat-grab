#!/bin/bash
# ============================================
# 微信公众号监控助手 - 一键安装脚本
# ============================================
# 使用方法:
#   curl -fsSL https://raw.githubusercontent.com/1480735780/wechat-grab/main/install.sh | bash
# ============================================

set -e

# 颜色常量
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# 项目信息
REPO_URL="https://github.com/1480735780/wechat-grab.git"
INSTALL_DIR="$HOME/wechat-grab"

echo ""
echo -e "${CYAN}${BOLD}"
echo " ____    _    _ __  _ __   __ _ _   _ "
echo "|  _ \  | |  | |  _ \| '_ \ / _\` | | | |"
echo "| | | | | |__| | |_) | | | | (_| | |_| |"
echo "|_| |_| |____/|____/|_| |_|\__,_|\__, |"
echo "                                 |___/"
echo "  微信公众号监控助手 v1.0"
echo -e "${NC}"

echo -e "${BOLD}正在安装微信公众号监控助手...${NC}"
echo ""

# 检查 Python
check_python() {
    if command -v python3 &>/dev/null; then
        PYTHON="python3"
        PYTHON_VERSION=$($PYTHON --version 2>&1)
        echo -e "  ${GREEN}✓${NC} Python 已安装: $PYTHON_VERSION"
    elif command -v python &>/dev/null; then
        PYTHON="python"
        PYTHON_VERSION=$($PYTHON --version 2>&1)
        echo -e "  ${GREEN}✓${NC} Python 已安装: $PYTHON_VERSION"
    else
        echo -e "  ${RED}✗${NC} 未找到 Python，请先安装 Python 3.11+"
        exit 1
    fi
}

# 检查 Git
check_git() {
    if command -v git &>/dev/null; then
        echo -e "  ${GREEN}✓${NC} Git 已安装"
    else
        echo -e "  ${RED}✗${NC} 未找到 Git，请先安装 Git"
        exit 1
    fi
}

# 克隆项目
clone_repo() {
    if [ -d "$INSTALL_DIR" ]; then
        echo -e "  ${YELLOW}⚠${NC} 目录已存在: $INSTALL_DIR"
        read -p "  是否重新克隆？(y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            rm -rf "$INSTALL_DIR"
        else
            echo -e "  ${GREEN}使用现有目录${NC}"
            return
        fi
    fi

    echo -e "  正在克隆项目..."
    git clone "$REPO_URL" "$INSTALL_DIR"
    echo -e "  ${GREEN}✓${NC} 克隆完成"
}

# 安装 Python 依赖
install_deps() {
    cd "$INSTALL_DIR"
    echo -e "  正在安装 Python 依赖..."
    $PYTHON -m pip install --upgrade pip
    $PYTHON -m pip install -r requirements.txt
    echo -e "  ${GREEN}✓${NC} 依赖安装完成"
}

# 创建必要的目录
create_dirs() {
    mkdir -p "$INSTALL_DIR/output"
    mkdir -p "$INSTALL_DIR/data"
    mkdir -p "$INSTALL_DIR/logs"
    echo -e "  ${GREEN}✓${NC} 目录创建完成"
}

# 创建启动脚本
create_launcher() {
    LAUNCHER="$INSTALL_DIR/wechat-monitor"
    cat > "$LAUNCHER" << 'EOF'
#!/bin/bash
# 微信公众号监控助手启动脚本
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 加载环境变量
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

# 执行 CLI 工具
python cli.py "$@"
EOF
    chmod +x "$LAUNCHER"
    echo -e "  ${GREEN}✓${NC} 启动脚本已创建"
}

# 主流程
echo -e "${BOLD}【步骤 1/5】检查环境${NC}"
check_python
check_git
echo ""

echo -e "${BOLD}【步骤 2/5】克隆项目${NC}"
clone_repo
echo ""

echo -e "${BOLD}【步骤 3/5】安装依赖${NC}"
install_deps
echo ""

echo -e "${BOLD}【步骤 4/5】创建目录${NC}"
create_dirs
echo ""

echo -e "${BOLD}【步骤 5/5】创建启动脚本${NC}"
create_launcher
echo ""

# 完成
echo -e "${GREEN}${BOLD}安装完成！${NC}"
echo ""
echo -e "安装目录: ${CYAN}$INSTALL_DIR${NC}"
echo ""
echo -e "${BOLD}下一步:${NC}"
echo -e "  1. 进入目录: ${YELLOW}cd $INSTALL_DIR${NC}"
echo -e "  2. 运行配置向导: ${YELLOW}./wechat-monitor setup${NC}"
echo -e "  3. 开始监控: ${YELLOW}./wechat-monitor daemon${NC}"
echo ""
echo -e "可用命令:"
echo -e "  ${YELLOW}./wechat-monitor setup${NC}    - 交互式配置向导"
echo -e "  ${YELLOW}./wechat-monitor run${NC}      - 运行一次同步（测试）"
echo -e "  ${YELLOW}./wechat-monitor daemon${NC}   - 启动守护进程"
echo -e "  ${YELLOW}./wechat-monitor status${NC}   - 查看运行状态"
echo -e "  ${YELLOW}./wechat-monitor logs${NC}     - 查看实时日志"
echo -e "  ${YELLOW}./wechat-monitor stop${NC}     - 停止守护进程"
echo -e "  ${YELLOW}./wechat-monitor deploy${NC}   - 引导 Docker 部署"
echo ""
echo -e "${CYAN}享受自动抓取公众号的乐趣吧！${NC}"
