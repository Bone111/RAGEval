"""
模型对比分析API端点
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
import logging
from datetime import datetime
import json

from app.api import deps
from app.models.evalscope_task import EvalScopeTask, EvalScopeResult

router = APIRouter()
logger = logging.getLogger(__name__)

class ComparisonRequest(BaseModel):
    """模型对比请求"""
    task_ids: List[int]
    comparison_type: str = "detailed"  # detailed, summary, report
    include_charts: bool = True
    include_statistics: bool = True

class ComparisonResponse(BaseModel):
    """模型对比响应"""
    comparison_id: str
    tasks: List[Dict[str, Any]]
    comparison_data: Dict[str, Any]
    statistics: Dict[str, Any]
    charts_data: Dict[str, Any]
    generated_at: datetime

@router.post("/compare", response_model=ComparisonResponse)
async def compare_models(
    request: ComparisonRequest,
    db: Session = Depends(deps.get_db)
):
    """执行模型对比分析"""
    try:
        # 验证任务ID
        if len(request.task_ids) < 2:
            raise HTTPException(status_code=400, detail="至少需要2个任务进行对比")
        
        if len(request.task_ids) > 10:
            raise HTTPException(status_code=400, detail="最多支持10个任务对比")
        
        # 获取任务数据
        tasks_data = []
        for task_id in request.task_ids:
            task = db.query(EvalScopeTask).filter(
                EvalScopeTask.id == task_id,
                EvalScopeTask.status == 'completed'
            ).first()
            
            if not task:
                raise HTTPException(status_code=404, detail=f"任务 {task_id} 不存在或未完成")
            
            # 获取评测结果
            results = db.query(EvalScopeResult).filter(
                EvalScopeResult.task_id == task_id
            ).all()
            
            if not results:
                logger.warning(f"任务 {task_id} 没有评测结果")
                continue
            
            # 整理任务数据
            task_data = {
                'task_id': task.id,
                'task_name': task.task_name,
                'model_id': task.model_id,
                'model_type': task.eval_type,
                'datasets': task.datasets,
                'status': task.status,
                'created_at': task.created_at,
                'completed_at': task.completed_at,
                'progress': task.progress,
                'results': []
            }
            
            # 整理结果数据
            for result in results:
                task_data['results'].append({
                    'id': result.id,
                    'benchmark': result.benchmark,
                    'metric_name': result.metric_name,
                    'metric_value': result.metric_value,
                    'category': result.category,
                    'subset_name': result.subset_name,
                    'num_samples': result.num_samples,
                    'raw_results': result.raw_results
                })
            
            tasks_data.append(task_data)
        
        if len(tasks_data) < 2:
            raise HTTPException(status_code=400, detail="没有足够的有效任务进行对比")
        
        # 生成对比分析数据
        comparison_service = ModelComparisonService()
        
        comparison_data = comparison_service.generate_comparison_data(tasks_data)
        statistics = comparison_service.calculate_statistics(tasks_data) if request.include_statistics else {}
        charts_data = comparison_service.generate_charts_data(tasks_data) if request.include_charts else {}
        
        # 生成对比ID
        comparison_id = f"comparison_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{len(tasks_data)}models"
        
        response = ComparisonResponse(
            comparison_id=comparison_id,
            tasks=tasks_data,
            comparison_data=comparison_data,
            statistics=statistics,
            charts_data=charts_data,
            generated_at=datetime.now()
        )
        
        logger.info(f"模型对比分析完成: {comparison_id}")
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"模型对比分析失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"模型对比分析失败: {str(e)}")

@router.get("/tasks/completed")
async def get_completed_tasks_for_comparison(
    db: Session = Depends(deps.get_db)
):
    """获取可用于对比的已完成任务列表"""
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
            # 检查是否有评测结果
            results_count = db.query(EvalScopeResult).filter(
                EvalScopeResult.task_id == task.id
            ).count()
            
            # 修复：返回所有已完成的任务，不管是否有评测结果
            # 这样用户可以在模型对比页面看到所有可用的任务
            task_info = {
                "task_id": task.id,  # 修复：前端期望的字段名是task_id，不是id
                "task_name": task.task_name,
                "model_id": task.model_id,
                "model_type": task.eval_type,
                "datasets": task.datasets,
                "status": task.status,
                "created_at": task.created_at.isoformat() if task.created_at else None,
                "completed_at": task.completed_at.isoformat() if task.completed_at else None,
                "progress": task.progress,
                "results_count": results_count,
                "has_results": results_count > 0  # 添加一个标识字段
            }
            task_list.append(task_info)
        
        return {
            "tasks": task_list,
            "total": len(task_list)
        }
        
    except Exception as e:
        logger.error(f"获取已完成任务失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取任务列表失败: {str(e)}")

@router.get("/statistics/{comparison_id}")
async def get_comparison_statistics(
    comparison_id: str,
    db: Session = Depends(deps.get_db)
):
    """获取对比分析统计信息"""
    try:
        # 这里可以实现缓存或存储对比结果的逻辑
        # 目前返回基础统计信息
        return {
            "comparison_id": comparison_id,
            "statistics": {
                "total_models": 0,
                "total_datasets": 0,
                "average_score": 0,
                "best_model": None,
                "worst_model": None
            },
            "message": "统计信息功能开发中"
        }
        
    except Exception as e:
        logger.error(f"获取对比统计失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取统计信息失败: {str(e)}")

@router.post("/export")
async def export_comparison_report(
    request: ComparisonRequest,
    db: Session = Depends(deps.get_db)
):
    """导出对比分析报告"""
    try:
        # 获取对比数据
        comparison_response = await compare_models(request, db)
        
        # 生成报告
        report_service = ReportService()
        report_config = {
            'format': 'excel',
            'customTitle': f'模型对比分析报告_{datetime.now().strftime("%Y%m%d_%H%M%S")}',
            'includeModelComparison': True,
            'includeSummary': True
        }
        
        # 这里需要将对比数据转换为报告服务需要的格式
        # 暂时返回基础信息
        return {
            "message": "对比报告导出功能开发中",
            "comparison_id": comparison_response.comparison_id,
            "available_formats": ["excel", "pdf", "html"]
        }
        
    except Exception as e:
        logger.error(f"导出对比报告失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"导出报告失败: {str(e)}")

class ModelComparisonService:
    """模型对比分析服务"""
    
    def generate_comparison_data(self, tasks_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """生成对比分析数据"""
        # 收集所有数据集
        all_datasets = set()
        for task in tasks_data:
            for result in task['results']:
                all_datasets.add(result['benchmark'])
        
        all_datasets = list(all_datasets)
        
        # 生成对比表格数据
        comparison_table = []
        for dataset in all_datasets:
            row = {'benchmark': dataset}
            
            for task in tasks_data:
                result = next((r for r in task['results'] if r['benchmark'] == dataset), None)
                if result:
                    row[task['model_id']] = result['metric_value'] * 100 if result['metric_value'] else 0
                else:
                    row[task['model_id']] = None
            
            comparison_table.append(row)
        
        # 计算胜率
        win_rates = {}
        for task in tasks_data:
            wins = 0
            total = 0
            
            for result in task['results']:
                dataset = result['benchmark']
                score = result['metric_value'] or 0
                
                # 与其他模型比较
                for other_task in tasks_data:
                    if other_task['task_id'] == task['task_id']:
                        continue
                    
                    other_result = next((r for r in other_task['results'] if r['benchmark'] == dataset), None)
                    if other_result:
                        total += 1
                        if score > (other_result['metric_value'] or 0):
                            wins += 1
            
            win_rate = (wins / total * 100) if total > 0 else 0
            win_rates[task['model_id']] = round(win_rate, 2)
        
        # 计算平均分数
        average_scores = {}
        for task in tasks_data:
            scores = [r['metric_value'] for r in task['results'] if r['metric_value'] is not None]
            avg_score = (sum(scores) / len(scores) * 100) if scores else 0
            average_scores[task['model_id']] = round(avg_score, 2)
        
        return {
            'comparison_table': comparison_table,
            'win_rates': win_rates,
            'average_scores': average_scores,
            'datasets': all_datasets,
            'models': [task['model_id'] for task in tasks_data]
        }
    
    def calculate_statistics(self, tasks_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """计算统计信息"""
        all_scores = []
        model_stats = {}
        
        for task in tasks_data:
            scores = [r['metric_value'] for r in task['results'] if r['metric_value'] is not None]
            if scores:
                avg_score = sum(scores) / len(scores)
                model_stats[task['model_id']] = {
                    'average_score': round(avg_score, 4),
                    'max_score': round(max(scores), 4),
                    'min_score': round(min(scores), 4),
                    'score_count': len(scores),
                    'score_std': round(self._calculate_std(scores), 4)
                }
                all_scores.extend(scores)
        
        # 全局统计
        global_stats = {}
        if all_scores:
            global_stats = {
                'overall_average': round(sum(all_scores) / len(all_scores), 4),
                'overall_max': round(max(all_scores), 4),
                'overall_min': round(min(all_scores), 4),
                'total_scores': len(all_scores),
                'score_range': round(max(all_scores) - min(all_scores), 4)
            }
        
        # 找出最佳和最差模型
        if model_stats:
            best_model = max(model_stats.items(), key=lambda x: x[1]['average_score'])
            worst_model = min(model_stats.items(), key=lambda x: x[1]['average_score'])
            
            global_stats['best_model'] = {
                'model_id': best_model[0],
                'average_score': best_model[1]['average_score']
            }
            global_stats['worst_model'] = {
                'model_id': worst_model[0],
                'average_score': worst_model[1]['average_score']
            }
        
        return {
            'model_statistics': model_stats,
            'global_statistics': global_stats
        }
    
    def generate_charts_data(self, tasks_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """生成图表数据"""
        # 雷达图数据
        all_datasets = set()
        for task in tasks_data:
            for result in task['results']:
                all_datasets.add(result['benchmark'])
        
        all_datasets = list(all_datasets)
        
        radar_data = []
        for task in tasks_data:
            values = []
            for dataset in all_datasets:
                result = next((r for r in task['results'] if r['benchmark'] == dataset), None)
                score = (result['metric_value'] * 100) if result and result['metric_value'] else 0
                values.append(score)
            
            radar_data.append({
                'name': task['model_id'],
                'value': values
            })
        
        # 柱状图数据
        bar_data = []
        for dataset in all_datasets:
            dataset_scores = []
            for task in tasks_data:
                result = next((r for r in task['results'] if r['benchmark'] == dataset), None)
                score = (result['metric_value'] * 100) if result and result['metric_value'] else 0
                dataset_scores.append(score)
            
            bar_data.append({
                'dataset': dataset,
                'scores': dataset_scores,
                'models': [task['model_id'] for task in tasks_data]
            })
        
        # 热力图数据
        heatmap_data = []
        for i, dataset in enumerate(all_datasets):
            for j, task in enumerate(tasks_data):
                result = next((r for r in task['results'] if r['benchmark'] == dataset), None)
                score = (result['metric_value'] * 100) if result and result['metric_value'] else 0
                heatmap_data.append([i, j, score])
        
        return {
            'radar': {
                'indicators': [{'name': d.upper(), 'max': 100} for d in all_datasets],
                'series': radar_data
            },
            'bar': {
                'datasets': all_datasets,
                'data': bar_data
            },
            'heatmap': {
                'xAxis': all_datasets,
                'yAxis': [task['model_id'] for task in tasks_data],
                'data': heatmap_data
            }
        }
    
    def _calculate_std(self, scores: List[float]) -> float:
        """计算标准差"""
        if len(scores) <= 1:
            return 0.0
        
        mean = sum(scores) / len(scores)
        variance = sum((x - mean) ** 2 for x in scores) / len(scores)
        return variance ** 0.5
