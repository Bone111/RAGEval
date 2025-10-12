#!/bin/bash
export CELERY_BROKER_URL=redis://localhost:6379/0
export CELERY_RESULT_BACKEND=redis://localhost:6379/0
export EVALSCOPE_PYTHON_PATH=/Users/Bone/miniconda3/envs/evalscope/bin/python
cd /Users/Bone/Documents/工作/10月/代码测试区/RAGEval/rag-evaluation-backend
celery -A app.tasks.evalscope_tasks_optimized worker --loglevel=info --concurrency=2
