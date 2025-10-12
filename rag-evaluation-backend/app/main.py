from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
from app.core.config import settings
from app.api.api_v1.api import api_router

# 导入新增的用户配置模型，确保它们被SQLAlchemy识别
from app.models import user_config  # noqa

# 导入EvalScope路由
from app.api.api_v1.endpoints import evalscope
from app.api.api_v1.endpoints import evalscope_sync
# from app.api.api_v1.endpoints import vlm_eval  # 暂时注释，VLM功能开发中

app = FastAPI(
    title=settings.PROJECT_NAME,
    # openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# 设置CORS
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# 包含API路由
app.include_router(api_router, prefix=settings.API_V1_STR)

# 包含EvalScope路由
app.include_router(
    evalscope.router,
    prefix=f"{settings.API_V1_STR}/evalscope",
    tags=["evalscope"]
)

# 包含EvalScope同步路由
app.include_router(
    evalscope_sync.router,
    prefix=f"{settings.API_V1_STR}/evalscope",
    tags=["evalscope-sync"]
)

# 包含VLM评测路由 (暂时注释)
# app.include_router(
#     vlm_eval.router,
#     prefix=f"{settings.API_V1_STR}/vlm",
#     tags=["vlm-eval"]
# )

# 静态文件挂载
static_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../static'))
app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/health")
def root():
    return {"message": "Welcome to RAG Evaluation System API"}