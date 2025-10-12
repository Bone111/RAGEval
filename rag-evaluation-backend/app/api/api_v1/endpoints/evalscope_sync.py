"""
EvalScope同步评测API - 简化版，立即可用
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import subprocess
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any

from app.api import deps
from app.schemas import evalscope as schemas
from app.services.evalscope_service import EvalScopeService
from app.services.unified_model_service import UnifiedModelService
from app.models.evalscope_task import EvalScopeResult
from app.models.model_config import ModelConfig
from app.models.user import User

router = APIRouter()

@router.get("/models", response_model=List[Dict[str, Any]])
async def get_user_models(
    current_user: User = Depends(deps.get_optional_current_user),
    db: Session = Depends(deps.get_db)
):
    """
    获取用户配置的模型列表
    支持可选认证：
    - 已认证：返回用户个性化的模型列表
    - 未认证：返回公共可用的模型列表
    """
    # 使用统一模型服务
    unified_service = UnifiedModelService(db)
    
    if current_user:
        # 已认证用户：从数据库查询用户的模型配置
        print(f"INFO: 用户 {current_user.name} 请求模型列表")
        models = db.query(ModelConfig).filter(
            ModelConfig.user_id == str(current_user.id),
            ModelConfig.is_active == True
        ).all()
        print(f"INFO: 查询到用户的 {len(models)} 个模型配置")
    else:
        # 未认证用户：查询所有公共可用的模型配置
        print("INFO: 未认证用户请求模型列表，返回公共模型")
        models = db.query(ModelConfig).filter(
            ModelConfig.is_active == True
        ).limit(20).all()
        print(f"INFO: 查询到 {len(models)} 个公共模型配置")
    
    # 转换为前端需要的格式
    model_list = []
    for model in models:
        model_info = {
            "id": model.model_id,
            "name": model.model_name or model.model_id,
            "display_name": model.model_name or model.model_id,
            "type": model.model_type,
            "rating": 2500,  # 默认rating
            "wins": 0,
            "losses": 0,
            "draws": 0,
            "total_battles": 0,
            "win_rate": 0.0,
            "recent_form": [],
            "tier": "Bronze",
            "config": {
                "model_id": model.model_id,
                "model_name": model.model_name,
                "model_type": model.model_type,
                "model_path": model.model_path,
                "api_url": model.api_url,
                "api_key": model.api_key,
                "model_args": model.model_args or {},
                "generation_config": model.generation_config or {}
            }
        }
        model_list.append(model_info)
    
    # 如果没有找到ModelConfig中的模型，尝试从统一模型管理获取
    if not model_list:
        print("INFO: ModelConfig中没有模型，尝试从统一模型管理获取")
        
        if current_user:
            # 已认证用户：获取用户的统一管理模型
            unified_models = await unified_service.get_all_available_models(str(current_user.id))
        else:
            # 未认证用户：获取公共模型
            unified_models = await unified_service.get_public_models()
        
        # 转换统一模型格式为evalscope所需格式
        for model in unified_models:
            model_info = {
                "id": model.get('id'),
                "name": model.get('name'),
                "display_name": model.get('display_name'),
                "type": model.get('model_type'),
                "rating": model.get('quality_rating', 2500) if model.get('quality_rating') else 2500,
                "wins": 0,
                "losses": 0,
                "draws": 0,
                "total_battles": 0,
                "win_rate": 0.0,
                "recent_form": [],
                "tier": "Bronze",
                "config": model.get('config', {})
            }
            model_list.append(model_info)
        
        print(f"INFO: 从统一模型管理获取到 {len(model_list)} 个模型")
    
    # 如果还是没有模型，返回空列表
    if not model_list:
        print("WARN: 数据库中没有任何可用的模型配置，返回空列表")
        print("提示：请在【API配置管理】或【大模型管理】中配置模型，然后点击【同步现有模型】按钮")
    
    return model_list

@router.post("/tasks/sync", response_model=schemas.TaskResponse)
async def create_and_run_task_sync(
    task_data: schemas.TaskCreate,
    db: Session = Depends(deps.get_db)
):
    """同步创建并执行评测任务（简化版）
    
    创建任务后立即返回任务对象，然后在后台线程中执行评测
    """
    
    # 验证数据集
    if not task_data.datasets:
        raise HTTPException(status_code=400, detail="至少选择一个数据集")
    
    # 临时使用固定用户ID
    test_user_id = "5bddb026-0a9d-4a87-8958-d97860566dc9"
    
    # 创建任务（带模型验证）
    try:
        task = await EvalScopeService.create_task(
            db=db,
            user_id=test_user_id,
            task_data=task_data
        )
    except ValueError as e:
        # 模型验证失败，返回400错误
        print(f"❌ 任务创建失败: {str(e)}")
        raise HTTPException(
            status_code=400, 
            detail=str(e)
        )
    except Exception as e:
        # 其他错误
        print(f"❌ 任务创建失败（未知错误）: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"任务创建失败: {str(e)}"
        )
    
    # 立即更新任务状态为running
    task.status = 'running'
    task.started_at = datetime.now(timezone.utc)
    task.progress = 10
    db.commit()
    
    # 刷新task对象以确保所有字段都是最新的
    db.refresh(task)
    
    print(f"✅ 任务 {task.id} 创建成功，准备在后台执行评测")
    
    # 启动后台线程执行评测
    import threading
    eval_thread = threading.Thread(
        target=run_eval_in_background,
        args=(task.id, task_data),
        daemon=True
    )
    eval_thread.start()
    
    # 立即返回任务对象（包含ID），前端可以跳转到详情页面
    return task


def run_eval_in_background(task_id: int, task_data: schemas.TaskCreate):
    """在后台线程中执行评测"""
    from app.core.database import SessionLocal
    
    db = SessionLocal()
    try:
        # 获取任务
        from app.models.evalscope_task import EvalScopeTask
        task = db.query(EvalScopeTask).filter(EvalScopeTask.id == task_id).first()
        if not task:
            print(f"❌ 任务 {task_id} 不存在")
            return
        
        print(f"🚀 后台线程开始执行任务 {task_id}")
        
        # 更新进度
        task.progress = 20
        db.commit()
        
        # 构建命令 (使用conda环境)
        # 从环境变量获取Python路径，如果未设置则使用当前Python
        conda_python = os.getenv('EVALSCOPE_PYTHON_PATH', 'python')
        
        # 修复模型ID格式问题
        model_id = task.model_id
        print(f"DEBUG: 原始模型ID: {task.model_id}, eval_type: {task.eval_type}")
        
        # 对于API模型，需要特殊处理
        if task.eval_type == 'openai_api':
            # API模型直接使用原始ID
            if model_id and model_id not in ['model', '']:
                print(f"INFO: 使用API模型: {model_id}")
            else:
                raise ValueError(f"API模型ID无效 ({task.model_id})。请在【大模型管理】中正确配置模型。")
        else:
            # 本地模型需要namespace/name格式
            if not model_id or model_id == "model" or model_id.strip() == "":
                # 尝试从extra_metadata中获取用户配置的模型名
                if task.extra_metadata and task.extra_metadata.get('user_model_config'):
                    user_config = task.extra_metadata['user_model_config']
                    if user_config.get('model_name'):
                        model_id = user_config['model_name']
                        print(f"INFO: 从用户配置获取模型名: {model_id}")
                    else:
                        raise ValueError(f"用户配置中没有模型名。请在【大模型管理】中完善模型配置。")
                else:
                    raise ValueError(f"本地模型ID无效 ({task.model_id})。请在【大模型管理】中正确配置模型。")
        
        cmd = [
            conda_python, '-m', 'evalscope.cli.cli', 'eval',
            '--model', model_id,
            '--datasets'
        ] + task.datasets
        
        # 添加limit参数
        if task_data.limit:
            cmd.extend(['--limit', str(task_data.limit)])
        
        # 添加eval_type参数
        if task.eval_type:
            cmd.extend(['--eval-type', task.eval_type])
            
        # 如果是API模型，添加API配置
        if task.eval_type == 'openai_api':
            # 优先从task.extra_metadata获取配置(数据库中保存的)
            user_config = None
            if task.extra_metadata and task.extra_metadata.get('user_model_config'):
                user_config = task.extra_metadata['user_model_config']
                print(f"DEBUG: 从task.extra_metadata获取命令行API配置")
            # 如果extra_metadata中没有,尝试从task_data获取(向后兼容)
            elif hasattr(task_data, 'user_model_config') and task_data.user_model_config:
                user_config = task_data.user_model_config
                print(f"DEBUG: 从task_data获取命令行API配置")
            
            if user_config:
                # 添加API URL (注意：配置中使用的是base_url，而命令行参数是--api-url)
                api_url = user_config.get('api_url') or user_config.get('base_url')
                if api_url:
                    cmd.extend(['--api-url', api_url])
                    print(f"DEBUG: 添加命令行参数 --api-url {api_url}")
                
                # 添加API密钥
                if user_config.get('api_key'):
                    cmd.extend(['--api-key', user_config['api_key']])
                    print(f"DEBUG: 添加命令行参数 --api-key ***")
            else:
                print(f"WARNING: 未找到云端模型配置")
        
        print(f"执行命令: {' '.join(cmd)}")
        
        # 使用subprocess命令行方式（更稳定）
        # 准备环境变量
        env = os.environ.copy()
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,  
                timeout=600,
                env=env,
                cwd=os.getcwd()  # 确保工作目录正确
            )
            
            print(f"命令执行完成，返回码: {result.returncode}")
            
            if result.returncode != 0:
                print(f"错误输出: {result.stderr}")
                task.status = 'failed'
                task.error_message = f"评测执行失败:\n{result.stderr}"
                task.completed_at = datetime.now(timezone.utc)
                db.commit()
                return  # 后台线程，无需返回值
            
            print(f"标准输出: {result.stdout[:500]}...")  # 打印前500字符
            
            # 解析文本结果
            stdout_lines = result.stdout.split('\n')
            results_parsed = parse_stdout_for_results(stdout_lines)
            
            print(f"解析到 {len(results_parsed)} 个结果")
            
        except subprocess.TimeoutExpired:
            print("命令执行超时")
            task.status = 'failed'
            task.error_message = "评测任务超时（超过10分钟）"
            task.completed_at = datetime.now(timezone.utc)
            db.commit()
            return  # 后台线程，无需返回值
            
        except Exception as e:
            print(f"命令执行异常: {e}")
            import traceback
            traceback.print_exc()
            task.status = 'failed'
            task.error_message = f"评测执行异常: {str(e)}"
            task.completed_at = datetime.now(timezone.utc)
            db.commit()
            return  # 后台线程，无需返回值
        
        # 保存结果到数据库
        for result_data in results_parsed:
            eval_result = EvalScopeResult(
                task_id=task.id,
                benchmark=result_data['benchmark'],
                metric_name=result_data['metric_name'],
                metric_value=result_data['metric_value'],
                category=result_data.get('category', 'default'),
                subset_name=result_data.get('subset_name', 'main'),
                num_samples=result_data.get('num_samples'),
                raw_results=result_data
            )
            db.add(eval_result)
        
        # 任务完成
        task.status = 'completed'
        task.progress = 100
        task.completed_at = datetime.now(timezone.utc)
        db.commit()
        
        print(f"✅ 任务 {task.id} 执行成功")
        
    except Exception as e:
        print(f"❌ 任务执行出错: {e}")
        import traceback
        traceback.print_exc()
        task.status = 'failed'
        task.error_message = f"任务执行异常: {str(e)}"
        task.completed_at = datetime.now(timezone.utc)
        db.commit()
    finally:
        # 关闭数据库连接
        db.close()
        print(f"🔒 任务 {task_id} 的数据库连接已关闭")


def parse_stdout_for_results(stdout_lines):
    """解析evalscope输出结果"""
    results = []
    
    # 查找结果表格 - 新的格式匹配
    in_table = False
    for line in stdout_lines:
        line = line.strip()
        
        # 检测表格头
        if '| Model' in line and '| Dataset' in line and '| Score' in line:
            in_table = True
            continue
        
        # 检测表格分隔符
        if in_table and line.startswith('+') and '=' in line:
            continue
        
        # 解析数据行
        if in_table and line.startswith('|') and not line.startswith('+='):
            try:
                # 解析格式：| Model | Dataset | Metric | Subset | Num | Score | Cat.0 |
                parts = [p.strip() for p in line.split('|') if p.strip()]
                
                if len(parts) >= 6:  # 至少6列
                    model_name = parts[0] 
                    dataset = parts[1]
                    metric = parts[2]
                    subset = parts[3] if len(parts) > 3 else 'main'
                    num_samples = parts[4] if len(parts) > 4 else '1'
                    score = parts[5] if len(parts) > 5 else '0'
                    
                    # 转换数据类型
                    try:
                        score_float = float(score)
                    except:
                        score_float = None
                    
                    try:
                        num_int = int(num_samples)
                    except:
                        num_int = None
                    
                    results.append({
                        'benchmark': dataset,
                        'metric_name': metric,
                        'metric_value': score_float,
                        'category': 'default',
                        'subset_name': subset,
                        'num_samples': num_int,
                        'raw_results': {
                            'model': model_name,
                            'parsed_from': 'stdout_table'
                        }
                    })
                    
                    print(f"解析到结果: {dataset} - {metric} = {score}")
            except Exception as e:
                print(f"解析表格行失败: {line} -> {e}")
    
    print(f"总共解析到 {len(results)} 个结果")
    return results
