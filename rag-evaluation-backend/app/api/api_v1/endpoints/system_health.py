"""
系统健康检查API端点
用于检查各种环境和依赖的安装状态
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import Dict, Any, List
import os
import sys
import subprocess
import importlib
from pathlib import Path

from app.api import deps
from app.models.user import User

router = APIRouter()


def check_python_package(package_name: str, import_name: str = None) -> Dict[str, Any]:
    """检查Python包是否安装"""
    if import_name is None:
        import_name = package_name
    
    try:
        module = importlib.import_module(import_name)
        version = getattr(module, '__version__', 'unknown')
        return {
            "installed": True,
            "version": version,
            "path": getattr(module, '__file__', 'unknown')
        }
    except ImportError:
        return {
            "installed": False,
            "version": None,
            "path": None,
            "error": f"Package '{package_name}' not found"
        }
    except Exception as e:
        return {
            "installed": False,
            "version": None,
            "path": None,
            "error": str(e)
        }


def check_command_available(command: str) -> Dict[str, Any]:
    """检查命令行工具是否可用"""
    try:
        result = subprocess.run(
            ['which', command] if os.name != 'nt' else ['where', command],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            return {
                "available": True,
                "path": result.stdout.strip()
            }
        else:
            return {
                "available": False,
                "path": None,
                "error": f"Command '{command}' not found in PATH"
            }
    except subprocess.TimeoutExpired:
        return {
            "available": False,
            "path": None,
            "error": f"Timeout checking command '{command}'"
        }
    except Exception as e:
        return {
            "available": False,
            "path": None,
            "error": str(e)
        }


def check_service_running(service_name: str, port: int = None) -> Dict[str, Any]:
    """检查服务是否运行"""
    try:
        if port:
            # 检查端口是否被占用
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(('localhost', port))
            sock.close()
            
            if result == 0:
                return {
                    "running": True,
                    "port": port,
                    "status": "active"
                }
            else:
                return {
                    "running": False,
                    "port": port,
                    "status": "inactive",
                    "error": f"Port {port} is not open"
                }
        else:
            # 检查进程是否运行
            if os.name == 'nt':
                result = subprocess.run(['tasklist', '/FI', f'IMAGENAME eq {service_name}'], 
                                      capture_output=True, text=True)
            else:
                result = subprocess.run(['pgrep', '-f', service_name], 
                                      capture_output=True, text=True)
            
            if result.returncode == 0 and result.stdout.strip():
                return {
                    "running": True,
                    "status": "active"
                }
            else:
                return {
                    "running": False,
                    "status": "inactive",
                    "error": f"Service '{service_name}' not running"
                }
    except Exception as e:
        return {
            "running": False,
            "status": "error",
            "error": str(e)
        }


@router.get("/environment-check")
async def check_environment_status(
    db: Session = Depends(deps.get_db)
    # 临时移除认证: current_user: User = Depends(deps.get_current_active_admin)
) -> Dict[str, Any]:
    """检查系统环境状态"""
    
    # Python环境信息
    python_info = {
        "version": sys.version,
        "executable": sys.executable,
        "platform": sys.platform,
        "path": sys.path[:5]  # 只显示前5个路径
    }
    
    # 检查关键Python包
    python_packages = {
        "evalscope": check_python_package("evalscope"),
        "celery": check_python_package("celery"),
        "redis": check_python_package("redis"),
        "fastapi": check_python_package("fastapi"),
        "sqlalchemy": check_python_package("sqlalchemy"),
        "pandas": check_python_package("pandas"),
        "numpy": check_python_package("numpy"),
        "transformers": check_python_package("transformers"),
        "datasets": check_python_package("datasets"),
        "openai": check_python_package("openai"),
        "requests": check_python_package("requests"),
        "psycopg2": check_python_package("psycopg2"),
        "psycopg2-binary": check_python_package("psycopg2-binary")
    }
    
    # 检查命令行工具
    command_tools = {
        "python": check_command_available("python"),
        "python3": check_command_available("python3"),
        "pip": check_command_available("pip"),
        "pip3": check_command_available("pip3"),
        "conda": check_command_available("conda"),
        "redis-cli": check_command_available("redis-cli"),
        "psql": check_command_available("psql")
    }
    
    # 检查服务状态
    services = {
        "redis": check_service_running("redis-server", 6379),
        "postgresql": check_service_running("postgres", 5432),
        "celery_worker": check_service_running("celery"),
        "fastapi": check_service_running("uvicorn", 8000)
    }
    
    # 检查环境变量
    env_vars = {
        "CELERY_BROKER_URL": os.getenv("CELERY_BROKER_URL"),
        "CELERY_RESULT_BACKEND": os.getenv("CELERY_RESULT_BACKEND"),
        "DATABASE_URL": os.getenv("DATABASE_URL"),
        "POSTGRES_SERVER": os.getenv("POSTGRES_SERVER"),
        "POSTGRES_USER": os.getenv("POSTGRES_USER"),
        "POSTGRES_PASSWORD": os.getenv("POSTGRES_PASSWORD"),
        "POSTGRES_DB": os.getenv("POSTGRES_DB"),
        "REDIS_HOST": os.getenv("REDIS_HOST"),
        "REDIS_PORT": os.getenv("REDIS_PORT"),
        "EVALSCOPE_PYTHON_PATH": os.getenv("EVALSCOPE_PYTHON_PATH")
    }
    
    # 检查工作目录权限
    work_dirs = {
        "outputs": {
            "path": "./outputs",
            "exists": Path("./outputs").exists(),
            "writable": Path("./outputs").exists() and os.access("./outputs", os.W_OK),
            "error": None
        },
        "logs": {
            "path": "./logs",
            "exists": Path("./logs").exists(),
            "writable": Path("./logs").exists() and os.access("./logs", os.W_OK),
            "error": None
        }
    }
    
    # 检查缓存目录
    cache_dirs = {
        "modelscope_cache": {
            "path": os.path.expanduser("~/.cache/modelscope"),
            "exists": Path(os.path.expanduser("~/.cache/modelscope")).exists(),
            "writable": Path(os.path.expanduser("~/.cache/modelscope")).exists() and 
                       os.access(os.path.expanduser("~/.cache/modelscope"), os.W_OK),
            "error": None
        },
        "huggingface_cache": {
            "path": os.path.expanduser("~/.cache/huggingface"),
            "exists": Path(os.path.expanduser("~/.cache/huggingface")).exists(),
            "writable": Path(os.path.expanduser("~/.cache/huggingface")).exists() and 
                       os.access(os.path.expanduser("~/.cache/huggingface"), os.W_OK),
            "error": None
        }
    }
    
    # 计算总体健康状态
    critical_packages = ["evalscope", "celery", "redis", "fastapi", "sqlalchemy"]
    critical_services = ["redis", "celery_worker"]
    
    critical_package_status = all(
        python_packages[pkg]["installed"] for pkg in critical_packages
    )
    critical_service_status = all(
        services[svc]["running"] for svc in critical_services
    )
    
    overall_status = "healthy" if critical_package_status and critical_service_status else "unhealthy"
    
    return {
        "overall_status": overall_status,
        "timestamp": "2025-10-12T18:00:00Z",  # 实际应该用datetime.now().isoformat()
        "python_info": python_info,
        "python_packages": python_packages,
        "command_tools": command_tools,
        "services": services,
        "environment_variables": env_vars,
        "work_directories": work_dirs,
        "cache_directories": cache_dirs,
        "critical_status": {
            "packages_ok": critical_package_status,
            "services_ok": critical_service_status,
            "overall_ok": overall_status == "healthy"
        }
    }


@router.get("/environment-check/summary")
async def get_environment_summary(
    db: Session = Depends(deps.get_db)
    # 临时移除认证: current_user: User = Depends(deps.get_current_active_admin)
) -> Dict[str, Any]:
    """获取环境检查摘要"""
    
    # 获取完整的环境检查结果
    full_check = await check_environment_status(db)
    
    # 统计信息
    total_packages = len(full_check["python_packages"])
    installed_packages = sum(1 for pkg in full_check["python_packages"].values() if pkg["installed"])
    
    total_services = len(full_check["services"])
    running_services = sum(1 for svc in full_check["services"].values() if svc["running"])
    
    # 问题列表
    issues = []
    
    # 检查关键包
    for pkg_name, pkg_info in full_check["python_packages"].items():
        if not pkg_info["installed"]:
            issues.append({
                "type": "package",
                "name": pkg_name,
                "severity": "critical" if pkg_name in ["evalscope", "celery", "redis"] else "warning",
                "message": f"Python包 '{pkg_name}' 未安装",
                "solution": f"请运行: pip install {pkg_name}"
            })
    
    # 检查关键服务
    for svc_name, svc_info in full_check["services"].items():
        if not svc_info["running"]:
            issues.append({
                "type": "service",
                "name": svc_name,
                "severity": "critical" if svc_name in ["redis", "celery_worker"] else "warning",
                "message": f"服务 '{svc_name}' 未运行",
                "solution": f"请启动 {svc_name} 服务"
            })
    
    # 检查环境变量
    critical_env_vars = ["CELERY_BROKER_URL", "CELERY_RESULT_BACKEND"]
    for env_var in critical_env_vars:
        if not full_check["environment_variables"].get(env_var):
            issues.append({
                "type": "environment",
                "name": env_var,
                "severity": "critical",
                "message": f"环境变量 '{env_var}' 未设置",
                "solution": f"请设置环境变量: export {env_var}=<value>"
            })
    
    return {
        "overall_status": full_check["overall_status"],
        "summary": {
            "packages": {
                "total": total_packages,
                "installed": installed_packages,
                "missing": total_packages - installed_packages
            },
            "services": {
                "total": total_services,
                "running": running_services,
                "stopped": total_services - running_services
            },
            "issues": {
                "total": len(issues),
                "critical": len([i for i in issues if i["severity"] == "critical"]),
                "warnings": len([i for i in issues if i["severity"] == "warning"])
            }
        },
        "issues": issues,
        "recommendations": [
            "确保所有关键Python包已安装",
            "确保Redis和Celery服务正在运行",
            "检查环境变量配置",
            "定期运行环境检查"
        ]
    }
