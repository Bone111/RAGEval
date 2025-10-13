"""
大模型统一管理服务
"""
import os
import json
import asyncio
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
from pathlib import Path
from sqlalchemy.orm import Session
from sqlalchemy import desc, asc, and_, or_, func
import logging

from app.models.model_management import (
    ModelInfo, ModelUsageLog, ModelDownloadTask, 
    LocalModelRegistry, ModelCategory, ModelCategoryMapping
)
from app.models.model_config import ModelConfig
from app.models.user_config import UserModelConfig


logger = logging.getLogger(__name__)


class ModelManagementService:
    """大模型统一管理服务"""
    
    def __init__(self, db: Session):
        self.db = db

    # ==================== 模型信息管理 ====================
    
    async def get_models_overview(self, user_id: str) -> Dict[str, Any]:
        """获取模型总览统计"""
        try:
            # 基础统计
            total_models = self.db.query(ModelInfo).filter(
                ModelInfo.user_id == user_id,
                ModelInfo.is_active == True
            ).count()
            
            # 按类型分组统计
            type_stats = self.db.query(
                ModelInfo.model_type,
                func.count(ModelInfo.id).label('count')
            ).filter(
                ModelInfo.user_id == user_id,
                ModelInfo.is_active == True
            ).group_by(ModelInfo.model_type).all()
            
            # 按状态分组统计
            status_stats = self.db.query(
                ModelInfo.status,
                func.count(ModelInfo.id).label('count')
            ).filter(
                ModelInfo.user_id == user_id,
                ModelInfo.is_active == True
            ).group_by(ModelInfo.status).all()
            
            # 最近使用的模型
            recent_used = self.db.query(ModelInfo).filter(
                ModelInfo.user_id == user_id,
                ModelInfo.is_active == True,
                ModelInfo.last_used_at.isnot(None)
            ).order_by(desc(ModelInfo.last_used_at)).limit(5).all()
            
            # 收藏的模型
            favorites = self.db.query(ModelInfo).filter(
                ModelInfo.user_id == user_id,
                ModelInfo.is_active == True,
                ModelInfo.is_favorite == True
            ).all()
            
            # 磁盘使用统计
            disk_usage_query = self.db.query(
                func.sum(ModelInfo.disk_usage).label('total_size')
            ).filter(
                ModelInfo.user_id == user_id,
                ModelInfo.is_active == True,
                ModelInfo.disk_usage.isnot(None)
            ).first()
            
            total_disk_usage = disk_usage_query.total_size if disk_usage_query.total_size else 0
            
            # 下载中的任务
            downloading_tasks = self.db.query(ModelDownloadTask).filter(
                ModelDownloadTask.user_id == user_id,
                ModelDownloadTask.status == 'downloading'
            ).count()
            
            return {
                'total_models': total_models,
                'type_distribution': {item.model_type: item.count for item in type_stats},
                'status_distribution': {item.status: item.count for item in status_stats},
                'recent_used': [self._serialize_model_info(model) for model in recent_used],
                'favorites': [self._serialize_model_info(model) for model in favorites],
                'total_disk_usage': total_disk_usage,
                'downloading_tasks': downloading_tasks
            }
            
        except Exception as e:
            logger.error(f"获取模型总览失败: {e}")
            return {}
    
    async def get_models_list(
        self,
        user_id: str,
        page: int = 1,
        page_size: int = 20,
        model_type: Optional[str] = None,
        status: Optional[str] = None,
        search: Optional[str] = None,
        sort_by: str = 'created_at',
        sort_order: str = 'desc'
    ) -> Dict[str, Any]:
        """获取模型列表"""
        try:
            query = self.db.query(ModelInfo).filter(
                ModelInfo.user_id == user_id,
                ModelInfo.is_active == True
            )
            
            # 筛选条件
            if model_type:
                query = query.filter(ModelInfo.model_type == model_type)
            
            if status:
                query = query.filter(ModelInfo.status == status)
            
            if search:
                search_pattern = f"%{search}%"
                query = query.filter(
                    or_(
                        ModelInfo.model_name.ilike(search_pattern),
                        ModelInfo.display_name.ilike(search_pattern),
                        ModelInfo.model_family.ilike(search_pattern)
                    )
                )
            
            # 排序
            if sort_order == 'desc':
                query = query.order_by(desc(getattr(ModelInfo, sort_by)))
            else:
                query = query.order_by(asc(getattr(ModelInfo, sort_by)))
            
            # 分页
            total = query.count()
            models = query.offset((page - 1) * page_size).limit(page_size).all()
            
            return {
                'total': total,
                'page': page,
                'page_size': page_size,
                'models': [self._serialize_model_info(model) for model in models]
            }
            
        except Exception as e:
            logger.error(f"获取模型列表失败: {e}")
            return {'total': 0, 'models': []}
    
    async def get_model_detail(self, user_id: str, model_id: int) -> Optional[Dict[str, Any]]:
        """获取模型详细信息"""
        try:
            model = self.db.query(ModelInfo).filter(
                ModelInfo.id == model_id,
                ModelInfo.user_id == user_id
            ).first()
            
            if not model:
                return None
            
            # 获取使用统计
            usage_stats = await self._get_model_usage_stats(model_id)
            
            # 获取分类信息
            categories = self.db.query(ModelCategory).join(
                ModelCategoryMapping,
                ModelCategory.id == ModelCategoryMapping.category_id
            ).filter(
                ModelCategoryMapping.model_id == model_id
            ).all()
            
            result = self._serialize_model_info(model)
            result['usage_stats'] = usage_stats
            result['categories'] = [self._serialize_category(cat) for cat in categories]
            
            return result
            
        except Exception as e:
            logger.error(f"获取模型详情失败: {e}")
            return None
    
    async def update_model_info(
        self,
        user_id: str,
        model_id: int,
        updates: Dict[str, Any]
    ) -> bool:
        """更新模型信息"""
        try:
            model = self.db.query(ModelInfo).filter(
                ModelInfo.id == model_id,
                ModelInfo.user_id == user_id
            ).first()
            
            if not model:
                return False
            
            # 更新允许的字段
            allowed_fields = [
                'display_name', 'notes', 'is_favorite', 'tags',
                'quality_rating', 'capabilities', 'languages'
            ]
            
            for field, value in updates.items():
                if field in allowed_fields:
                    setattr(model, field, value)
            
            model.updated_at = datetime.utcnow()
            self.db.commit()
            
            return True
            
        except Exception as e:
            logger.error(f"更新模型信息失败: {e}")
            self.db.rollback()
            return False
    
    async def delete_model(self, user_id: str, model_id: int) -> bool:
        """删除模型（软删除）"""
        try:
            model = self.db.query(ModelInfo).filter(
                ModelInfo.id == model_id,
                ModelInfo.user_id == user_id
            ).first()
            
            if not model:
                return False
            
            model.is_active = False
            model.updated_at = datetime.utcnow()
            self.db.commit()
            
            return True
            
        except Exception as e:
            logger.error(f"删除模型失败: {e}")
            self.db.rollback()
            return False
    
    # ==================== 本地模型扫描 ====================
    
    async def scan_local_models(self, scan_paths: List[str]) -> Dict[str, Any]:
        """扫描本地模型"""
        try:
            results = {
                'scanned_paths': [],
                'found_models': [],
                'errors': []
            }
            
            for scan_path in scan_paths:
                if not os.path.exists(scan_path):
                    results['errors'].append(f"路径不存在: {scan_path}")
                    continue
                
                try:
                    found_models = await self._scan_path_for_models(scan_path)
                    results['scanned_paths'].append(scan_path)
                    results['found_models'].extend(found_models)
                except Exception as e:
                    results['errors'].append(f"扫描路径 {scan_path} 失败: {str(e)}")
            
            return results
            
        except Exception as e:
            logger.error(f"扫描本地模型失败: {e}")
            return {'scanned_paths': [], 'found_models': [], 'errors': [str(e)]}
    
    async def _scan_path_for_models(self, scan_path: str) -> List[Dict[str, Any]]:
        """扫描指定路径下的模型"""
        found_models = []
        
        for root, dirs, files in os.walk(scan_path):
            # 查找模型配置文件
            config_files = []
            model_files = []
            
            for file in files:
                file_path = os.path.join(root, file)
                file_lower = file.lower()
                
                # 配置文件
                if file_lower in ['config.json', 'model_config.json', 'generation_config.json']:
                    config_files.append(file_path)
                
                # 模型文件
                if any(file_lower.endswith(ext) for ext in ['.bin', '.safetensors', '.pth', '.ckpt', '.gguf']):
                    model_files.append(file_path)
            
            # 如果找到模型文件，记录这个目录
            if model_files or config_files:
                model_info = await self._analyze_model_directory(root, config_files, model_files)
                if model_info:
                    found_models.append(model_info)
        
        return found_models
    
    async def _analyze_model_directory(
        self, 
        model_dir: str, 
        config_files: List[str], 
        model_files: List[str]
    ) -> Optional[Dict[str, Any]]:
        """分析模型目录"""
        try:
            model_name = os.path.basename(model_dir)
            
            # 分析配置文件获取模型信息
            detected_info = {}
            
            for config_file in config_files:
                try:
                    with open(config_file, 'r', encoding='utf-8') as f:
                        config_data = json.load(f)
                        detected_info.update(config_data)
                except Exception as e:
                    logger.warning(f"读取配置文件失败 {config_file}: {e}")
            
            # 计算总文件大小
            total_size = 0
            for file_path in model_files + config_files:
                try:
                    total_size += os.path.getsize(file_path)
                except:
                    pass
            
            # 获取最后修改时间
            last_modified = datetime.fromtimestamp(os.path.getmtime(model_dir))
            
            # 检查是否已经注册
            existing = self.db.query(LocalModelRegistry).filter(
                LocalModelRegistry.model_path == model_dir
            ).first()
            
            if existing:
                # 更新现有记录
                existing.file_size = total_size
                existing.file_count = len(model_files) + len(config_files)
                existing.config_files = config_files
                existing.last_modified = last_modified
                existing.last_scanned = datetime.utcnow()
                existing.detected_info = detected_info
                self.db.commit()
            else:
                # 创建新记录
                registry_entry = LocalModelRegistry(
                    model_path=model_dir,
                    model_name=model_name,
                    model_type=self._infer_model_type(detected_info, model_files),
                    file_size=total_size,
                    file_count=len(model_files) + len(config_files),
                    config_files=config_files,
                    scan_status='discovered',
                    last_modified=last_modified,
                    detected_info=detected_info
                )
                self.db.add(registry_entry)
                self.db.commit()
            
            return {
                'path': model_dir,
                'name': model_name,
                'size': total_size,
                'file_count': len(model_files) + len(config_files),
                'detected_info': detected_info,
                'last_modified': last_modified.isoformat()
            }
            
        except Exception as e:
            logger.error(f"分析模型目录失败 {model_dir}: {e}")
            return None
    
    def _infer_model_type(self, config_data: Dict, model_files: List[str]) -> str:
        """推断模型类型"""
        # 通过配置文件推断
        if 'model_type' in config_data:
            return config_data['model_type']
        
        if 'architectures' in config_data:
            arch = config_data['architectures'][0].lower()
            if 'llama' in arch:
                return 'llama'
            elif 'qwen' in arch:
                return 'qwen'
            elif 'gpt' in arch:
                return 'gpt'
        
        # 通过文件名推断
        for file_path in model_files:
            file_name = os.path.basename(file_path).lower()
            if 'llama' in file_name:
                return 'llama'
            elif 'qwen' in file_name:
                return 'qwen'
            elif 'gpt' in file_name:
                return 'gpt'
        
        return 'unknown'
    
    def _extract_friendly_model_name(self, model_path: str, original_name: str) -> str:
        """从模型路径提取友好的模型名称"""
        try:
            # 处理Hugging Face Hub缓存路径
            # /Users/xxx/.cache/huggingface/hub/models--org--name/snapshots/hash
            if 'huggingface/hub/models--' in model_path:
                parts = model_path.split('models--')
                if len(parts) > 1:
                    model_part = parts[1].split('/snapshots')[0]
                    # 将--替换为/，得到org/model格式
                    friendly_name = model_part.replace('--', '/')
                    return friendly_name
            
            # 处理ModelScope Hub缓存路径  
            # /Users/xxx/.cache/modelscope/hub/models/Org/Model___Version
            if 'modelscope/hub/models/' in model_path:
                parts = model_path.split('modelscope/hub/models/')
                if len(parts) > 1:
                    model_part = parts[1]
                    # 修复：正确处理ModelScope模型名称格式
                    # 保持点号不变，只处理版本分隔符
                    if '___' in model_part:
                        # 有版本信息，去掉版本部分
                        friendly_name = model_part.split('___')[0]
                    else:
                        friendly_name = model_part
                    return friendly_name
            
            # 处理普通路径，提取最后的目录名
            path_parts = model_path.rstrip('/').split('/')
            if len(path_parts) > 0:
                last_part = path_parts[-1]
                # 如果是hash格式（长度>30且全为字母数字），尝试使用上级目录
                if len(last_part) > 30 and last_part.isalnum():
                    if len(path_parts) > 1:
                        return path_parts[-2]
                return last_part
            
            return original_name
            
        except Exception as e:
            logger.warning(f"提取友好模型名称失败: {e}")
            return original_name
    
    async def register_local_model(
        self, 
        user_id: str, 
        registry_id: int,
        custom_info: Optional[Dict[str, Any]] = None,
        auto_enable: bool = True
    ) -> Optional[int]:
        """将本地扫描的模型注册为用户模型"""
        try:
            registry_entry = self.db.query(LocalModelRegistry).filter(
                LocalModelRegistry.id == registry_id
            ).first()
            
            if not registry_entry:
                return None
            
            # 创建模型信息记录
            model_info = ModelInfo(
                user_id=user_id,
                model_id=f"local_{registry_entry.id}_{int(datetime.utcnow().timestamp())}",
                model_name=self._extract_friendly_model_name(registry_entry.model_path, registry_entry.model_name),
                display_name=custom_info.get('display_name', self._extract_friendly_model_name(registry_entry.model_path, registry_entry.model_name)) if custom_info else self._extract_friendly_model_name(registry_entry.model_path, registry_entry.model_name),
                model_type='local',
                model_source='local_scan',
                model_path=registry_entry.model_path,
                status='available',
                is_active=auto_enable,  # 根据auto_enable参数设置是否启用
                file_size=registry_entry.file_size,
                disk_usage=registry_entry.file_size,
                notes=custom_info.get('notes') if custom_info else None,
                extra_metadata={
                    'registry_id': registry_entry.id,
                    'detected_info': registry_entry.detected_info,
                    'config_files': registry_entry.config_files
                }
            )
            
            # 从配置文件提取信息
            if registry_entry.detected_info:
                if 'max_position_embeddings' in registry_entry.detected_info:
                    model_info.supported_context_length = registry_entry.detected_info['max_position_embeddings']
                
                if 'architectures' in registry_entry.detected_info:
                    model_info.model_family = registry_entry.detected_info['architectures'][0].split('For')[0]
            
            self.db.add(model_info)
            self.db.flush()  # 获取ID
            
            # 更新注册表状态
            registry_entry.scan_status = 'registered'
            
            self.db.commit()
            
            return model_info.id
            
        except Exception as e:
            logger.error(f"注册本地模型失败: {e}")
            self.db.rollback()
            return None
    
    # ==================== 使用统计 ====================
    
    async def log_model_usage(
        self,
        user_id: str,
        model_id: int,
        usage_type: str,
        usage_data: Dict[str, Any]
    ) -> bool:
        """记录模型使用日志"""
        try:
            usage_log = ModelUsageLog(
                user_id=user_id,
                model_id=model_id,
                usage_type=usage_type,
                task_name=usage_data.get('task_name'),
                input_tokens=usage_data.get('input_tokens'),
                output_tokens=usage_data.get('output_tokens'),
                latency_ms=usage_data.get('latency_ms'),
                throughput=usage_data.get('throughput'),
                cost_estimate=usage_data.get('cost_estimate'),
                quality_score=usage_data.get('quality_score'),
                user_rating=usage_data.get('user_rating'),
                started_at=usage_data.get('started_at', datetime.utcnow()),
                completed_at=usage_data.get('completed_at'),
                extra_data=usage_data.get('extra_data', {})
            )
            
            self.db.add(usage_log)
            
            # 🔥 关键修复：更新模型使用统计前先刷新对象
            model = self.db.query(ModelInfo).filter(
                ModelInfo.id == model_id,
                ModelInfo.user_id == user_id
            ).first()
            
            if model:
                # 刷新模型对象以获取最新数据
                self.db.refresh(model)
                
                # 记录更新前的值
                old_usage_count = model.usage_count
                
                model.usage_count += 1
                model.last_used_at = datetime.utcnow()
                model.updated_at = datetime.utcnow()
                
                # 立即刷新确保更新
                self.db.flush()
                
                logger.info(f"✅ 更新模型使用统计: {model.model_name} 使用次数: {old_usage_count} -> {model.usage_count}")
            else:
                logger.warning(f"⚠️ 找不到模型 ID {model_id} (用户: {user_id}) 用于更新使用统计")
            
            self.db.commit()
            return True
            
        except Exception as e:
            logger.error(f"记录模型使用失败: {e}")
            self.db.rollback()
            return False
    
    async def log_model_usage_by_name(
        self, 
        model_name: str, 
        usage_type: str = 'eval', 
        task_name: str = None,
        user_id: str = None
    ) -> bool:
        """通过模型名称记录使用情况（便捷方法）"""
        try:
            # 查找模型
            query = self.db.query(ModelInfo).filter(
                ModelInfo.model_name == model_name,
                ModelInfo.is_active == True
            )
            
            # 如果没有指定用户ID，使用第一个找到的模型
            if user_id:
                model = query.filter(ModelInfo.user_id == user_id).first()
            else:
                model = query.first()
                if model:
                    user_id = model.user_id
            
            if not model:
                logger.warning(f"⚠️ 找不到模型: {model_name}")
                return False
            
            # 记录使用情况
            usage_data = {
                'task_name': task_name,
                'started_at': datetime.utcnow(),
                'completed_at': datetime.utcnow()
            }
            
            return await self.log_model_usage(
                user_id=user_id,
                model_id=model.id,
                usage_type=usage_type,
                usage_data=usage_data
            )
            
        except Exception as e:
            logger.error(f"通过名称记录模型使用失败: {e}")
            return False
    
    def log_model_usage_by_name_sync(
        self, 
        model_name: str, 
        usage_type: str = 'eval', 
        task_name: str = None,
        user_id: str = None
    ) -> bool:
        """通过模型名称记录使用情况（同步方法，用于Celery任务）"""
        try:
            # 查找模型
            query = self.db.query(ModelInfo).filter(
                ModelInfo.model_name == model_name,
                ModelInfo.is_active == True
            )
            
            # 如果没有指定用户ID，使用第一个找到的模型
            if user_id:
                model = query.filter(ModelInfo.user_id == user_id).first()
            else:
                model = query.first()
                if model:
                    user_id = model.user_id
            
            if not model:
                logger.warning(f"⚠️ 找不到模型: {model_name}")
                return False
            
            # 创建使用日志记录
            usage_log = ModelUsageLog(
                user_id=user_id,
                model_id=model.id,
                usage_type=usage_type,
                task_name=task_name,
                started_at=datetime.utcnow(),
                completed_at=datetime.utcnow(),
                extra_data={'sync_call': True}
            )
            
            self.db.add(usage_log)
            
            # 🔥 关键修复：使用原子更新操作来避免并发问题
            # 刷新模型对象以获取最新数据
            self.db.refresh(model)
            
            # 记录更新前的值
            old_usage_count = model.usage_count
            
            # 更新模型使用统计
            model.usage_count += 1
            model.last_used_at = datetime.utcnow()
            model.updated_at = datetime.utcnow()
            
            # 立即刷新确保更新
            self.db.flush()
            
            logger.info(f"✅ 更新模型使用统计: {model.model_name} 使用次数: {old_usage_count} -> {model.usage_count}")
            
            self.db.commit()
            return True
            
        except Exception as e:
            logger.error(f"同步记录模型使用失败: {e}")
            self.db.rollback()
            return False
    
    async def _get_model_usage_stats(self, model_id: int) -> Dict[str, Any]:
        """获取模型使用统计"""
        try:
            # 基础统计
            total_usage = self.db.query(ModelUsageLog).filter(
                ModelUsageLog.model_id == model_id
            ).count()
            
            # 按类型统计
            usage_by_type = self.db.query(
                ModelUsageLog.usage_type,
                func.count(ModelUsageLog.id).label('count')
            ).filter(
                ModelUsageLog.model_id == model_id
            ).group_by(ModelUsageLog.usage_type).all()
            
            # 性能统计
            perf_stats = self.db.query(
                func.avg(ModelUsageLog.latency_ms).label('avg_latency'),
                func.avg(ModelUsageLog.throughput).label('avg_throughput'),
                func.sum(ModelUsageLog.input_tokens).label('total_input_tokens'),
                func.sum(ModelUsageLog.output_tokens).label('total_output_tokens')
            ).filter(
                ModelUsageLog.model_id == model_id
            ).first()
            
            # 最近7天使用情况
            week_ago = datetime.utcnow() - timedelta(days=7)
            recent_usage = self.db.query(
                func.date(ModelUsageLog.created_at).label('date'),
                func.count(ModelUsageLog.id).label('count')
            ).filter(
                ModelUsageLog.model_id == model_id,
                ModelUsageLog.created_at >= week_ago
            ).group_by(func.date(ModelUsageLog.created_at)).all()
            
            return {
                'total_usage': total_usage,
                'usage_by_type': {item.usage_type: item.count for item in usage_by_type},
                'avg_latency': float(perf_stats.avg_latency) if perf_stats.avg_latency else None,
                'avg_throughput': float(perf_stats.avg_throughput) if perf_stats.avg_throughput else None,
                'total_input_tokens': int(perf_stats.total_input_tokens) if perf_stats.total_input_tokens else 0,
                'total_output_tokens': int(perf_stats.total_output_tokens) if perf_stats.total_output_tokens else 0,
                'recent_usage': {item.date.isoformat(): item.count for item in recent_usage}
            }
            
        except Exception as e:
            logger.error(f"获取使用统计失败: {e}")
            return {}
    
    # ==================== 分类管理 ====================
    
    async def get_categories(self) -> List[Dict[str, Any]]:
        """获取所有分类"""
        try:
            categories = self.db.query(ModelCategory).filter(
                ModelCategory.is_active == True
            ).order_by(ModelCategory.sort_order, ModelCategory.name).all()
            
            return [self._serialize_category(cat) for cat in categories]
            
        except Exception as e:
            logger.error(f"获取分类失败: {e}")
            return []
    
    async def add_model_to_category(self, model_id: int, category_id: int) -> bool:
        """将模型添加到分类"""
        try:
            existing = self.db.query(ModelCategoryMapping).filter(
                ModelCategoryMapping.model_id == model_id,
                ModelCategoryMapping.category_id == category_id
            ).first()
            
            if existing:
                return True
            
            mapping = ModelCategoryMapping(
                model_id=model_id,
                category_id=category_id
            )
            self.db.add(mapping)
            self.db.commit()
            
            return True
            
        except Exception as e:
            logger.error(f"添加模型分类失败: {e}")
            self.db.rollback()
            return False
    
    # ==================== 本地模型注册表管理 ====================
    
    async def get_local_registry_entries(self) -> List[Dict[str, Any]]:
        """获取本地模型注册表条目"""
        try:
            entries = self.db.query(LocalModelRegistry).order_by(
                LocalModelRegistry.last_scanned.desc()
            ).all()
            
            return [self._serialize_registry_entry(entry) for entry in entries]
            
        except Exception as e:
            logger.error(f"获取本地模型注册表失败: {e}")
            return []
    
    def _serialize_registry_entry(self, entry: LocalModelRegistry) -> Dict[str, Any]:
        """序列化注册表条目"""
        return {
            'id': entry.id,
            'model_path': entry.model_path,
            'model_name': entry.model_name,
            'model_type': entry.model_type,
            'file_size': entry.file_size,
            'file_count': entry.file_count,
            'config_files': entry.config_files,
            'scan_status': entry.scan_status,
            'last_modified': entry.last_modified.isoformat() if entry.last_modified else None,
            'last_scanned': entry.last_scanned.isoformat() if entry.last_scanned else None,
            'detected_info': entry.detected_info,
            'created_at': entry.created_at.isoformat() if entry.created_at else None,
            'updated_at': entry.updated_at.isoformat() if entry.updated_at else None
        }
    
    # ==================== 辅助方法 ====================
    
    def _serialize_model_info(self, model: ModelInfo) -> Dict[str, Any]:
        """序列化模型信息"""
        return {
            'id': model.id,
            'model_id': model.model_id,
            'model_name': model.model_name,
            'display_name': model.display_name,
            'model_type': model.model_type,
            'model_source': model.model_source,
            'model_family': model.model_family,
            'model_size': model.model_size,
            'parameter_count': model.parameter_count,
            'model_version': model.model_version,
            'model_path': model.model_path,
            'api_url': model.api_url,
            'api_provider': model.api_provider,
            'status': model.status,
            'download_progress': model.download_progress,
            'file_size': model.file_size,
            'disk_usage': model.disk_usage,
            'supported_context_length': model.supported_context_length,
            'max_tokens': model.max_tokens,
            'inference_speed': model.inference_speed,
            'memory_usage': model.memory_usage,
            'capabilities': model.capabilities,
            'languages': model.languages,
            'tags': model.tags,
            'usage_count': model.usage_count,
            'last_used_at': model.last_used_at.isoformat() if model.last_used_at else None,
            'benchmark_scores': model.benchmark_scores,
            'quality_rating': model.quality_rating,
            'is_active': model.is_active,
            'is_favorite': model.is_favorite,
            'notes': model.notes,
            'created_at': model.created_at.isoformat() if model.created_at else None,
            'updated_at': model.updated_at.isoformat() if model.updated_at else None,
            'last_scanned_at': model.last_scanned_at.isoformat() if model.last_scanned_at else None,
            'extra_metadata': model.extra_metadata,
            'is_translation_model': model.is_translation_model,
            'translation_priority': model.translation_priority
        }
    
    def _serialize_category(self, category: ModelCategory) -> Dict[str, Any]:
        """序列化分类信息"""
        return {
            'id': category.id,
            'name': category.name,
            'display_name': category.display_name,
            'description': category.description,
            'icon': category.icon,
            'color': category.color,
            'sort_order': category.sort_order,
            'is_active': category.is_active
        }
    
    # ==================== 数据同步功能 ====================
    
    async def sync_existing_models(self, user_id: str) -> Dict[str, Any]:
        """同步现有的模型配置到统一管理系统（智能同步：增删改）"""
        try:
            logger.info(f"🔄 开始为用户 {user_id} 同步模型配置...")
            result = {
                'synced_user_configs': 0,
                'synced_model_configs': 0,
                'scanned_local_models': 0,
                'removed_models': 0,
                'errors': []
            }
            
            # 0. 清理已删除的配置（智能同步：删除不再存在的配置）
            logger.info("🧹 步骤0: 清理已删除的配置...")
            removed_count = await self._cleanup_removed_configs(user_id)
            result['removed_models'] = removed_count
            logger.info(f"🗑️  清理了 {removed_count} 个已删除的配置")
            
            # 1. 同步用户配置的模型（API配置管理）
            logger.info("📦 步骤1: 同步用户API配置...")
            user_configs_synced = await self._sync_user_model_configs(user_id)
            result['synced_user_configs'] = user_configs_synced
            logger.info(f"✅ 同步了 {user_configs_synced} 个用户API配置")
            
            # 2. 同步传统模型配置
            logger.info("📦 步骤2: 同步传统模型配置...")
            model_configs_synced = await self._sync_model_configs(user_id)
            result['synced_model_configs'] = model_configs_synced
            logger.info(f"✅ 同步了 {model_configs_synced} 个传统模型配置")
            
            # 3. 扫描常见的本地模型路径
            logger.info("📦 步骤3: 扫描本地模型路径...")
            local_models_scanned = await self._scan_common_model_paths()
            result['scanned_local_models'] = local_models_scanned
            logger.info(f"✅ 扫描到 {local_models_scanned} 个本地模型")
            
            # 4. 自动注册发现的本地模型
            logger.info("📦 步骤4: 自动注册本地模型...")
            registered_models = await self.auto_register_discovered_models(user_id)
            result['auto_registered_models'] = registered_models
            logger.info(f"✅ 自动注册了 {registered_models} 个本地模型")
            
            logger.info(f"🎉 同步完成! 新增: API {user_configs_synced} 个, 传统 {model_configs_synced} 个, 本地 {local_models_scanned} 个 | 清理: {removed_count} 个")
            return result
            
        except Exception as e:
            logger.error(f"❌ 同步现有模型失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {'error': str(e)}
    
    async def _cleanup_removed_configs(self, user_id: str) -> int:
        """清理已删除或禁用的配置（智能同步核心）"""
        try:
            # 1. 获取所有活跃的用户配置ID
            active_user_config_ids = [
                str(config.id) for config in 
                self.db.query(UserModelConfig.id).filter(
                    UserModelConfig.user_id == user_id,
                    UserModelConfig.is_active == True
                ).all()
            ]
            
            # 2. 获取所有活跃的传统配置ID
            active_model_config_ids = [
                str(config.id) for config in 
                self.db.query(ModelConfig.id).filter(
                    ModelConfig.user_id == user_id,
                    ModelConfig.is_active == True
                ).all()
            ]
            
            # 3. 查找model_info中需要删除的记录（来源于user_config或model_config，但源已删除）
            orphaned_models = []
            
            # 查找来源于user_config但源已删除的
            user_config_models = self.db.query(ModelInfo).filter(
                ModelInfo.user_id == user_id,
                ModelInfo.model_id.like('user_config_%')
            ).all()
            
            for model in user_config_models:
                # 提取原始config_id
                config_id = model.model_id.replace('user_config_', '')
                if config_id not in active_user_config_ids:
                    orphaned_models.append(model)
                    logger.info(f"🗑️  标记删除: {model.model_name} (源配置已删除/禁用)")
            
            # 查找来源于model_config但源已删除的
            model_config_models = self.db.query(ModelInfo).filter(
                ModelInfo.user_id == user_id,
                ModelInfo.model_id.like('model_config_%')
            ).all()
            
            for model in model_config_models:
                config_id = model.model_id.replace('model_config_', '')
                if config_id not in active_model_config_ids:
                    orphaned_models.append(model)
                    logger.info(f"🗑️  标记删除: {model.model_name} (源配置已删除/禁用)")
            
            # 4. 批量删除孤立记录
            removed_count = 0
            for model in orphaned_models:
                self.db.delete(model)
                removed_count += 1
            
            self.db.commit()
            
            if removed_count > 0:
                logger.info(f"✅ 清理完成: 删除了 {removed_count} 个孤立模型记录")
            else:
                logger.debug("✅ 无需清理，所有记录都有效")
            
            return removed_count
            
        except Exception as e:
            logger.error(f"❌ 清理孤立配置失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            self.db.rollback()
            return 0
    
    async def _sync_user_model_configs(self, user_id: str) -> int:
        """同步用户配置的模型（API配置管理）"""
        try:
            # 获取用户的模型配置
            user_configs = self.db.query(UserModelConfig).filter(
                UserModelConfig.user_id == user_id,
                UserModelConfig.is_active == True
            ).all()
            
            logger.info(f"📋 找到 {len(user_configs)} 个活跃的用户API配置")
            
            synced_count = 0
            skipped_count = 0
            updated_count = 0
            
            for config in user_configs:
                # 检查是否已经同步过
                existing = self.db.query(ModelInfo).filter(
                    ModelInfo.user_id == user_id,
                    ModelInfo.model_id == f"user_config_{config.id}"
                ).first()
                
                # 优先使用真实的模型名称
                real_model_name = config.model_name or config.name
                display_name = real_model_name
                if config.model_name and config.name and config.model_name != config.name:
                    display_name = config.model_name
                
                if existing:
                    # 已存在，检查是否需要更新
                    needs_update = False
                    if existing.model_name != real_model_name:
                        existing.model_name = real_model_name
                        needs_update = True
                    if existing.display_name != display_name:
                        existing.display_name = display_name
                        needs_update = True
                    if existing.api_url != config.base_url:
                        existing.api_url = config.base_url
                        needs_update = True
                    if existing.api_key != config.api_key:
                        existing.api_key = config.api_key
                        needs_update = True
                    
                    if needs_update:
                        existing.updated_at = datetime.utcnow()
                        logger.info(f"🔄 更新配置: {config.name} -> {real_model_name}")
                        updated_count += 1
                    else:
                        logger.debug(f"⏭️  跳过未变更的配置: {config.name}")
                        skipped_count += 1
                    continue
                
                # 创建新的模型信息记录
                logger.info(f"➕ 新增API配置: {config.name} -> 模型: {real_model_name} (类型: {config.type})")
                
                model_info = ModelInfo(
                    user_id=user_id,
                    model_id=f"user_config_{config.id}",
                    model_name=real_model_name,
                    display_name=display_name,
                    model_type='api',
                    model_source=config.type,
                    api_url=config.base_url,
                    api_key=config.api_key,
                    api_provider=config.type,
                    status='available',
                    extra_metadata={
                        'user_config_id': str(config.id),
                        'user_custom_name': config.name,
                        'additional_params': config.additional_params,
                        'sync_source': 'user_config'
                    }
                )
                
                self.db.add(model_info)
                synced_count += 1
            
            self.db.commit()
            logger.info(f"💾 已提交: 新增 {synced_count} 个, 更新 {updated_count} 个, 跳过 {skipped_count} 个")
            return synced_count
            
        except Exception as e:
            logger.error(f"❌ 同步用户模型配置失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            self.db.rollback()
            return 0
    
    async def _sync_model_configs(self, user_id: str) -> int:
        """同步传统模型配置表"""
        try:
            # 获取传统的模型配置
            model_configs = self.db.query(ModelConfig).filter(
                ModelConfig.user_id == user_id,
                ModelConfig.is_active == True
            ).all()
            
            logger.info(f"📋 找到 {len(model_configs)} 个活跃的传统模型配置")
            
            synced_count = 0
            skipped_count = 0
            
            for config in model_configs:
                # 检查是否已经同步过
                existing = self.db.query(ModelInfo).filter(
                    ModelInfo.user_id == user_id,
                    ModelInfo.model_id == f"model_config_{config.id}"
                ).first()
                
                if existing:
                    logger.debug(f"⏭️  跳过已同步的配置: {config.model_name or config.model_id}")
                    skipped_count += 1
                    continue  # 已经同步过，跳过
                
                # 推断模型类型
                model_type = config.model_type
                if model_type not in ['local', 'api', 'download', 'cloud']:
                    model_type = 'api' if config.api_url else 'local'
                
                logger.info(f"➕ 同步传统配置: {config.model_name or config.model_id} (类型: {model_type})")
                
                # 创建新的模型信息记录
                model_info = ModelInfo(
                    user_id=user_id,
                    model_id=f"model_config_{config.id}",
                    model_name=config.model_name or config.model_id,
                    display_name=config.model_name or config.model_id,
                    model_type=model_type,
                    model_path=config.model_path,
                    api_url=config.api_url,
                    api_key=config.api_key,
                    status='available',
                    extra_metadata={
                        'model_config_id': config.id,
                        'model_args': config.model_args,
                        'generation_config': config.generation_config,
                        'sync_source': 'model_config'
                    }
                )
                
                self.db.add(model_info)
                synced_count += 1
            
            self.db.commit()
            logger.info(f"💾 已提交: 新增 {synced_count} 个, 跳过 {skipped_count} 个已存在的配置")
            return synced_count
            
        except Exception as e:
            logger.error(f"❌ 同步传统模型配置失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            self.db.rollback()
            return 0
    
    async def _scan_common_model_paths(self) -> int:
        """扫描常见的本地模型路径"""
        try:
            # 常见的本地模型路径
            common_paths = [
                os.path.expanduser("~/models"),
                os.path.expanduser("~/.cache/huggingface/transformers"),
                os.path.expanduser("~/.cache/modelscope/hub"),
                os.path.expanduser("~/.cache/huggingface/hub"),
                os.path.expanduser("~/Downloads/models"),
                os.path.expanduser("~/Documents/models"),
                "/opt/models",
                "/usr/local/models",
                "./models",
                "./local_models",
                "/data/models",
                "/home/models"
            ]
            
            # 过滤存在的路径
            existing_paths = [path for path in common_paths if os.path.exists(path)]
            
            logger.info(f"扫描到的本地模型路径: {existing_paths}")
            
            if not existing_paths:
                logger.warning("未找到常见的本地模型路径")
                return 0
            
            # 使用现有的扫描功能
            scan_result = await self.scan_local_models(existing_paths)
            found_count = len(scan_result.get('found_models', []))
            logger.info(f"扫描到 {found_count} 个本地模型")
            
            # 自动注册发现的本地模型
            if found_count > 0:
                await self._auto_register_local_models(scan_result.get('found_models', []))
            
            return found_count
            
        except Exception as e:
            logger.error(f"扫描常见模型路径失败: {e}")
            return 0
    
    async def get_local_registry_entries(self) -> List[Dict[str, Any]]:
        """获取本地模型注册表条目"""
        try:
            entries = self.db.query(LocalModelRegistry).order_by(
                desc(LocalModelRegistry.last_scanned)
            ).all()
            
            return [
                {
                    'id': entry.id,
                    'model_name': entry.model_name,
                    'model_path': entry.model_path,
                    'model_type': entry.model_type,
                    'file_size': entry.file_size,
                    'file_count': entry.file_count,
                    'scan_status': entry.scan_status,
                    'is_enabled': getattr(entry, 'is_enabled', True),  # 默认为True以兼容旧数据
                    'last_modified': entry.last_modified.isoformat() if entry.last_modified else None,
                    'last_scanned': entry.last_scanned.isoformat() if entry.last_scanned else None,
                    'detected_info': entry.detected_info,
                    'config_files': entry.config_files
                }
                for entry in entries
            ]
            
        except Exception as e:
            logger.error(f"获取本地注册表失败: {e}")
            return []
    
    async def auto_register_discovered_models(self, user_id: str) -> int:
        """自动注册所有发现的本地模型到用户模型列表（默认启用有效LLM）"""
        try:
            # 获取所有未注册的本地模型（不管是否启用）
            discovered_models = self.db.query(LocalModelRegistry).filter(
                LocalModelRegistry.scan_status == 'discovered'
            ).all()
            
            registered_count = 0
            
            for registry_entry in discovered_models:
                # 检查是否已经有对应的model_info记录
                existing = self.db.query(ModelInfo).filter(
                    ModelInfo.user_id == user_id,
                    ModelInfo.extra_metadata['registry_id'].astext == str(registry_entry.id)
                ).first()
                
                if existing:
                    continue
                
                # 判断是否为有效LLM（自动过滤无效模型）
                is_valid_llm = self._is_valid_llm_model(registry_entry.model_name, registry_entry.model_path)
                
                # 自动注册本地模型（默认启用有效LLM，禁用无效模型）
                model_id = await self.register_local_model(
                    user_id, 
                    registry_entry.id,
                    auto_enable=is_valid_llm  # 有效LLM自动启用
                )
                if model_id:
                    registered_count += 1
                    if is_valid_llm:
                        logger.info(f"✅ 注册并启用: {registry_entry.model_name}")
                    else:
                        logger.info(f"⚠️  注册但禁用: {registry_entry.model_name} (非LLM或无效)")
            
            return registered_count
            
        except Exception as e:
            logger.error(f"自动注册本地模型失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return 0
    
    def _is_valid_llm_model(self, model_name: str, model_path: str) -> bool:
        """判断是否为有效的LLM模型"""
        # 无效路径标记
        if '.no_exist' in model_path or '.no_exist' in model_name:
            return False
        
        # 非LLM模型（语音、图像等）
        invalid_patterns = [
            'wav2vec',  # 语音模型
            'whisper',  # 语音模型
            'clip',  # 图像模型
            'vit-',  # 图像模型
            'DialoGPT',  # 旧对话模型
        ]
        
        model_name_lower = model_name.lower()
        for pattern in invalid_patterns:
            if pattern.lower() in model_name_lower:
                return False
        
        # 有效的LLM模型特征
        valid_patterns = [
            'qwen',
            'llama',
            'gpt',
            'chatglm',
            'baichuan',
            'internlm',
            'mistral',
            'mixtral',
        ]
        
        for pattern in valid_patterns:
            if pattern.lower() in model_name_lower:
                return True
        
        # 默认启用（保守策略）
        return True
    
    async def _auto_register_local_models(self, found_models: List[Dict[str, Any]]) -> int:
        """自动注册发现的本地模型"""
        try:
            registered_count = 0
            
            for model_info in found_models:
                # 检查是否已经注册过
                existing = self.db.query(LocalModelRegistry).filter(
                    LocalModelRegistry.model_path == model_info['path']
                ).first()
                
                if existing:
                    continue  # 已经注册过，跳过
                
                # 创建注册表记录
                registry_entry = LocalModelRegistry(
                    model_path=model_info['path'],
                    model_name=model_info['name'],
                    model_type=model_info.get('detected_info', {}).get('model_type', 'unknown'),
                    file_size=model_info['size'],
                    file_count=model_info['file_count'],
                    scan_status='discovered',
                    detected_info=model_info.get('detected_info', {})
                )
                
                self.db.add(registry_entry)
                registered_count += 1
            
            if registered_count > 0:
                self.db.commit()
                logger.info(f"自动注册了 {registered_count} 个本地模型")
            
            return registered_count
            
        except Exception as e:
            logger.error(f"自动注册本地模型失败: {e}")
            self.db.rollback()
            return 0
    
    async def refresh_model_display_names(self, user_id: str) -> int:
        """刷新模型显示名称，从原始配置中获取真实名称"""
        try:
            updated_count = 0
            
            # 获取所有用户的模型
            models = self.db.query(ModelInfo).filter(
                ModelInfo.user_id == user_id,
                ModelInfo.is_active == True
            ).all()
            
            for model in models:
                updated = False
                
                # 如果是从用户配置同步的模型
                if model.extra_metadata and model.extra_metadata.get('sync_source') == 'user_config':
                    user_config_id = model.extra_metadata.get('user_config_id')
                    if user_config_id:
                        user_config = self.db.query(UserModelConfig).filter(
                            UserModelConfig.id == user_config_id
                        ).first()
                        
                        if user_config and user_config.model_name:
                            # 更新为真实的模型名称
                            model.display_name = user_config.model_name
                            model.model_name = user_config.model_name
                            # 保存用户自定义名称到元数据
                            if not model.extra_metadata:
                                model.extra_metadata = {}
                            model.extra_metadata['user_custom_name'] = user_config.name
                            logger.info(f"更新模型 {model.id}: {user_config.name} -> {user_config.model_name}")
                            updated = True
                
                # 如果是从模型配置同步的模型
                elif model.extra_metadata and model.extra_metadata.get('sync_source') == 'model_config':
                    model_config_id = model.extra_metadata.get('model_config_id')
                    if model_config_id:
                        model_config = self.db.query(ModelConfig).filter(
                            ModelConfig.id == model_config_id
                        ).first()
                        
                        if model_config:
                            # 使用模型配置中的名称
                            real_name = model_config.model_name or model_config.model_id
                            if real_name and real_name != model.display_name:
                                model.display_name = real_name
                                model.model_name = real_name
                                updated = True
                
                if updated:
                    model.updated_at = datetime.utcnow()
                    updated_count += 1
            
            if updated_count > 0:
                self.db.commit()
                logger.info(f"更新了 {updated_count} 个模型的显示名称")
            
            return updated_count
            
        except Exception as e:
            logger.error(f"刷新模型显示名称失败: {e}")
            self.db.rollback()
            return 0

    # ==================== 翻译模型管理 ====================
    
    async def get_translation_models(self, user_id: str) -> List[Dict[str, Any]]:
        """获取翻译专用模型列表"""
        try:
            translation_models = self.db.query(ModelInfo).filter(
                ModelInfo.user_id == user_id,
                ModelInfo.is_active == True,
                ModelInfo.is_translation_model == True,
                ModelInfo.status == 'available'
            ).order_by(
                desc(ModelInfo.translation_priority),
                desc(ModelInfo.usage_count)
            ).all()
            
            return [self._serialize_model_info(model) for model in translation_models]
            
        except Exception as e:
            logger.error(f"获取翻译模型失败: {e}")
            return []
    
    async def get_best_translation_model(self, user_id: str) -> Optional[Dict[str, Any]]:
        """获取最佳翻译模型"""
        try:
            # 优先获取翻译专用模型
            translation_model = self.db.query(ModelInfo).filter(
                ModelInfo.user_id == user_id,
                ModelInfo.is_active == True,
                ModelInfo.is_translation_model == True,
                ModelInfo.status == 'available'
            ).order_by(
                desc(ModelInfo.translation_priority),
                desc(ModelInfo.usage_count)
            ).first()
            
            if translation_model:
                return self._serialize_model_info(translation_model)
            
            # 如果没有翻译专用模型，获取支持对话的模型
            chat_model = self.db.query(ModelInfo).filter(
                ModelInfo.user_id == user_id,
                ModelInfo.is_active == True,
                ModelInfo.status == 'available',
                ModelInfo.capabilities.contains(['chat'])
            ).order_by(
                desc(ModelInfo.usage_count),
                desc(ModelInfo.quality_rating).nullslast()
            ).first()
            
            if chat_model:
                return self._serialize_model_info(chat_model)
            
            return None
            
        except Exception as e:
            logger.error(f"获取最佳翻译模型失败: {e}")
            return None
    
    async def set_translation_model(
        self, 
        user_id: str, 
        model_id: int, 
        is_translation: bool = True,
        priority: int = 50
    ) -> bool:
        """设置模型为翻译专用模型"""
        try:
            model = self.db.query(ModelInfo).filter(
                ModelInfo.user_id == user_id,
                ModelInfo.id == model_id,
                ModelInfo.is_active == True
            ).first()
            
            if not model:
                return False
            
            model.is_translation_model = is_translation
            model.translation_priority = priority if is_translation else 0
            model.updated_at = datetime.utcnow()
            
            self.db.commit()
            return True
            
        except Exception as e:
            logger.error(f"设置翻译模型失败: {e}")
            self.db.rollback()
            return False
    
    async def toggle_local_model_enabled(self, registry_id: int, is_enabled: bool, user_id: str) -> bool:
        """切换本地模型的启用/禁用状态"""
        try:
            logger.info(f"🔄 切换本地模型状态: registry_id={registry_id}, is_enabled={is_enabled}, user_id={user_id}")
            
            # 获取注册表条目
            registry_entry = self.db.query(LocalModelRegistry).filter(
                LocalModelRegistry.id == registry_id
            ).first()
            
            if not registry_entry:
                logger.warning(f"⚠️ 找不到registry_id={registry_id}的注册表条目")
                return False
            
            logger.info(f"✅ 找到注册表条目: {registry_entry.model_name}")
            
            # 更新启用状态
            registry_entry.is_enabled = is_enabled
            logger.info(f"📝 更新is_enabled字段为: {is_enabled}")
            
            if is_enabled:
                # 启用：如果没有对应的model_info记录，则创建
                # 查找所有该用户的模型，然后在Python中筛选
                all_user_models = self.db.query(ModelInfo).filter(
                    ModelInfo.user_id == user_id
                ).all()
                
                existing_model = None
                for model in all_user_models:
                    if (model.extra_metadata and 
                        isinstance(model.extra_metadata, dict) and 
                        str(model.extra_metadata.get('registry_id')) == str(registry_id)):
                        existing_model = model
                        break
                
                if not existing_model:
                    # 注册本地模型
                    logger.info(f"🆕 创建新的模型记录")
                    model_id = await self.register_local_model(user_id, registry_id)
                    if not model_id:
                        logger.error(f"❌ 注册本地模型失败")
                        return False
                else:
                    # 重新激活已存在的模型
                    logger.info(f"♻️ 重新激活已存在的模型: {existing_model.model_name}")
                    existing_model.is_active = True
                    existing_model.updated_at = datetime.utcnow()
            else:
                # 禁用：将对应的model_info记录设为不活跃
                # 查找所有该用户的模型，然后在Python中筛选
                all_user_models = self.db.query(ModelInfo).filter(
                    ModelInfo.user_id == user_id
                ).all()
                
                existing_model = None
                for model in all_user_models:
                    if (model.extra_metadata and 
                        isinstance(model.extra_metadata, dict) and 
                        str(model.extra_metadata.get('registry_id')) == str(registry_id)):
                        existing_model = model
                        break
                
                if existing_model:
                    logger.info(f"🔇 禁用模型: {existing_model.model_name}")
                    existing_model.is_active = False
                    existing_model.updated_at = datetime.utcnow()
                else:
                    logger.info(f"ℹ️ 没有找到对应的model_info记录")
            
            self.db.commit()
            logger.info(f"✅ 成功切换模型状态，已提交到数据库")
            return True
            
        except Exception as e:
            logger.error(f"❌ 切换模型启用状态失败: {e}")
            logger.exception("详细错误信息:")
            self.db.rollback()
            return False
    
    async def batch_toggle_local_models(self, registry_ids: List[int], is_enabled: bool, user_id: str) -> Dict[str, int]:
        """批量切换本地模型的启用状态"""
        try:
            success_count = 0
            failed_count = 0
            
            for registry_id in registry_ids:
                success = await self.toggle_local_model_enabled(registry_id, is_enabled, user_id)
                if success:
                    success_count += 1
                else:
                    failed_count += 1
            
            return {
                'success_count': success_count,
                'failed_count': failed_count
            }
            
        except Exception as e:
            logger.error(f"批量切换模型状态失败: {e}")
            return {'success_count': 0, 'failed_count': len(registry_ids)}
    
    # ==================== 模型复制功能 ====================
    
    async def copy_model(
        self,
        user_id: str,
        source_model_id: int,
        new_model_name: str,
        new_display_name: str,
        notes: Optional[str] = None
    ) -> Optional[int]:
        """复制模型"""
        try:
            # 获取源模型
            source_model = self.db.query(ModelInfo).filter(
                ModelInfo.id == source_model_id,
                ModelInfo.user_id == user_id,
                ModelInfo.is_active == True
            ).first()
            
            if not source_model:
                return None
            
            # 检查模型名称是否重复
            existing_model = self.db.query(ModelInfo).filter(
                ModelInfo.user_id == user_id,
                ModelInfo.model_name == new_model_name,
                ModelInfo.is_active == True
            ).first()
            
            if existing_model:
                raise ValueError(f"模型名称 '{new_model_name}' 已存在，请使用其他名称")
            
            # 创建新模型记录
            new_model = ModelInfo(
                user_id=user_id,
                model_id=f"copy_{source_model.model_id}_{int(datetime.utcnow().timestamp())}",
                model_name=new_model_name,
                display_name=new_display_name,
                model_type=source_model.model_type,
                model_source=source_model.model_source,
                model_family=source_model.model_family,
                model_size=source_model.model_size,
                parameter_count=source_model.parameter_count,
                model_version=source_model.model_version,
                model_path=source_model.model_path,
                api_url=source_model.api_url,
                api_key=source_model.api_key,
                api_provider=source_model.api_provider,
                status='available',
                download_progress=source_model.download_progress,
                file_size=source_model.file_size,
                disk_usage=source_model.disk_usage,
                supported_context_length=source_model.supported_context_length,
                max_tokens=source_model.max_tokens,
                inference_speed=source_model.inference_speed,
                memory_usage=source_model.memory_usage,
                capabilities=source_model.capabilities,
                languages=source_model.languages,
                tags=source_model.tags,
                usage_count=0,  # 新复制的模型使用次数重置为0
                last_used_at=None,  # 新复制的模型最后使用时间重置
                benchmark_scores=source_model.benchmark_scores,
                quality_rating=source_model.quality_rating,
                is_active=True,
                is_favorite=False,  # 新复制的模型默认不收藏
                notes=notes or f"复制自: {source_model.display_name or source_model.model_name}",
                extra_metadata={
                    'copied_from': source_model_id,
                    'copied_at': datetime.utcnow().isoformat(),
                    'original_model_name': source_model.model_name,
                    'original_display_name': source_model.display_name
                }
            )
            
            self.db.add(new_model)
            self.db.flush()  # 获取ID
            
            self.db.commit()
            
            logger.info(f"成功复制模型: {source_model.model_name} -> {new_model_name}")
            return new_model.id
            
        except ValueError:
            # 重新抛出验证错误
            raise
        except Exception as e:
            logger.error(f"复制模型失败: {e}")
            self.db.rollback()
            return None