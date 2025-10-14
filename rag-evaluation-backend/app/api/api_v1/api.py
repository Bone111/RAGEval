from fastapi import APIRouter

from app.api.api_v1.endpoints import (
    auth, users, datasets, projects, 
    questions,  # 重新启用 - llama_index依赖已修复
    rag_answers, dataset_questions, performance, accuracy, admin, rag_proxy, 
    llamaindex_split,  # 重新启用 - llama_index依赖已修复
    mineru_convert, llm_proxy, user_configs, 
    evalscope, reports, comparison,  # 添加EvalScope相关路由和报告生成（只使用Celery版）
    model_management,  # 新增大模型统一管理路由
    unified_models,  # 统一模型服务API
    system_health  # 系统健康检查API
)

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["认证"])
api_router.include_router(users.router, prefix="/users", tags=["用户管理"])
api_router.include_router(datasets.router, prefix="/datasets", tags=["数据集管理"])
api_router.include_router(projects.router, prefix="/projects", tags=["项目管理"])
api_router.include_router(questions.router, prefix="/questions", tags=["问题管理"])  # 重新启用
api_router.include_router(rag_answers.router, prefix="/rag-answers", tags=["RAG回答"])
api_router.include_router(performance.router, prefix="/performance", tags=["性能测试"])
api_router.include_router(dataset_questions.router, prefix="/datasets-questions", tags=["dataset-questions"])
api_router.include_router(accuracy.router, prefix="/accuracy", tags=["accuracy"])
api_router.include_router(admin.router, prefix="/admin", tags=["管理员"])
api_router.include_router(rag_proxy.router, prefix="/rag", tags=["RAG代理"])
api_router.include_router(llamaindex_split.router, tags=["LlamaIndex分块"])  # 重新启用
api_router.include_router(mineru_convert.router, prefix="/mineru", tags=["mineru"])
api_router.include_router(llm_proxy.router, prefix="/llm", tags=["大模型转发"])
api_router.include_router(user_configs.router, prefix="/user-configs", tags=["用户配置管理"])

# 添加EvalScope相关路由
# 只使用 Celery 版本（功能完整，生产级）
api_router.include_router(evalscope.router, prefix="/evalscope", tags=["EvalScope评测"])

# 简化同步版本已停用 - 统一使用 Celery 版本
# 前端请调用: POST /api/v1/evalscope/tasks (而不是 /tasks/sync)

api_router.include_router(reports.router, prefix="/reports", tags=["报告生成"])
api_router.include_router(comparison.router, prefix="/comparison", tags=["模型对比分析"])

# 添加大模型统一管理路由
api_router.include_router(model_management.router, prefix="/model-management", tags=["大模型统一管理"])

# 添加统一模型服务路由
api_router.include_router(unified_models.router, prefix="/unified-models", tags=["统一模型服务"])

# 添加系统健康检查路由
api_router.include_router(system_health.router, prefix="/system", tags=["系统健康检查"])

@api_router.get("/health")
def health_check():
    return {"status": "健康"}

# 在这里添加更多路由
# 例如:
# from app.api.api_v1.endpoints import users, projects, evaluations
# api_router.include_router(users.router, prefix="/users", tags=["users"])
# api_router.include_router(projects.router, prefix="/projects", tags=["projects"])
# api_router.include_router(evaluations.router, prefix="/evaluations", tags=["evaluations"])