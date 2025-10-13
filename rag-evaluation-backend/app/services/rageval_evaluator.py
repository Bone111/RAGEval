"""
RAGEval评测器 - 专门用于RAG系统评测
"""
import asyncio
import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.evalscope_task import EvalScopeTask, EvalScopeResult
from app.services.rag_service import RagService

logger = logging.getLogger(__name__)


class RAGEvalEvaluator:
    """RAGEval评测器 - 专门用于RAG系统评测"""
    
    def __init__(self, db: Session, task: EvalScopeTask, work_dir: Path, 
                 reporter, process_manager):
        self.db = db
        self.task = task
        self.work_dir = work_dir
        self.reporter = reporter
        self.process_manager = process_manager
        
        # 初始化服务
        self.rag_service = RagService(db)
        
        # RAG评测指标
        self.rag_metrics = [
            'answer_relevance',      # 答案相关性
            'answer_accuracy',       # 答案准确性
            'answer_completeness',   # 答案完整性
            'context_relevance',    # 上下文相关性
            'context_quality',      # 上下文质量
            'retrieval_precision',  # 检索精度
            'retrieval_recall',     # 检索召回率
            'response_time',        # 响应时间
            'token_efficiency'      # Token效率
        ]
    
    def evaluate(self) -> List[Dict[str, Any]]:
        """执行RAG评测"""
        all_results = []
        
        try:
            # 1. 准备评测环境
            self._prepare_evaluation_environment()
            
            # 2. 为每个数据集执行评测
            for idx, dataset_name in enumerate(self.task.datasets):
                if getattr(self.reporter, 'cancelled', False):
                    self.reporter.log("WARNING", f"⚠️ 任务已被取消，停止执行")
                    break
                
                self.reporter.log("INFO", f"")
                self.reporter.log("INFO", f"▶️  [{idx+1}/{len(self.task.datasets)}] RAG评测数据集: {dataset_name}")
                self.reporter.update_dataset_progress(dataset_name, status='running', current_step='准备')
                
                # 执行单个数据集的RAG评测
                dataset_results = self._evaluate_dataset(dataset_name)
                all_results.extend(dataset_results)
                
                # 更新数据集完成状态
                self.reporter.update_dataset_progress(dataset_name, status='completed')
                self.reporter.log("INFO", f"✅ 数据集 {dataset_name} RAG评测完成")
                
                # 更新整体进度
                progress = int((idx + 1) / len(self.task.datasets) * 80) + 15
                self.reporter.update_progress(progress, f"完成数据集 {dataset_name}")
            
            self.reporter.log("INFO", "")
            self.reporter.log("INFO", "🎉 所有数据集RAG评测完成")
            
            return all_results
            
        except Exception as e:
            logger.error(f"RAGEval评测失败: {e}")
            self.reporter.log("ERROR", f"❌ RAGEval评测失败: {e}")
            raise
    
    def _prepare_evaluation_environment(self):
        """准备评测环境"""
        self.reporter.log("INFO", "🔧 准备RAG评测环境...")
        
        # 创建工作目录
        self.work_dir.mkdir(parents=True, exist_ok=True)
        
        # 创建时间戳目录
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.timestamp_dir = self.work_dir / timestamp
        self.timestamp_dir.mkdir(exist_ok=True)
        
        # 创建子目录
        (self.timestamp_dir / "configs").mkdir(exist_ok=True)
        (self.timestamp_dir / "logs").mkdir(exist_ok=True)
        (self.timestamp_dir / "predictions").mkdir(exist_ok=True)
        (self.timestamp_dir / "reports").mkdir(exist_ok=True)
        (self.timestamp_dir / "reviews").mkdir(exist_ok=True)
        
        # 保存任务配置
        task_config = {
            "task_id": self.task.id,
            "task_name": self.task.task_name,
            "model_id": self.task.model_id,
            "datasets": self.task.datasets,
            "dataset_args": self.task.dataset_args,
            "eval_backend": self.task.eval_backend,
            "eval_type": self.task.eval_type,
            "created_at": self.task.created_at.isoformat(),
            "rag_metrics": self.rag_metrics
        }
        
        config_file = self.timestamp_dir / "configs" / "rageval_task_config.json"
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(task_config, f, ensure_ascii=False, indent=2)
        
        self.reporter.log("INFO", f"✅ RAG评测环境准备完成: {self.timestamp_dir}")
    
    def _evaluate_dataset(self, dataset_name: str) -> List[Dict[str, Any]]:
        """评测单个数据集"""
        dataset_results = []
        
        try:
            # 1. 获取数据集问题
            questions = self._get_dataset_questions(dataset_name)
            if not questions:
                self.reporter.log("WARNING", f"⚠️ 数据集 {dataset_name} 没有找到问题")
                return []
            
            # 2. 限制问题数量
            limit = self.task.dataset_args.get(dataset_name, {}).get('limit') if self.task.dataset_args else None
            if limit and len(questions) > limit:
                questions = questions[:limit]
                self.reporter.log("INFO", f"📊 限制问题数量: {limit}")
            
            self.reporter.log("INFO", f"📋 开始评测 {len(questions)} 个问题")
            
            # 3. 为每个问题执行RAG评测
            for idx, question in enumerate(questions):
                if getattr(self.reporter, 'cancelled', False):
                    break
                
                self.reporter.log("INFO", f"🔍 [{idx+1}/{len(questions)}] 评测问题: {question.question_text[:50]}...")
                
                # 执行单个问题的RAG评测
                question_result = self._evaluate_question(question, dataset_name)
                if question_result:
                    dataset_results.append(question_result)
                
                # 更新进度
                progress = int((idx + 1) / len(questions) * 100)
                self.reporter.update_dataset_progress(dataset_name, current_step=f"评测问题 {idx+1}/{len(questions)}")
            
            # 4. 计算数据集整体指标
            if dataset_results:
                dataset_summary = self._calculate_dataset_summary(dataset_results, dataset_name)
                dataset_results.append(dataset_summary)
            
            # 5. 保存结果
            self._save_dataset_results(dataset_results, dataset_name)
            
            return dataset_results
            
        except Exception as e:
            logger.error(f"数据集 {dataset_name} 评测失败: {e}")
            self.reporter.log("ERROR", f"❌ 数据集 {dataset_name} 评测失败: {e}")
            raise
    
    def _get_dataset_questions(self, dataset_name: str) -> List[Dict[str, Any]]:
        """获取数据集问题"""
        # 使用EvalScope API获取数据集问题
        try:
            from evalscope.api.dataset import get_dataset
            
            # 获取数据集
            dataset = get_dataset(dataset_name)
            if not dataset:
                self.reporter.log("WARNING", f"⚠️ 无法获取数据集: {dataset_name}")
                return []
            
            # 获取问题列表
            questions = []
            limit = self.task.dataset_args.get(dataset_name, {}).get('limit', 5) if self.task.dataset_args else 5
            
            # 从EvalScope数据集获取问题
            for i, sample in enumerate(dataset):
                if i >= limit:
                    break
                    
                question_data = {
                    'id': f"{dataset_name}_{i}",
                    'question_text': sample.get('question', ''),
                    'answer': sample.get('answer', ''),
                    'dataset_name': dataset_name
                }
                questions.append(question_data)
            
            self.reporter.log("INFO", f"📋 从EvalScope获取到 {len(questions)} 个问题")
            return questions
            
        except Exception as e:
            self.reporter.log("ERROR", f"❌ 获取数据集问题失败: {e}")
            # 返回模拟数据
            return [
                {
                    'id': f"{dataset_name}_1",
                    'question_text': f"这是一个来自{dataset_name}数据集的测试问题",
                    'answer': "测试答案",
                    'dataset_name': dataset_name
                }
            ]
    
    def _evaluate_question(self, question: Dict[str, Any], dataset_name: str) -> Optional[Dict[str, Any]]:
        """评测单个问题"""
        try:
            start_time = time.time()
            
            # 1. 获取RAG回答
            rag_answer = self._get_rag_answer(question)
            if not rag_answer:
                self.reporter.log("WARNING", f"⚠️ 问题 {question['id']} 获取RAG回答失败")
                return None
            
            # 2. 计算RAG指标
            metrics = self._calculate_rag_metrics(question, rag_answer)
            
            # 3. 计算响应时间
            response_time = time.time() - start_time
            metrics['response_time'] = response_time
            
            # 4. 构建结果
            result = {
                'question_id': question['id'],
                'question_text': question['question_text'],
                'dataset_name': dataset_name,
                'rag_answer': rag_answer.get('answer_text') if rag_answer else None,
                'metrics': metrics,
                'timestamp': datetime.now().isoformat(),
                'task_id': self.task.id
            }
            
            return result
            
        except Exception as e:
            logger.error(f"问题 {question['id']} 评测失败: {e}")
            return None
    
    def _get_rag_answer(self, question: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """获取RAG回答"""
        try:
            # 这里需要根据任务配置调用相应的RAG服务
            # 暂时返回模拟数据
            return None
        except Exception as e:
            logger.error(f"获取RAG回答失败: {e}")
            return None
    
    def _calculate_rag_metrics(self, question: Dict[str, Any], rag_answer: Dict[str, Any]) -> Dict[str, float]:
        """计算RAG指标"""
        metrics = {}
        
        try:
            # 1. 答案相关性
            metrics['answer_relevance'] = self._calculate_answer_relevance(question, rag_answer)
            
            # 2. 答案准确性
            metrics['answer_accuracy'] = self._calculate_answer_accuracy(question, rag_answer)
            
            # 3. 答案完整性
            metrics['answer_completeness'] = self._calculate_answer_completeness(question, rag_answer)
            
            # 4. 上下文相关性
            metrics['context_relevance'] = self._calculate_context_relevance(question, rag_answer)
            
            # 5. 上下文质量
            metrics['context_quality'] = self._calculate_context_quality(question, rag_answer)
            
            # 6. 检索精度
            metrics['retrieval_precision'] = self._calculate_retrieval_precision(question, rag_answer)
            
            # 7. 检索召回率
            metrics['retrieval_recall'] = self._calculate_retrieval_recall(question, rag_answer)
            
            # 8. Token效率
            metrics['token_efficiency'] = self._calculate_token_efficiency(question, rag_answer)
            
        except Exception as e:
            logger.error(f"计算RAG指标失败: {e}")
            # 返回默认值
            for metric in self.rag_metrics:
                if metric not in metrics:
                    metrics[metric] = 0.0
        
        return metrics
    
    def _calculate_answer_relevance(self, question: Dict[str, Any], rag_answer: Dict[str, Any]) -> float:
        """计算答案相关性"""
        # 使用LLM评估答案与问题的相关性
        try:
            prompt = f"""
请评估以下答案与问题的相关性，给出0-1之间的分数：

问题：{question['question_text']}
答案：{rag_answer.get('answer_text', '无答案') if rag_answer else '无答案'}

请只返回一个0-1之间的数字，表示相关性分数。
"""
            
            # 这里需要调用LLM服务
            # 暂时返回模拟值
            return 0.85
            
        except Exception as e:
            logger.error(f"计算答案相关性失败: {e}")
            return 0.0
    
    def _calculate_answer_accuracy(self, question: Dict[str, Any], rag_answer: Dict[str, Any]) -> float:
        """计算答案准确性"""
        # 使用LLM评估答案的准确性
        try:
            prompt = f"""
请评估以下答案的准确性，给出0-1之间的分数：

问题：{question['question_text']}
答案：{rag_answer.get('answer_text', '无答案') if rag_answer else '无答案'}

请只返回一个0-1之间的数字，表示准确性分数。
"""
            
            # 这里需要调用LLM服务
            # 暂时返回模拟值
            return 0.78
            
        except Exception as e:
            logger.error(f"计算答案准确性失败: {e}")
            return 0.0
    
    def _calculate_answer_completeness(self, question: Dict[str, Any], rag_answer: Dict[str, Any]) -> float:
        """计算答案完整性"""
        # 使用LLM评估答案的完整性
        try:
            prompt = f"""
请评估以下答案的完整性，给出0-1之间的分数：

问题：{question['question_text']}
答案：{rag_answer.get('answer_text', '无答案') if rag_answer else '无答案'}

请只返回一个0-1之间的数字，表示完整性分数。
"""
            
            # 这里需要调用LLM服务
            # 暂时返回模拟值
            return 0.82
            
        except Exception as e:
            logger.error(f"计算答案完整性失败: {e}")
            return 0.0
    
    def _calculate_context_relevance(self, question: Dict[str, Any], rag_answer: Dict[str, Any]) -> float:
        """计算上下文相关性"""
        # 评估检索到的上下文与问题的相关性
        try:
            # 这里需要分析RAG回答中的上下文
            # 暂时返回模拟值
            return 0.75
            
        except Exception as e:
            logger.error(f"计算上下文相关性失败: {e}")
            return 0.0
    
    def _calculate_context_quality(self, question: Dict[str, Any], rag_answer: Dict[str, Any]) -> float:
        """计算上下文质量"""
        # 评估检索到的上下文的质量
        try:
            # 这里需要分析RAG回答中的上下文质量
            # 暂时返回模拟值
            return 0.80
            
        except Exception as e:
            logger.error(f"计算上下文质量失败: {e}")
            return 0.0
    
    def _calculate_retrieval_precision(self, question: Dict[str, Any], rag_answer: Dict[str, Any]) -> float:
        """计算检索精度"""
        # 评估检索到的相关文档的比例
        try:
            # 这里需要分析检索结果
            # 暂时返回模拟值
            return 0.70
            
        except Exception as e:
            logger.error(f"计算检索精度失败: {e}")
            return 0.0
    
    def _calculate_retrieval_recall(self, question: Dict[str, Any], rag_answer: Dict[str, Any]) -> float:
        """计算检索召回率"""
        # 评估检索到的相关文档占所有相关文档的比例
        try:
            # 这里需要分析检索结果
            # 暂时返回模拟值
            return 0.65
            
        except Exception as e:
            logger.error(f"计算检索召回率失败: {e}")
            return 0.0
    
    def _calculate_token_efficiency(self, question: Dict[str, Any], rag_answer: Dict[str, Any]) -> float:
        """计算Token效率"""
        # 评估答案质量与Token消耗的比例
        try:
            if not rag_answer or not rag_answer.get('answer_text'):
                return 0.0
            
            # 计算Token数量（简化计算）
            token_count = len(rag_answer.get('answer_text', '').split())
            
            # 计算效率分数（这里需要根据实际需求调整）
            efficiency = min(1.0, 100 / max(token_count, 1))
            
            return efficiency
            
        except Exception as e:
            logger.error(f"计算Token效率失败: {e}")
            return 0.0
    
    def _calculate_dataset_summary(self, results: List[Dict[str, Any]], dataset_name: str) -> Dict[str, Any]:
        """计算数据集整体指标"""
        if not results:
            return {}
        
        # 计算各项指标的平均值
        summary = {
            'dataset_name': dataset_name,
            'total_questions': len(results),
            'task_id': self.task.id,
            'timestamp': datetime.now().isoformat(),
            'metrics': {}
        }
        
        # 计算各项指标的平均值
        for metric in self.rag_metrics:
            values = [r['metrics'].get(metric, 0) for r in results if 'metrics' in r]
            if values:
                summary['metrics'][metric] = sum(values) / len(values)
            else:
                summary['metrics'][metric] = 0.0
        
        return summary
    
    def _save_dataset_results(self, results: List[Dict[str, Any]], dataset_name: str):
        """保存数据集结果"""
        try:
            # 保存预测结果
            predictions_file = self.timestamp_dir / "predictions" / f"{dataset_name}.jsonl"
            with open(predictions_file, 'w', encoding='utf-8') as f:
                for result in results:
                    if 'question_id' in result:  # 跳过汇总结果
                        f.write(json.dumps(result, ensure_ascii=False) + '\n')
            
            # 保存评测报告
            report_file = self.timestamp_dir / "reports" / f"{dataset_name}.json"
            report_data = {
                'dataset_name': dataset_name,
                'task_id': self.task.id,
                'total_questions': len([r for r in results if 'question_id' in r]),
                'metrics_summary': results[-1]['metrics'] if results and 'metrics' in results[-1] else {},
                'timestamp': datetime.now().isoformat()
            }
            
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(report_data, f, ensure_ascii=False, indent=2)
            
            self.reporter.log("INFO", f"💾 结果已保存: {predictions_file}")
            
        except Exception as e:
            logger.error(f"保存结果失败: {e}")
            self.reporter.log("ERROR", f"❌ 保存结果失败: {e}")
