#!/bin/bash

# 简化版启动脚本 - 只启动前后端
cd "$(dirname "$0")"

# 端口号变量
BACKEND_PORT=8000
FRONTEND_PORT=5173
REDIS_PORT=6379

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 打印带颜色的消息
function print_info() {
  echo -e "${BLUE}[INFO]${NC} $1"
}

function print_success() {
  echo -e "${GREEN}[SUCCESS]${NC} $1"
}

function print_warning() {
  echo -e "${YELLOW}[WARNING]${NC} $1"
}

function print_error() {
  echo -e "${RED}[ERROR]${NC} $1"
}

# 杀掉指定端口的进程
function kill_port() {
  PORT=$1
  PID=$(lsof -ti tcp:$PORT 2>/dev/null)
  if [ -n "$PID" ]; then
    print_warning "端口 $PORT 已被进程 $PID 占用，自动kill..."
    kill -9 $PID
    sleep 1
  fi
}

function usage() {
  echo "用法："
  echo "  $0 start         # 启动前后端服务和Celery worker"
  echo "  $0 stop          # 停止所有服务"
  echo "  $0 status        # 检查服务状态"
  echo "  $0 backend       # 只启动后端"
  echo "  $0 frontend      # 只启动前端"
  echo "  $0 celery        # 只启动Celery worker"
  exit 1
}

# 检查端口是否被占用
function check_port() {
  PORT=$1
  if lsof -ti tcp:$PORT >/dev/null 2>&1; then
    return 0  # 端口被占用
  else
    return 1  # 端口可用
  fi
}

# 停止所有服务
function stop_services() {
  print_info "停止所有服务..."
  kill_port $BACKEND_PORT
  kill_port $FRONTEND_PORT
  
  # 停止Celery worker
  print_info "停止Celery worker..."
  pkill -f "celery.*evalscope_tasks_optimized.*worker" || true
  sleep 2
  
  print_success "所有服务已停止"
}

# 检查服务状态
function check_status() {
  print_info "检查服务状态..."
  
  if check_port $BACKEND_PORT; then
    print_success "后端服务 (端口 $BACKEND_PORT): 运行中"
  else
    print_warning "后端服务 (端口 $BACKEND_PORT): 未运行"
  fi
  
  if check_port $FRONTEND_PORT; then
    print_success "前端服务 (端口 $FRONTEND_PORT): 运行中"
  else
    print_warning "前端服务 (端口 $FRONTEND_PORT): 未运行"
  fi
  
  if check_port $REDIS_PORT; then
    print_success "Redis服务 (端口 $REDIS_PORT): 运行中"
  else
    print_warning "Redis服务 (端口 $REDIS_PORT): 未运行"
  fi
  
  # 检查Celery worker
  if ps aux | grep -E "celery.*evalscope_tasks_optimized.*worker" | grep -v grep > /dev/null; then
    print_success "Celery worker: 运行中"
  else
    print_warning "Celery worker: 未运行"
  fi
}

# 启动后端服务
function start_backend() {
  print_info "启动后端服务..."
  kill_port $BACKEND_PORT
  
  cd rag-evaluation-backend
  if [ ! -f "app/main.py" ]; then
    print_error "找不到 app/main.py 文件！"
    return 1
  fi
  
  print_info "启动命令: uvicorn app.main:app --reload --host 0.0.0.0 --port $BACKEND_PORT"
  # 加载.env文件中的环境变量
  if [ -f ".env" ]; then
    print_info "加载.env文件中的环境变量..."
    set -a  # 自动导出变量
    source .env
    set +a  # 关闭自动导出
  fi
  PYTHONPATH=. uvicorn app.main:app --reload --host 0.0.0.0 --port $BACKEND_PORT &
  BACKEND_PID=$!
  cd ..
  
  # 等待后端启动
  sleep 3
  if check_port $BACKEND_PORT; then
    print_success "后端服务启动成功！PID: $BACKEND_PID"
    echo "🔧 后端API文档: http://localhost:$BACKEND_PORT/docs"
    return 0
  else
    print_error "后端服务启动失败！"
    return 1
  fi
}

