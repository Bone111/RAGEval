#!/bin/bash

# RAGEval 开发环境设置脚本
# 自动安装和配置开发环境

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo -e "${BLUE}🔧 RAGEval 开发环境设置${NC}"

# 检查操作系统
if [[ "$OSTYPE" == "darwin"* ]]; then
    OS="macos"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    OS="linux"
else
    echo -e "${RED}❌ 不支持的操作系统: $OSTYPE${NC}"
    exit 1
fi

echo "检测到操作系统: $OS"

# 安装pyenv (如果未安装)
install_pyenv() {
    if command -v pyenv &> /dev/null; then
        echo -e "${GREEN}✅ pyenv已安装${NC}"
        return
    fi
    
    echo -e "${YELLOW}📋 安装pyenv...${NC}"
    
    if [[ "$OS" == "macos" ]]; then
        # macOS安装
        if command -v brew &> /dev/null; then
            brew install pyenv
        else
            echo "请先安装Homebrew: https://brew.sh/"
            exit 1
        fi
    elif [[ "$OS" == "linux" ]]; then
        # Linux安装
        curl https://pyenv.run | bash
    fi
    
    # 配置shell
    echo 'export PYENV_ROOT="$HOME/.pyenv"' >> ~/.bashrc
    echo 'command -v pyenv >/dev/null || export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.bashrc
    echo 'eval "$(pyenv init -)"' >> ~/.bashrc
    
    echo -e "${GREEN}✅ pyenv安装完成${NC}"
    echo "请重新启动终端或运行: source ~/.bashrc"
}

# 安装Python 3.11
install_python() {
    echo -e "${YELLOW}📋 安装Python 3.11...${NC}"
    
    # 检查Python 3.11是否已安装
    if pyenv versions | grep -q "3.11"; then
        echo -e "${GREEN}✅ Python 3.11已安装${NC}"
    else
        echo "正在安装Python 3.11..."
        pyenv install 3.11.10
        echo -e "${GREEN}✅ Python 3.11.10安装完成${NC}"
    fi
    
    # 设置项目Python版本
    cd "$PROJECT_ROOT"
    pyenv local 3.11.10
    echo -e "${GREEN}✅ 项目Python版本设置为3.11.10${NC}"
}

# 创建虚拟环境
create_venv() {
    echo -e "${YELLOW}📋 创建虚拟环境...${NC}"
    
    cd "$PROJECT_ROOT"
    
    if [ -d ".venv" ]; then
        echo -e "${YELLOW}⚠️  虚拟环境已存在，正在删除...${NC}"
        rm -rf .venv
    fi
    
    python -m venv .venv
    source .venv/bin/activate
    
    # 升级pip
    pip install --upgrade pip
    
    echo -e "${GREEN}✅ 虚拟环境创建完成${NC}"
}

# 安装依赖
install_dependencies() {
    echo -e "${YELLOW}📋 安装项目依赖...${NC}"
    
    cd "$PROJECT_ROOT"
    source .venv/bin/activate
    
    # 安装后端依赖
    if [ -f "rag-evaluation-backend/requirements.txt" ]; then
        pip install -r rag-evaluation-backend/requirements.txt
    fi
    
    # 安装开发依赖
    pip install black isort pytest pytest-cov
    
    echo -e "${GREEN}✅ 依赖安装完成${NC}"
}

# 安装Redis (如果未安装)
install_redis() {
    echo -e "${YELLOW}📋 检查Redis...${NC}"
    
    if command -v redis-server &> /dev/null; then
        echo -e "${GREEN}✅ Redis已安装${NC}"
    else
        echo -e "${YELLOW}⚠️  Redis未安装${NC}"
        
        if [[ "$OS" == "macos" ]]; then
            if command -v brew &> /dev/null; then
                brew install redis
                brew services start redis
            else
                echo "请手动安装Redis: https://redis.io/docs/getting-started/installation/"
            fi
        elif [[ "$OS" == "linux" ]]; then
            sudo apt-get update
            sudo apt-get install redis-server
            sudo systemctl start redis-server
            sudo systemctl enable redis-server
        fi
        
        echo -e "${GREEN}✅ Redis安装完成${NC}"
    fi
}

# 创建环境配置文件
create_env_config() {
    echo -e "${YELLOW}📋 创建环境配置文件...${NC}"
    
    cd "$PROJECT_ROOT/rag-evaluation-backend"
    
    if [ ! -f ".env" ]; then
        cat > .env << EOF
# 数据库配置
DATABASE_URL=sqlite:///./app.db

# Celery配置
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# JWT配置
SECRET_KEY=your-secret-key-here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# 日志级别
LOG_LEVEL=INFO

# 开发模式
DEBUG=True
EOF
        echo -e "${GREEN}✅ .env文件创建完成${NC}"
    else
        echo -e "${GREEN}✅ .env文件已存在${NC}"
    fi
}

# 验证安装
verify_installation() {
    echo -e "${YELLOW}📋 验证安装...${NC}"
    
    cd "$PROJECT_ROOT"
    source .venv/bin/activate
    
    # 检查Python版本
    PYTHON_VERSION=$(python --version 2>&1 | grep -oE '[0-9]+\.[0-9]+' | head -1)
    if [[ "$PYTHON_VERSION" == "3.11"* ]]; then
        echo -e "${GREEN}✅ Python版本正确: $PYTHON_VERSION${NC}"
    else
        echo -e "${RED}❌ Python版本错误: $PYTHON_VERSION${NC}"
        exit 1
    fi
    
    # 检查关键依赖
    python -c "import fastapi, celery, sqlalchemy; print('✅ 关键依赖检查通过')"
    
    # 检查Redis连接
    python -c "import redis; r = redis.Redis(); r.ping(); print('✅ Redis连接正常')" 2>/dev/null || echo -e "${YELLOW}⚠️  Redis连接失败，请确保Redis服务正在运行${NC}"
    
    echo -e "${GREEN}✅ 安装验证完成${NC}"
}

# 显示使用说明
show_usage() {
    echo -e "${BLUE}🎉 开发环境设置完成！${NC}"
    echo ""
    echo -e "${YELLOW}使用方法:${NC}"
    echo "1. 启动后端服务:"
    echo "   ./start_backend.sh"
    echo ""
    echo "2. 或者手动启动:"
    echo "   source .venv/bin/activate"
    echo "   cd rag-evaluation-backend"
    echo "   python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"
    echo ""
    echo "3. 启动Celery Worker (可选):"
    echo "   source .venv/bin/activate"
    echo "   cd rag-evaluation-backend"
    echo "   celery -A app.tasks.evalscope_tasks_real worker --loglevel=info"
    echo ""
    echo -e "${YELLOW}服务地址:${NC}"
    echo "后端API: http://localhost:8000"
    echo "API文档: http://localhost:8000/docs"
    echo ""
    echo -e "${YELLOW}注意事项:${NC}"
    echo "- 确保Redis服务正在运行"
    echo "- 首次运行可能需要下载模型，请耐心等待"
    echo "- 如需使用PostgreSQL，请修改.env文件中的DATABASE_URL"
}

# 主函数
main() {
    install_pyenv
    install_python
    create_venv
    install_dependencies
    install_redis
    create_env_config
    verify_installation
    show_usage
}

# 运行主函数
main "$@"
