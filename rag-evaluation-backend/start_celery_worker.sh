#!/bin/bash
# Celery Worker 启动脚本
# 配置环境变量并启动Worker

echo "🚀 启动 Celery Worker..."

# 设置EvalScope Python环境路径（生产环境可修改此路径）
export EVALSCOPE_PYTHON_PATH="/Users/Bone/miniconda3/envs/evalscope/bin/python"

# 进入项目目录
cd "$(dirname "$0")"

# 停止已有的Worker进程
echo "停止已有的Worker进程..."
pkill -f "celery.*evalscope_tasks_real.*worker" || true

# 等待进程完全停止
sleep 2

# 启动新的Worker
echo "启动新的Worker进程..."
nohup celery -A app.tasks.evalscope_tasks_real worker \
    --loglevel=info \
    --concurrency=2 \
    > celery_worker.log 2>&1 &

# 等待启动
sleep 3

# 检查是否启动成功
if ps aux | grep -E "celery.*evalscope_tasks_real.*worker" | grep -v grep > /dev/null; then
    echo "✅ Celery Worker 启动成功"
    echo "📝 日志文件: celery_worker.log"
    echo "🔍 查看日志: tail -f celery_worker.log"
else
    echo "❌ Celery Worker 启动失败，请查看日志"
    tail -50 celery_worker.log
    exit 1
fi

