#!/bin/bash

# RAGEval 后端启动脚本
# 确保使用正确的Python版本和虚拟环境

set -e  # 遇到错误立即退出

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 项目根目录
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$PROJECT_ROOT/rag-evaluation-backend"

echo -e "${BLUE}🚀 RAGEval 后端启动脚本${NC}"
echo "项目根目录: $PROJECT_ROOT"
echo "后端目录: $BACKEND_DIR"

# 检查Python版本
check_python_version() {
    echo -e "${YELLOW}📋 检查Python版本...${NC}"
    
    # 优先使用pyenv管理的Python
    if command -v pyenv &> /dev/null; then
        echo "检测到pyenv，使用pyenv管理的Python"
        if [ -f "$PROJECT_ROOT/.python-version" ]; then
            PYTHON_VERSION=$(cat "$PROJECT_ROOT/.python-version")
            echo "项目指定Python版本: $PYTHON_VERSION"
            export PATH="$HOME/.pyenv/bin:$PATH"
            eval "$(pyenv init -)"
            pyenv shell "$PYTHON_VERSION"
        fi
    fi
    
    # 检查Python版本
    PYTHON_CMD=""
    for cmd in python3.11 python3 python; do
        if command -v "$cmd" &> /dev/null; then
            VERSION=$($cmd --version 2>&1 | grep -oE '[0-9]+\.[0-9]+' | head -1)
            if [[ "$VERSION" == "3.11"* ]]; then
                PYTHON_CMD="$cmd"
                echo -e "${GREEN}✅ 找到Python 3.11: $cmd (版本: $VERSION)${NC}"
                break
            fi
        fi
    done
    
    if [ -z "$PYTHON_CMD" ]; then
        echo -e "${RED}❌ 未找到Python 3.11${NC}"
        echo "请安装Python 3.11或使用pyenv管理Python版本"
        echo "安装pyenv: https://github.com/pyenv/pyenv#installation"
        exit 1
    fi
    
    # 验证Python路径
    PYTHON_PATH=$(which "$PYTHON_CMD")
    echo "使用Python: $PYTHON_PATH"
}

# 检查虚拟环境
check_venv() {
    echo -e "${YELLOW}📋 检查虚拟环境...${NC}"
    
    VENV_DIR="$PROJECT_ROOT/.venv"
    
    if [ ! -d "$VENV_DIR" ]; then
        echo -e "${YELLOW}⚠️  虚拟环境不存在，正在创建...${NC}"
        "$PYTHON_CMD" -m venv "$VENV_DIR"
        echo -e "${GREEN}✅ 虚拟环境创建完成${NC}"
    fi
    
    # 激活虚拟环境
    source "$VENV_DIR/bin/activate"
    echo -e "${GREEN}✅ 虚拟环境已激活${NC}"
    
    # 验证虚拟环境中的Python版本
    VENV_PYTHON_VERSION=$(python --version 2>&1 | grep -oE '[0-9]+\.[0-9]+' | head -1)
    echo "虚拟环境Python版本: $VENV_PYTHON_VERSION"
    
    if [[ ! "$VENV_PYTHON_VERSION" == "3.11"* ]]; then
        echo -e "${RED}❌ 虚拟环境Python版本不正确${NC}"
        echo "请删除虚拟环境并重新创建:"
        echo "rm -rf $VENV_DIR"
        echo "然后重新运行此脚本"
        exit 1
    fi
}

# 安装依赖
install_dependencies() {
    echo -e "${YELLOW}📋 检查并安装依赖...${NC}"
    
    # 检查requirements.txt是否存在
    if [ -f "$BACKEND_DIR/requirements.txt" ]; then
        echo "安装requirements.txt中的依赖..."
        pip install -r "$BACKEND_DIR/requirements.txt"
    else
        echo "requirements.txt不存在，使用pyproject.toml安装依赖..."
        pip install -e .
    fi
    
    echo -e "${GREEN}✅ 依赖安装完成${NC}"
}

# 检查环境变量
check_env() {
    echo -e "${YELLOW}📋 检查环境变量...${NC}"
    
    # 检查.env文件
    if [ -f "$BACKEND_DIR/.env" ]; then
        echo "加载.env文件..."
        export $(cat "$BACKEND_DIR/.env" | grep -v '^#' | xargs)
    fi
    
    # 设置默认环境变量
    export DATABASE_URL="${DATABASE_URL:-sqlite:///./app.db}"
    export CELERY_BROKER_URL="${CELERY_BROKER_URL:-redis://localhost:6379/0}"
    export CELERY_RESULT_BACKEND="${CELERY_RESULT_BACKEND:-redis://localhost:6379/0}"
    
    echo "DATABASE_URL: $DATABASE_URL"
    echo "CELERY_BROKER_URL: $CELERY_BROKER_URL"
    echo "CELERY_RESULT_BACKEND: $CELERY_RESULT_BACKEND"
}

# 启动服务
start_service() {
    echo -e "${YELLOW}📋 启动后端服务...${NC}"
    
    cd "$BACKEND_DIR"
    
    # 检查端口是否被占用
    if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null ; then
        echo -e "${YELLOW}⚠️  端口8000已被占用，正在停止现有服务...${NC}"
        pkill -f "uvicorn.*rag-evaluation-backend" || true
        sleep 2
    fi
    
    echo -e "${GREEN}🚀 启动FastAPI服务...${NC}"
    echo "服务地址: http://localhost:8000"
    echo "API文档: http://localhost:8000/docs"
    echo "按 Ctrl+C 停止服务"
    echo ""
    
    # 启动服务
    python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
}

# 主函数
main() {
    check_python_version
    check_venv
    install_dependencies
    check_env
    start_service
}

# 运行主函数
main "$@"
