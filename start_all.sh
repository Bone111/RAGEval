#!/bin/bash

# 项目根目录
cd "$(dirname "$0")"

function usage() {
  echo "用法："
  echo "  $0 init           # 首次启动，启动数据库、后端、前端"
  echo "  $0 dev frontend   # 只启动前端（开发模式）"
  echo "  $0 dev backend    # 只启动后端（开发模式）"
  echo "  $0 dev all        # 启动前端和后端（不启动数据库）"
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

# 杀掉指定端口的进程
function kill_port() {
  PORT=$1
  PID=$(lsof -ti tcp:$PORT)
  if [ -n "$PID" ]; then
    echo "端口 $PORT 已被进程 $PID 占用，自动kill..."
    kill -9 $PID
  fi
}

if [ "$MODE" = "init" ]; then
  echo "【首次启动】启动数据库、后端、前端..."
  echo "启动数据库..."
  cd rag-evaluation-backend/app/docker && docker-compose up -d
  if [ $? -ne 0 ]; then
    echo "[错误] docker-compose 启动失败，请检查 docker 配置。"
    exit 2
  fi
  cd ../../../..
  echo "启动后端..."
  kill_port $BACKEND_PORT
  cd rag-evaluation-backend && PYTHONPATH=. uvicorn app.main:app --reload &
  cd ..
  echo "启动前端..."
  kill_port $FRONTEND_PORT
  cd rag-evaluation-frontend && npm run dev -- --port $FRONTEND_PORT &
  cd ..
  echo "全部服务已启动。"
  echo "访问前端: http://localhost:$FRONTEND_PORT"
  echo "访问后端: http://localhost:$BACKEND_PORT/docs"
  exit 0
fi

if [ "$MODE" = "dev" ]; then
  if [ "$TARGET" = "frontend" ]; then
    kill_port $FRONTEND_PORT
    echo "【开发模式】只启动前端..."
    cd rag-evaluation-frontend && npm run dev -- --port $FRONTEND_PORT
    exit 0
  elif [ "$TARGET" = "backend" ]; then
    kill_port $BACKEND_PORT
    echo "【开发模式】只启动后端..."
    cd rag-evaluation-backend && PYTHONPATH=. uvicorn app.main:app --reload
    exit 0
  elif [ "$TARGET" = "all" ]; then
    kill_port $BACKEND_PORT
    echo "【开发模式】启动前端和后端（不启动数据库）..."
    cd rag-evaluation-backend && PYTHONPATH=. uvicorn app.main:app --reload &
    cd ..
    kill_port $FRONTEND_PORT
    cd rag-evaluation-frontend && npm run dev -- --port $FRONTEND_PORT &
    cd ..
    echo "前后端已启动。"
    echo "访问前端: http://localhost:$FRONTEND_PORT"
    echo "访问后端: http://localhost:$BACKEND_PORT/docs"
    exit 0
  else
    usage
  fi
fi

usage 