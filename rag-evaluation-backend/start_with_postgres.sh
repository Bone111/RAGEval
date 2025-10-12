#!/bin/bash
# 使用PostgreSQL数据库启动后端服务

cd "$(dirname "$0")"

export DATABASE_URL="postgresql://postgres:postgres@localhost:5432/rag_evaluation"
export POSTGRES_SERVER="localhost"
export POSTGRES_USER="postgres"
export POSTGRES_PASSWORD="postgres"
export POSTGRES_DB="rag_evaluation"

# Celery配置
export CELERY_BROKER_URL="redis://localhost:6379/0"
export CELERY_RESULT_BACKEND="redis://localhost:6379/0"

echo "================================================"
echo "启动后端服务 - 使用PostgreSQL数据库"
echo "================================================"
echo "数据库: $DATABASE_URL"
echo ""

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

