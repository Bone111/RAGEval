#!/bin/bash

echo "🚀 启动EvalScope真实评测服务"
echo "================================================"
echo ""

# 进入项目目录
cd "$(dirname "$0")"
PROJECT_DIR=$(pwd)

# 检查Redis
echo "📍 检查Redis服务..."
if ! redis-cli ping > /dev/null 2>&1; then
    echo "⚠️ Redis未运行，正在启动..."
    brew services start redis
    sleep 2
    if redis-cli ping > /dev/null 2>&1; then
        echo "✅ Redis启动成功"
    else
        echo "❌ Redis启动失败"
        exit 1
    fi
else
    echo "✅ Redis运行正常"
fi

# 检查conda环境
echo ""
echo "📍 检查Python环境..."
if python3 -c "import evalscope" 2>/dev/null; then
    echo "✅ evalscope 可用"
else
    echo "❌ evalscope 未安装"
    echo "请先在conda环境中安装: pip install evalscope"
    exit 1
fi

echo ""
echo "🎯 启动服务..."
echo ""

# 创建启动脚本
cat > temp_start_all.sh << 'EOF'
#!/bin/bash

# 启动后端
echo "启动后端服务..."
cd rag-evaluation-backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

# 启动Celery Worker  
echo "启动Celery Worker..."
celery -A app.tasks.evalscope_tasks_real worker --loglevel=info --concurrency=2 &
CELERY_PID=$!

# 启动前端
echo "启动前端服务..."
cd ../rag-evaluation-frontend
npm run dev &
FRONTEND_PID=$!

echo ""
echo "✅ 所有服务已启动!"
echo "后端: PID $BACKEND_PID"
echo "Celery: PID $CELERY_PID" 
echo "前端: PID $FRONTEND_PID"
echo ""
echo "🌐 访问地址:"
echo "前端: http://localhost:5173"
echo "后端: http://localhost:8000/docs"
echo ""
echo "💡 停止服务:"
echo "pkill -f uvicorn"
echo "pkill -f celery"
echo "pkill -f vite"

# 等待用户中断
wait
EOF

chmod +x temp_start_all.sh
./temp_start_all.sh

# 清理
rm temp_start_all.sh


