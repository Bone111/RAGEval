import secrets
from typing import Any, Dict, List, Optional, Union
import os
import socket

from pydantic import AnyHttpUrl, field_validator, EmailStr, Field, ConfigDict, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic.networks import PostgresDsn

# 检测是否在Docker容器中运行
def is_running_in_docker():
    try:
        with open('/proc/self/cgroup', 'r') as f:
            return 'docker' in f.read()
    except:
        return False

class Settings(BaseSettings):
    PROJECT_NAME: str = "RAG Evaluation System"
    API_V1_STR: str = "/api/v1"
    
    # JWT设置 - 让认证永久有效
    SECRET_KEY: str = os.getenv("SECRET_KEY", "rag-evaluation-secret-key-2024-permanent")  # 固定密钥
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 365  # 🔥 设置1年过期，基本永久有效
    
    # 数据库设置
    # 优先读取 DATABASE_URL（常见命名），否则用 POSTGRES_* 组装
    POSTGRES_SERVER: str = os.getenv("POSTGRES_SERVER", "localhost")
    POSTGRES_PORT: int = int(os.getenv("POSTGRES_PORT", "5432"))
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "postgres")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "postgres")
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "rag_evaluation")
    # 兼容常见变量名 DATABASE_URL
    DATABASE_URL: Optional[str] = os.getenv("DATABASE_URL")
    # 修改为支持SQLite和PostgreSQL
    DATABASE_URI: Optional[str] = None

    @field_validator("DATABASE_URI", mode="before")
    @classmethod
    def assemble_db_connection(cls, v: Optional[str], info) -> Any:
        # 如果显式提供（或通过 DATABASE_URL 注入）则直接返回
        if isinstance(v, str) and v:
            return v

        values = info.data
        # 优先使用 DATABASE_URL（如果设置）
        database_url_env = values.get("DATABASE_URL")
        if isinstance(database_url_env, str) and database_url_env:
            return database_url_env

        # 默认使用PostgreSQL（推荐生产环境使用）
        # 检查是否有PostgreSQL配置
        postgres_server = values.get("POSTGRES_SERVER")
        
        # 强制使用PostgreSQL（移除SQLite fallback）
        if postgres_server:
            db_name = values.get('POSTGRES_DB', 'rag_evaluation')
            host = postgres_server
            port = values.get("POSTGRES_PORT", 5432)
            user = values.get("POSTGRES_USER", "postgres")
            password = values.get("POSTGRES_PASSWORD", "postgres")
            
            postgres_dsn = PostgresDsn.build(
                scheme="postgresql",
                username=user,
                password=password,
                host=f"{host}:{port}" if port else host,
                path=f"{db_name}"
            )
            print(f"✅ 使用PostgreSQL数据库: {user}@{host}:{port}/{db_name}")
            return str(postgres_dsn)
        else:
            # PostgreSQL未配置时报错（不再fallback到SQLite）
            raise ValueError(
                "❌ PostgreSQL未配置！请在.env中配置:\n"
                "  POSTGRES_SERVER=localhost\n"
                "  POSTGRES_USER=postgres\n"
                "  POSTGRES_PASSWORD=your_password\n"
                "  POSTGRES_DB=rag_evaluation\n"
                "或设置 DATABASE_URL=postgresql://..."
            )
    
    # Redis设置（建议通过环境变量配置）
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    
    # Celery设置
    CELERY_BROKER_URL: str = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
    CELERY_RESULT_BACKEND: str = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")
    
    # CORS设置
    BACKEND_CORS_ORIGINS: List[AnyHttpUrl] = []

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> Union[List[str], str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)

    # OpenAI API 配置
    OPENAI_API_KEY: Optional[str] = None
    DEFAULT_MODEL: Optional[str] = None  # 不设置默认模型，要求用户在【大模型管理】中配置
    
    # Anthropic API 配置
    ANTHROPIC_API_KEY: Optional[str] = None
    
    # 初始管理员用户（建议通过环境变量配置）
    FIRST_ADMIN_EMAIL: EmailStr = os.getenv("FIRST_ADMIN_EMAIL", "admin@example.com")
    FIRST_ADMIN_PASSWORD: str = os.getenv("FIRST_ADMIN_PASSWORD", "adminpassword")
    
    # 认证设置
    DISABLE_AUTH: bool = os.getenv("DISABLE_AUTH", "false").lower() == "true"
    
    # EvalScope性能优化配置
    # 小任务阈值：样本数小于此值时使用快速路径（禁用进度监控）
    EVALSCOPE_SMALL_TASK_THRESHOLD: int = int(os.getenv("EVALSCOPE_SMALL_TASK_THRESHOLD", "100"))
    # 进度监控间隔（秒）- 小任务
    EVALSCOPE_PROGRESS_INTERVAL_SMALL: int = int(os.getenv("EVALSCOPE_PROGRESS_INTERVAL_SMALL", "10"))
    # 进度监控间隔（秒）- 大任务
    EVALSCOPE_PROGRESS_INTERVAL_LARGE: int = int(os.getenv("EVALSCOPE_PROGRESS_INTERVAL_LARGE", "2"))
    # 数据库更新最小间隔（秒）- 避免频繁提交
    EVALSCOPE_DB_UPDATE_INTERVAL: float = float(os.getenv("EVALSCOPE_DB_UPDATE_INTERVAL", "1.0"))
    # WebSocket超时（秒）- 避免阻塞
    EVALSCOPE_WEBSOCKET_TIMEOUT: float = float(os.getenv("EVALSCOPE_WEBSOCKET_TIMEOUT", "0.5"))
    # 是否启用Python API优先（False则直接用命令行，更快）
    EVALSCOPE_PREFER_PYTHON_API: bool = os.getenv("EVALSCOPE_PREFER_PYTHON_API", "false").lower() == "true"

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="allow"
    )

settings = Settings()

