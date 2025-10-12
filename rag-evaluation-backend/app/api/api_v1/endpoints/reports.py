"""
报告生成API端点
"""
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from pydantic import BaseModel
import os
import logging

from app.api import deps
from app.services.report_service import ReportService
from app.models.evalscope_task import EvalScopeTask

router = APIRouter()
logger = logging.getLogger(__name__)

class ReportGenerateRequest(BaseModel):
    """报告生成请求"""
    task_ids: List[str]
    config: Dict[str, Any]

@router.post("/generate")
async def generate_report(
    request: ReportGenerateRequest,
    db: Session = Depends(deps.get_db)
):
    """生成评测报告"""
    try:
        # 验证任务ID
        if not request.task_ids:
            raise HTTPException(status_code=400, detail="至少选择一个评测任务")
        
        # 验证任务是否存在且已完成
        valid_tasks = []
        for task_id in request.task_ids:
            task = db.query(EvalScopeTask).filter(
                EvalScopeTask.id == task_id,
                EvalScopeTask.status == 'completed'
            ).first()
            
            if not task:
                logger.warning(f"任务 {task_id} 不存在或未完成")
                continue
            
            valid_tasks.append(task_id)
        
        if not valid_tasks:
            raise HTTPException(status_code=400, detail="没有找到有效的已完成评测任务")
        
        # 生成报告
        report_service = ReportService()
        
        try:
            filepath, filename = report_service.generate_report(
                task_ids=valid_tasks,
                report_config=request.config,
                db_session=db
            )
            
            # 读取文件内容
            with open(filepath, 'rb') as f:
                file_content = f.read()
            
            # 确定MIME类型
            format_type = request.config.get('format', 'pdf').lower()
            if format_type == 'pdf':
                media_type = 'application/pdf'
            elif format_type == 'excel':
                media_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            elif format_type == 'html':
                media_type = 'text/html'
            else:
                media_type = 'application/octet-stream'
            
            # 清理临时文件
            report_service.cleanup_temp_files()
            
            # 返回文件
            return Response(
                content=file_content,
                media_type=media_type,
                headers={
                    "Content-Disposition": f"attachment; filename={filename}",
                    "Content-Length": str(len(file_content))
                }
            )
            
        except Exception as e:
            # 确保清理临时文件
            report_service.cleanup_temp_files()
            raise e
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"生成报告失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"生成报告失败: {str(e)}")

@router.get("/tasks/completed")
async def get_completed_tasks(
    db: Session = Depends(deps.get_db)
):
    """获取已完成的评测任务列表"""
    try:
        # 临时使用固定用户ID
        test_user_id = "5bddb026-0a9d-4a87-8958-d97860566dc9"
        
        # 查询已完成的任务
        tasks = db.query(EvalScopeTask).filter(
            EvalScopeTask.user_id == test_user_id,
            EvalScopeTask.status == 'completed'
        ).order_by(EvalScopeTask.completed_at.desc()).all()
        
        # 转换为前端需要的格式
        task_list = []
        for task in tasks:
            task_info = {
                "id": task.id,
                "task_name": task.task_name,
                "model_id": task.model_id,
                "datasets": task.datasets,
                "status": task.status,
                "created_at": task.created_at.isoformat() if task.created_at else None,
                "completed_at": task.completed_at.isoformat() if task.completed_at else None,
                "progress": task.progress
            }
            task_list.append(task_info)
        
        return {
            "tasks": task_list,
            "total": len(task_list)
        }
        
    except Exception as e:
        logger.error(f"获取已完成任务失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取任务列表失败: {str(e)}")

@router.get("/formats")
async def get_supported_formats():
    """获取支持的报告格式"""
    try:
        report_service = ReportService()
        formats = report_service.get_supported_formats()
        
        return {
            "formats": formats,
            "details": {
                "pdf": {
                    "name": "PDF文档",
                    "description": "适合打印和分享的PDF格式报告",
                    "supported": True
                },
                "excel": {
                    "name": "Excel表格",
                    "description": "可编辑的Excel格式报告，支持数据筛选和分析",
                    "supported": True
                },
                "html": {
                    "name": "HTML网页",
                    "description": "可在浏览器中查看的HTML格式报告",
                    "supported": True
                }
            }
        }
        
    except Exception as e:
        logger.error(f"获取支持格式失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取支持格式失败: {str(e)}")

