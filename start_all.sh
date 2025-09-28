#!/bin/bash

# 项目根目录
cd "$(dirname "$0")"

function usage() {
  echo "用法："
  echo "  $0 init           # 首次启动，启动数据库、后端、前端"
  echo "  $0 dev frontend   # 只启动前端（开发模式）"
  echo "  $0 dev backend    # 只启动后端（开发模式）"
  echo "  $0 dev all        # 启动前端和后端（不启动数据库）"
  echo "  $0 docker         # 使用Docker启动完整服务栈"
  echo "  $0 stop           # 停止所有服务"
  echo "  $0 status         # 检查服务状态"
  exit 1
}

if [ $# -eq 0 ]; then
  usage
fi

MODE=$1
TARGET=$2

# 端口号变量
BACKEND_PORT=8000
FRONTEND_PORT=5174

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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

# 检查端口是否被占用
function check_port() {
  PORT=$1
  if lsof -ti tcp:$PORT >/dev/null 2>&1; then
    return 0  # 端口被占用
  else
    return 1  # 端口可用
  fi
}

# 等待服务启动
function wait_for_service() {
  local url=$1
  local service_name=$2
  local max_attempts=30
  local attempt=1
  
  print_info "等待 $service_name 启动..."
  
  while [ $attempt -le $max_attempts ]; do
    if curl -s "$url" >/dev/null 2>&1; then
      print_success "$service_name 启动成功！"
      return 0
    fi
    
    printf "."
    sleep 1
    attempt=$((attempt + 1))
  done
  
  echo ""
  print_error "$service_name 启动超时！"
  return 1
}

# 检查Docker是否运行
function check_docker() {
  if ! docker info >/dev/null 2>&1; then
    print_error "Docker 未运行或未安装！"
    return 1
  fi
  return 0
}

# 检查依赖
function check_dependencies() {
  print_info "检查依赖..."
  
  # 检查Node.js
  if ! command -v node >/dev/null 2>&1; then
    print_error "Node.js 未安装！"
    return 1
  fi
  
  # 检查npm
  if ! command -v npm >/dev/null 2>&1; then
    print_error "npm 未安装！"
    return 1
  fi
  
  # 检查Python
  if ! command -v python3 >/dev/null 2>&1; then
    print_error "Python3 未安装！"
    return 1
  fi
  
  print_success "依赖检查通过"
  return 0
}

# 停止所有服务
function stop_all_services() {
  print_info "停止所有服务..."
  
  # 停止开发服务器
  kill_port $BACKEND_PORT
  kill_port $FRONTEND_PORT
  
  # 停止Docker容器
  if check_docker; then
    if [ -f "docker/docker-compose.yml" ]; then
      print_info "停止Docker容器..."
      cd docker && docker compose down
      cd ..
    fi
  fi
  
  print_success "所有服务已停止"
}

# 检查服务状态
function check_status() {
  print_info "检查服务状态..."
  
  echo "=== 端口占用情况 ==="
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
  
  if check_port 5173; then
    print_success "Caddy服务 (端口 5173): 运行中"
  else
    print_warning "Caddy服务 (端口 5173): 未运行"
  fi
  
  echo ""
  echo "=== Docker容器状态 ==="
  if check_docker && [ -f "docker/docker-compose.yml" ]; then
    cd docker && docker compose ps
    cd ..
  else
    print_warning "Docker未运行或docker-compose.yml不存在"
  fi
}

# Docker模式
if [ "$MODE" = "docker" ]; then
  print_info "【Docker模式】启动完整服务栈..."
  
  if ! check_docker; then
    exit 1
  fi
  
  # 停止现有服务
  stop_all_services
  
  # 启动Docker服务
  if [ -f "docker/docker-compose.yml" ]; then
    print_info "启动Docker容器..."
    cd docker && docker compose up -d
    cd ..
    
    # 等待服务启动
    wait_for_service "http://localhost:8000/health" "后端服务"
    wait_for_service "http://localhost:5173" "前端服务"
    
    print_success "所有服务启动成功！"
    echo ""
    echo "=== 访问地址 ==="
    echo "🌐 前端应用: http://localhost:5173"
    echo "🔧 后端API: http://localhost:8000/docs"
    echo "🗄️ 数据库: localhost:5432"
    echo ""
    echo "使用 './start_all.sh status' 检查服务状态"
    echo "使用 './start_all.sh stop' 停止所有服务"
  else
    print_error "找不到 docker/docker-compose.yml 文件！"
    exit 1
  fi
  exit 0
fi

# 停止服务
if [ "$MODE" = "stop" ]; then
  stop_all_services
  exit 0
fi

# 检查状态
if [ "$MODE" = "status" ]; then
  check_status
  exit 0
fi

# 首次启动模式
if [ "$MODE" = "init" ]; then
  print_info "【首次启动】启动数据库、后端、前端..."
  
  if ! check_dependencies; then
    exit 1
  fi
  
  # 启动数据库
  print_info "启动数据库..."
  if [ -f "docker/docker-compose.yml" ]; then
    cd docker && docker compose up -d database
    cd ..
    wait_for_service "postgresql://postgres:postgres@localhost:5432/rag_evaluation" "数据库"
  else
    print_warning "找不到docker-compose.yml，请手动启动数据库"
  fi
  
  # 启动后端
  print_info "启动后端..."
  kill_port $BACKEND_PORT
  cd rag-evaluation-backend && PYTHONPATH=. uvicorn app.main:app --reload --host 0.0.0.0 &
  BACKEND_PID=$!
  cd ..
  
  # 等待后端启动
  wait_for_service "http://localhost:$BACKEND_PORT/health" "后端服务"
  
  # 启动前端
  print_info "启动前端..."
  kill_port $FRONTEND_PORT
  cd rag-evaluation-frontend && npm run dev -- --port $FRONTEND_PORT --host 0.0.0.0 &
  FRONTEND_PID=$!
  cd ..
  
  # 等待前端启动
  wait_for_service "http://localhost:$FRONTEND_PORT" "前端服务"
  
  print_success "全部服务已启动！"
  echo ""
  echo "=== 访问地址 ==="
  echo "🌐 前端应用: http://localhost:$FRONTEND_PORT"
  echo "🔧 后端API: http://localhost:$BACKEND_PORT/docs"
  echo "🗄️ 数据库: localhost:5432"
  echo ""
  echo "进程ID: 后端=$BACKEND_PID, 前端=$FRONTEND_PID"
  echo "使用 Ctrl+C 停止服务或运行 './start_all.sh stop'"
  exit 0
fi

# 开发模式
if [ "$MODE" = "dev" ]; then
  if ! check_dependencies; then
    exit 1
  fi
  
  if [ "$TARGET" = "frontend" ]; then
    kill_port $FRONTEND_PORT
    print_info "【开发模式】只启动前端..."
    cd rag-evaluation-frontend && npm run dev -- --port $FRONTEND_PORT --host 0.0.0.0
    exit 0
  elif [ "$TARGET" = "backend" ]; then
    kill_port $BACKEND_PORT
    print_info "【开发模式】只启动后端..."
    cd rag-evaluation-backend && PYTHONPATH=. uvicorn app.main:app --reload --host 0.0.0.0
    exit 0
  elif [ "$TARGET" = "all" ]; then
    print_info "【开发模式】启动前端和后端（不启动数据库）..."
    
    # 启动后端
    kill_port $BACKEND_PORT
    print_info "启动后端服务..."
    cd rag-evaluation-backend && PYTHONPATH=. uvicorn app.main:app --reload --host 0.0.0.0 &
    BACKEND_PID=$!
    cd ..
    
    # 等待后端启动
    wait_for_service "http://localhost:$BACKEND_PORT/health" "后端服务"
    
    # 启动前端
    kill_port $FRONTEND_PORT
    print_info "启动前端服务..."
    cd rag-evaluation-frontend && npm run dev -- --port $FRONTEND_PORT --host 0.0.0.0 &
    FRONTEND_PID=$!
    cd ..
    
    # 等待前端启动
    wait_for_service "http://localhost:$FRONTEND_PORT" "前端服务"
    
    print_success "前后端已启动！"
    echo ""
    echo "=== 访问地址 ==="
    echo "🌐 前端应用: http://localhost:$FRONTEND_PORT"
    echo "🔧 后端API: http://localhost:$BACKEND_PORT/docs"
    echo ""
    echo "进程ID: 后端=$BACKEND_PID, 前端=$FRONTEND_PID"
    echo "使用 Ctrl+C 停止服务或运行 './start_all.sh stop'"
    
    # 等待用户中断
    trap 'print_info "正在停止服务..."; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0' INT
    wait
    exit 0
  else
    usage
  fi
fi

usage 