# 启动前端服务
function start_frontend() {
  print_info "启动前端服务..."
  kill_port $FRONTEND_PORT
  
  cd rag-evaluation-frontend
  if [ ! -f "package.json" ]; then
    print_error "找不到 package.json 文件！"
    return 1
  fi
  
  print_info "启动命令: npm run dev -- --port $FRONTEND_PORT --host 0.0.0.0"
  npm run dev -- --port $FRONTEND_PORT --host 0.0.0.0 &
  FRONTEND_PID=$!
  cd ..
  
  # 等待前端启动
  sleep 5
  if check_port $FRONTEND_PORT; then
    print_success "前端服务启动成功！PID: $FRONTEND_PID"
    echo "🌐 前端应用: http://localhost:$FRONTEND_PORT"
    return 0
  else
    print_error "前端服务启动失败！"
    return 1
  fi
}

# 启动Celery worker
function start_celery() {
  print_info "启动Celery worker..."
  
  # 检查Redis是否运行
  if ! check_port $REDIS_PORT; then
    print_error "Redis服务未运行，请先启动Redis服务！"
    print_info "启动Redis: brew services start redis"
    return 1
  fi
  
  # 停止已有的Celery worker
  pkill -f "celery.*evalscope_tasks_optimized.*worker" || true
  sleep 2
  
  cd rag-evaluation-backend
  if [ ! -f "app/tasks/evalscope_tasks_optimized.py" ]; then
    print_error "找不到 Celery任务模块！"
    return 1
  fi
  
  # 设置环境变量
  export CELERY_BROKER_URL=redis://localhost:6379/0
  export CELERY_RESULT_BACKEND=redis://localhost:6379/0
  
  print_info "启动命令: celery -A app.tasks.evalscope_tasks_optimized worker --loglevel=info --concurrency=2"
  celery -A app.tasks.evalscope_tasks_optimized worker --loglevel=info --concurrency=2 &
  CELERY_PID=$!
  cd ..
  
  # 等待Celery启动
  sleep 5
  if ps aux | grep -E "celery.*evalscope_tasks_optimized.*worker" | grep -v grep > /dev/null; then
    print_success "Celery worker启动成功！PID: $CELERY_PID"
    return 0
  else
    print_error "Celery worker启动失败！"
    return 1
  fi
}

# 参数处理
if [ $# -eq 0 ]; then
  usage
fi

MODE=$1

case $MODE in
  "start")
    print_info "启动前后端服务和Celery worker..."
    
    # 启动后端
    if start_backend; then
      # 启动Celery worker
      if start_celery; then
        # 启动前端
        if start_frontend; then
          print_success "所有服务启动完成！"
          echo ""
          echo "=== 服务访问地址 ==="
          echo "🌐 前端应用: http://localhost:$FRONTEND_PORT"
          echo "🔧 后端API: http://localhost:$BACKEND_PORT/docs"
          echo "⚡ Celery worker: 运行中"
          echo ""
          echo "使用 '$0 status' 检查服务状态"
          echo "使用 '$0 stop' 停止所有服务"
          echo "使用 Ctrl+C 或关闭终端来停止服务"
        else
          print_error "前端启动失败，停止其他服务"
          kill_port $BACKEND_PORT
          pkill -f "celery.*evalscope_tasks_optimized.*worker" || true
          exit 1
        fi
      else
        print_error "Celery worker启动失败，停止后端服务"
        kill_port $BACKEND_PORT
        exit 1
      fi
    else
      print_error "后端启动失败"
      exit 1
    fi
    ;;
    
  "stop")
    stop_services
    ;;
    
  "status")
    check_status
    ;;
    
  "backend")
    start_backend
    echo "后端服务已启动，按 Ctrl+C 停止"
    wait
    ;;
    
  "frontend")
    start_frontend  
    echo "前端服务已启动，按 Ctrl+C 停止"
    wait
    ;;
    
  "celery")
    start_celery
    echo "Celery worker已启动，按 Ctrl+C 停止"
    wait
    ;;
    
  *)
    usage
    ;;
esac
