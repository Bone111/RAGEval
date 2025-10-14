from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
from app.core.config import settings
from app.api.api_v1.api import api_router

# 导入新增的用户配置模型，确保它们被SQLAlchemy识别
from app.models import user_config  # noqa

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

# 包含API路由（已包含所有子路由，包括 evalscope 和 evalscope_sync）
app.include_router(api_router, prefix=settings.API_V1_STR)

# 静态文件挂载
static_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../static'))
app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/health")
def root():
    return {"message": "Welcome to RAG Evaluation System API"}