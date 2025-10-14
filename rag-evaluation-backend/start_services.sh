#!/bin/bash
# RAGEval 服务启动脚本
# 使用conda环境启动后端和Celery worker

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}🚀 RAGEval 服务启动脚本${NC}"
echo "使用conda环境: rag—eval"
echo ""

# 进入项目目录
cd "$(dirname "$0")"

# 清理现有进程
echo -e "${YELLOW}🧹 清理现有进程...${NC}"
pkill -f "uvicorn.*app.main" || true
pkill -f "celery.*evalscope_tasks" || true
sleep 2

# 清理环境变量
unset EVALSCOPE_PYTHON_PATH

# 激活conda环境并启动后端
echo -e "${YELLOW}🚀 启动后端服务...${NC}"
conda activate rag—eval && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!

# 等待后端启动
echo "等待后端服务启动..."
for i in {1..30}; do
    if curl -s http://localhost:8000/health >/dev/null 2>&1; then
        echo -e "${GREEN}✅ 后端服务启动成功 (PID: $BACKEND_PID)${NC}"
        break
    fi
    sleep 1
done

# 启动Celery Worker
echo -e "${YELLOW}🚀 启动Celery Worker...${NC}"
conda activate rag—eval && celery -A app.tasks.evalscope_tasks worker --loglevel=info --concurrency=2 &
CELERY_PID=$!

# 等待Worker启动
sleep 3

# 检查服务状态
echo ""
echo -e "${BLUE}📊 服务状态${NC}"
echo "================================================"

if curl -s http://localhost:8000/health >/dev/null 2>&1; then
    echo -e "${GREEN}✅ 后端服务: 运行中 (http://localhost:8000)${NC}"
else
    echo -e "${RED}❌ 后端服务: 未运行${NC}"
fi

if ps aux | grep -E "celery.*evalscope_tasks.*worker" | grep -v grep >/dev/null; then
    echo -e "${GREEN}✅ Celery Worker: 运行中${NC}"
else
    echo -e "${RED}❌ Celery Worker: 未运行${NC}"
fi

echo ""
echo -e "${BLUE}🌐 访问地址${NC}"
echo "API文档: http://localhost:8000/docs"
echo "健康检查: http://localhost:8000/health"
echo ""
echo "进程ID: 后端=$BACKEND_PID, Celery=$CELERY_PID"
echo "停止服务: pkill -f 'uvicorn.*app.main' && pkill -f 'celery.*evalscope_tasks'"
