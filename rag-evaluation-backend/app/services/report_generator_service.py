from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from datetime import datetime
import json
import uuid

from app.models.accuracy import AccuracyTest, AccuracyTestItem
from app.models.performance import PerformanceTest
from app.models.report import Report
from app.models.project import Project
from app.models.dataset import Dataset
from app.models.question import Question
from app.models.rag_answer import RagAnswer

class ReportGeneratorService:
    def __init__(self, db: Session):
        self.db = db
    
    def generate_accuracy_report(self, test_id: str, user_id: str) -> Optional[Report]:
        """生成精度评测报告"""
        # 获取评测详情
        test = self.db.query(AccuracyTest).filter(AccuracyTest.id == test_id).first()
        if not test or test.status != "completed":
            return None
        
        # 获取项目信息
        project = self.db.query(Project).filter(Project.id == test.project_id).first()
        if not project:
            return None
        
        # 获取数据集信息
        dataset = self.db.query(Dataset).filter(Dataset.id == test.dataset_id).first()
        if not dataset:
            return None
        
        # 获取评测项详情
        test_items = self.db.query(AccuracyTestItem).filter(
            AccuracyTestItem.evaluation_id == test_id
        ).all()
        
        # 生成报告内容
        report_content = self._generate_accuracy_report_content(
            test, project, dataset, test_items
        )
        
        # 创建报告
        report = Report(
            title=f"{test.name} - 精度评测报告",
            description=f"基于数据集 {dataset.name} 的精度评测报告",
            report_type="evaluation",
            public=False,
            user_id=user_id,
            project_id=str(test.project_id),
            config={
                "test_id": str(test.id),
                "test_name": test.name,
                "dataset_id": str(test.dataset_id),
                "dataset_name": dataset.name,
                "evaluation_type": test.evaluation_type,
                "scoring_method": test.scoring_method,
                "dimensions": test.dimensions,
                "weights": test.weights
            },
            content=report_content
        )
        
        self.db.add(report)
        self.db.commit()
        self.db.refresh(report)
        
        return report
    
    def generate_performance_report(self, test_id: str, user_id: str) -> Optional[Report]:
        """生成性能测试报告"""
        # 获取性能测试详情
        test = self.db.query(PerformanceTest).filter(PerformanceTest.id == test_id).first()
        if not test or test.status != "completed":
            return None
        
        # 获取项目信息
        project = self.db.query(Project).filter(Project.id == test.project_id).first()
        if not project:
            return None
        
        # 性能测试没有单独的测试项，直接使用测试本身的统计数据
        
        # 生成报告内容
        report_content = self._generate_performance_report_content(
            test, project
        )
        
        # 创建报告
        report = Report(
            title=f"{test.name} - 性能测试报告",
            description=f"项目 {project.name} 的性能测试报告",
            report_type="performance",
            public=False,
            user_id=user_id,
            project_id=str(test.project_id),
            config={
                "test_id": str(test.id),
                "test_name": test.name,
                "concurrency": test.concurrency,
                "total_requests": test.total_requests
            },
            content=report_content
        )
        
        self.db.add(report)
        self.db.commit()
        self.db.refresh(report)
        
        return report
    
    def generate_comparison_report(self, test_ids: List[str], user_id: str, project_id: str) -> Optional[Report]:
        """生成对比报告"""
        # 获取项目信息
        project = self.db.query(Project).filter(Project.id == project_id).first()
        if not project:
            return None
        
        # 获取所有测试详情
        tests = []
        for test_id in test_ids:
            # 尝试精度测试
            accuracy_test = self.db.query(AccuracyTest).filter(AccuracyTest.id == test_id).first()
            if accuracy_test:
                tests.append(("accuracy", accuracy_test))
            else:
                # 尝试性能测试
                performance_test = self.db.query(PerformanceTest).filter(PerformanceTest.id == test_id).first()
                if performance_test:
                    tests.append(("performance", performance_test))
        
        if not tests:
            return None
        
        # 生成对比报告内容
        report_content = self._generate_comparison_report_content(tests, project)
        
        # 创建报告
        report = Report(
            title=f"{project.name} - 评测对比报告",
            description=f"项目 {project.name} 的多项评测对比分析",
            report_type="comparison",
            public=False,
            user_id=user_id,
            project_id=project_id,
            config={
                "test_ids": test_ids,
                "test_count": len(tests)
            },
            content=report_content
        )
        
        self.db.add(report)
        self.db.commit()
        self.db.refresh(report)
        
        return report
    
    def _generate_accuracy_report_content(
        self, 
        test: AccuracyTest, 
        project: Project, 
        dataset: Dataset, 
        test_items: List[AccuracyTestItem]
    ) -> Dict[str, Any]:
        """生成精度评测报告内容"""
        # 基础统计信息
        total_questions = len(test_items)
        completed_items = [item for item in test_items if item.status in ["ai_completed", "human_completed", "both_completed"]]
        completed_count = len(completed_items)
        
        # 分数统计
        scores = [float(item.final_score) for item in completed_items if item.final_score is not None]
        avg_score = sum(scores) / len(scores) if scores else 0
        
        # 维度分数统计
        dimension_stats = {}
        for dimension in test.dimensions:
            dimension_scores = []
            for item in completed_items:
                if item.final_dimension_scores and dimension in item.final_dimension_scores:
                    score = item.final_dimension_scores[dimension]
                    if score is not None:
                        dimension_scores.append(float(score))
            
            if dimension_scores:
                dimension_stats[dimension] = {
                    "average": sum(dimension_scores) / len(dimension_scores),
                    "min": min(dimension_scores),
                    "max": max(dimension_scores),
                    "count": len(dimension_scores)
                }
        
        # 分数分布
        score_distribution = {"5": 0, "4": 0, "3": 0, "2": 0, "1": 0, "0": 0}
        for score in scores:
            score_key = str(int(round(score)))
            if score_key in score_distribution:
                score_distribution[score_key] += 1
        
        # 评测类型分布
        evaluation_types = {"ai": 0, "human": 0}
        for item in completed_items:
            if item.final_evaluation_type in evaluation_types:
                evaluation_types[item.final_evaluation_type] += 1
        
        # 详细评测结果
        detailed_results = []
        for item in completed_items[:20]:  # 只显示前20个结果
            # 获取问题和回答内容
            question = self.db.query(Question).filter(Question.id == item.question_id).first()
            rag_answer = self.db.query(RagAnswer).filter(RagAnswer.id == item.rag_answer_id).first()
            
            detailed_results.append({
                "question_id": str(item.question_id),
                "question_text": question.question_text if question else "",
                "rag_answer": rag_answer.answer if rag_answer else "",
                "final_score": float(item.final_score) if item.final_score else 0,
                "dimension_scores": item.final_dimension_scores or {},
                "evaluation_reason": item.final_evaluation_reason or "",
                "evaluation_type": item.final_evaluation_type or ""
            })
        
        return {
            "summary": {
                "test_name": test.name,
                "project_name": project.name,
                "dataset_name": dataset.name,
                "evaluation_type": test.evaluation_type,
                "scoring_method": test.scoring_method,
                "total_questions": total_questions,
                "completed_questions": completed_count,
                "completion_rate": completed_count / total_questions if total_questions > 0 else 0,
                "average_score": round(avg_score, 2),
                "overall_score": test.results_summary.get("overall_score", 0) if test.results_summary else 0
            },
            "dimensions": dimension_stats,
            "score_distribution": score_distribution,
            "evaluation_types": evaluation_types,
            "detailed_results": detailed_results,
            "test_config": {
                "dimensions": test.dimensions,
                "weights": test.weights,
                "prompt_template": test.prompt_template,
                "version": test.version
            },
            "timestamps": {
                "created_at": test.created_at.isoformat() if test.created_at else None,
                "started_at": test.started_at.isoformat() if test.started_at else None,
                "completed_at": test.completed_at.isoformat() if test.completed_at else None
            }
        }
    
    def _generate_performance_report_content(
        self, 
        test: PerformanceTest, 
        project: Project
    ) -> Dict[str, Any]:
        """生成性能测试报告内容"""
        # 基础统计信息 - 使用PerformanceTest模型中的统计数据
        total_requests = test.total_questions
        successful_count = test.success_questions
        failed_count = test.failed_questions
        
        # 成功率
        success_rate = successful_count / total_requests if total_requests > 0 else 0
        
        # 从summary_metrics中获取性能指标
        summary_metrics = test.summary_metrics or {}
        avg_response_time = summary_metrics.get('avg_response_time', 0)
        avg_first_response_time = summary_metrics.get('avg_first_response_time', 0)
        avg_generation_speed = summary_metrics.get('avg_generation_speed', 0)
        
        # 响应时间分布 - 从summary_metrics获取
        time_distribution = summary_metrics.get('time_distribution', {
            "<1s": 0,
            "1-2s": 0,
            "2-3s": 0,
            "3-5s": 0,
            "5-10s": 0,
            ">10s": 0
        })
        
        # 详细结果 - 从summary_metrics获取
        detailed_results = summary_metrics.get('detailed_results', [])
        
        return {
            "summary": {
                "test_name": test.name,
                "project_name": project.name,
                "concurrency": test.concurrency,
                "total_requests": total_requests,
                "successful_requests": successful_count,
                "success_rate": round(success_rate * 100, 2),
                "average_response_time": round(avg_response_time, 2),
                "average_first_response_time": round(avg_first_response_time, 2),
                "average_generation_speed": round(avg_generation_speed, 2)
            },
            "time_distribution": time_distribution,
            "detailed_results": detailed_results,
            "test_config": {
                "concurrency": test.concurrency,
                "total_requests": test.total_requests,
                "timeout": test.timeout
            },
            "timestamps": {
                "created_at": test.created_at.isoformat() if test.created_at else None,
                "started_at": test.started_at.isoformat() if test.started_at else None,
                "completed_at": test.completed_at.isoformat() if test.completed_at else None
            }
        }
    
    def _generate_comparison_report_content(self, tests: List[tuple], project: Project) -> Dict[str, Any]:
        """生成对比报告内容"""
        comparison_data = []
        
        for test_type, test in tests:
            if test_type == "accuracy":
                # 精度测试对比数据
                test_items = self.db.query(AccuracyTestItem).filter(
                    AccuracyTestItem.evaluation_id == test.id
                ).all()
                
                completed_items = [item for item in test_items if item.status in ["ai_completed", "human_completed", "both_completed"]]
                scores = [float(item.final_score) for item in completed_items if item.final_score is not None]
                avg_score = sum(scores) / len(scores) if scores else 0
                
                comparison_data.append({
                    "test_id": str(test.id),
                    "test_name": test.name,
                    "test_type": "accuracy",
                    "evaluation_type": test.evaluation_type,
                    "scoring_method": test.scoring_method,
                    "total_questions": len(test_items),
                    "completed_questions": len(completed_items),
                    "average_score": round(avg_score, 2),
                    "overall_score": test.results_summary.get("overall_score", 0) if test.results_summary else 0,
                    "dimensions": test.dimensions,
                    "created_at": test.created_at.isoformat() if test.created_at else None
                })
            
            elif test_type == "performance":
                # 性能测试对比数据
                summary_metrics = test.summary_metrics or {}
                avg_response_time = summary_metrics.get('avg_response_time', 0)
                
                comparison_data.append({
                    "test_id": str(test.id),
                    "test_name": test.name,
                    "test_type": "performance",
                    "concurrency": test.concurrency,
                    "total_requests": test.total_questions,
                    "successful_requests": test.success_questions,
                    "success_rate": test.success_questions / test.total_questions if test.total_questions > 0 else 0,
                    "average_response_time": round(avg_response_time, 2),
                    "created_at": test.created_at.isoformat() if test.created_at else None
                })
        
        return {
            "summary": {
                "project_name": project.name,
                "total_tests": len(tests),
                "accuracy_tests": len([t for t in tests if t[0] == "accuracy"]),
                "performance_tests": len([t for t in tests if t[0] == "performance"])
            },
            "comparison_data": comparison_data,
            "analysis": {
                "best_accuracy_test": max(comparison_data, key=lambda x: x.get("overall_score", 0)) if comparison_data else None,
                "fastest_performance_test": min([t for t in comparison_data if t["test_type"] == "performance"], key=lambda x: x.get("average_response_time", float('inf'))) if any(t["test_type"] == "performance" for t in comparison_data) else None
            }
        }