@router.post("/preview")
async def preview_report(
    request: ReportGenerateRequest,
    db: Session = Depends(deps.get_db)
):
    """预览报告内容"""
    try:
        # 验证任务ID
        if not request.task_ids:
            raise HTTPException(status_code=400, detail="至少选择一个评测任务")
        
        # 验证任务是否存在且已完成
        valid_tasks = []
        for task_id in request.task_ids:
            task = db.query(EvalScopeTask).filter(
                EvalScopeTask.id == task_id,
                EvalScopeTask.status == 'completed'
            ).first()
            
            if not task:
                logger.warning(f"任务 {task_id} 不存在或未完成")
                continue
            
            valid_tasks.append(task_id)
        
        if not valid_tasks:
            raise HTTPException(status_code=400, detail="没有找到有效的已完成评测任务")
        
        # 获取任务数据
        report_service = ReportService()
        tasks_data = report_service._get_tasks_data(valid_tasks, db)
        
        if not tasks_data:
            raise ValueError("未找到有效的评测任务数据")
        
        # 生成与实际报告一致的预览内容
        template = request.config.get('template', 'standard')
        
        # 使用与实际生成报告相同的Markdown内容生成方法
        markdown_content = report_service._generate_markdown_content(tasks_data, request.config)
        
        # 将Markdown转换为HTML用于预览
        html_content = report_service._convert_markdown_to_html(markdown_content)
        
        # 选择对应的摘要生成方法（保持向后兼容）
        if template == 'executive':
            summary = report_service._generate_executive_summary(tasks_data)
        elif template == 'detailed':
            summary = report_service._generate_detailed_summary(tasks_data)
        else:  # standard
            summary = report_service._generate_summary(tasks_data)
        
        preview_content = {
            "title": request.config.get('customTitle', 'EvalScope 评测报告'),
            "summary": summary,
            "template": template,
            "markdown_content": markdown_content,  # 完整的Markdown内容
            "html_content": html_content,  # 转换后的HTML内容
            "tasks": []
        }
        
        # 添加任务详情（保持向后兼容）
        for task_data in tasks_data:
            task_preview = {
                "task_name": task_data['task_name'],
                "model_id": task_data['model_id'],
                "datasets": task_data['datasets'],
                "status": task_data['status'],
                "completed_at": task_data['completed_at'].isoformat() if task_data['completed_at'] else None,
                "results_count": len(task_data['results']),
                "results": task_data['results'][:5]  # 只显示前5个结果
            }
            preview_content["tasks"].append(task_preview)
        
        return preview_content
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"预览报告失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"预览报告失败: {str(e)}")

@router.get("/templates")
async def get_report_templates():
    """获取报告模板"""
    try:
        templates = [
            {
                "id": "standard",
                "name": "标准报告",
                "description": "简洁明了的技术报告，适合日常评测和团队分享",
                "sections": ["概览", "模型性能", "数据集结果", "结论"],
                "format": ["pdf", "excel", "html"],
                "icon": "📊",
                "color": "#1890ff",
                "targetAudience": "技术团队",
                "preview": "包含基础评测指标、性能对比图表和简要结论，适合技术团队日常使用"
            },
            {
                "id": "detailed",
                "name": "详细报告",
                "description": "深度分析报告，包含错误分析和改进建议",
                "sections": ["概览", "模型性能", "数据集结果", "错误分析", "对比分析", "建议", "结论"],
                "format": ["pdf", "excel", "html"],
                "icon": "🔍",
                "color": "#52c41a",
                "targetAudience": "研究人员",
                "preview": "包含详细评测数据、错误案例分析、模型对比分析和具体改进建议，适合深度研究"
            },
            {
                "id": "executive",
                "name": "执行摘要",
                "description": "面向管理层的精简报告，突出关键指标和决策建议",
                "sections": ["执行摘要", "关键发现", "建议行动"],
                "format": ["pdf", "html"],
                "icon": "📈",
                "color": "#fa8c16",
                "targetAudience": "管理层",
                "preview": "突出关键性能指标、重要发现和行动建议，适合管理层决策参考"
            }
        ]
        
        return {
            "templates": templates
        }
        
    except Exception as e:
        logger.error(f"获取报告模板失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取报告模板失败: {str(e)}")
