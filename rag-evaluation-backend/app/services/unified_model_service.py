"""
统一模型服务 - 为所有评测功能提供模型管理
"""
import logging
from typing import List, Dict, Optional, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.models.model_management import ModelInfo
from app.models.user_config import UserModelConfig
from app.models.model_config import ModelConfig

logger = logging.getLogger(__name__)


class UnifiedModelService:
    """统一模型服务 - 为评测系统提供模型管理"""
    
    def __init__(self, db: Session):
        self.db = db
    
    async def get_available_models(
        self, 
        user_id: str, 
        model_types: Optional[List[str]] = None,
        capabilities: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        获取用户可用的模型列表
        
        Args:
            user_id: 用户ID
            model_types: 模型类型过滤 ['local', 'api', 'cloud']
            capabilities: 能力过滤 ['chat', 'code', 'math', 'multimodal']
        
        Returns:
            可用模型列表
        """
        try:
            query = self.db.query(ModelInfo).filter(
                ModelInfo.user_id == user_id,
                ModelInfo.is_active == True,
                ModelInfo.status == 'available'
            )
            
            # 类型过滤
            if model_types:
                query = query.filter(ModelInfo.model_type.in_(model_types))
            
            # 能力过滤
            if capabilities:
                for capability in capabilities:
                    query = query.filter(
                        ModelInfo.capabilities.contains([capability])
                    )
            
            models = query.order_by(ModelInfo.usage_count.desc()).all()
            
            return [self._serialize_model_for_eval(model) for model in models]
            
        except Exception as e:
            logger.error(f"获取可用模型失败: {e}")
            return []
    
    async def get_model_by_id(self, user_id: str, model_id: str) -> Optional[Dict[str, Any]]:
        """根据模型ID获取模型信息"""
        try:
            model = self.db.query(ModelInfo).filter(
                ModelInfo.user_id == user_id,
                ModelInfo.model_id == model_id,
                ModelInfo.is_active == True
            ).first()
            
            if model:
                return self._serialize_model_for_eval(model)
            
            return None
            
        except Exception as e:
            logger.error(f"获取模型信息失败: {e}")
            return None
    
    async def get_chat_models(self, user_id: str) -> List[Dict[str, Any]]:
        """获取支持对话的模型"""
        return await self.get_available_models(
            user_id, 
            capabilities=['chat']
        )
    
    async def get_code_models(self, user_id: str) -> List[Dict[str, Any]]:
        """获取支持代码生成的模型"""
        return await self.get_available_models(
            user_id, 
            capabilities=['code']
        )
    
    async def get_multimodal_models(self, user_id: str) -> List[Dict[str, Any]]:
        """获取多模态模型"""
        return await self.get_available_models(
            user_id, 
            capabilities=['multimodal']
        )
    
    async def get_local_models(self, user_id: str) -> List[Dict[str, Any]]:
        """获取本地模型"""
        return await self.get_available_models(
            user_id, 
            model_types=['local']
        )
    
    async def get_api_models(self, user_id: str) -> List[Dict[str, Any]]:
        """获取API模型"""
        return await self.get_available_models(
            user_id, 
            model_types=['api']
        )
    
    async def get_models_for_comparison(self, user_id: str) -> List[Dict[str, Any]]:
        """获取适合对比的模型（按使用次数排序）"""
        try:
            models = self.db.query(ModelInfo).filter(
                ModelInfo.user_id == user_id,
                ModelInfo.is_active == True,
                ModelInfo.status == 'available'
            ).order_by(
                ModelInfo.usage_count.desc(),
                ModelInfo.quality_rating.desc().nullslast()
            ).limit(20).all()
            
            return [self._serialize_model_for_eval(model) for model in models]
            
        except Exception as e:
            logger.error(f"获取对比模型失败: {e}")
            return []
    
    async def get_arena_models(self, user_id: str) -> List[Dict[str, Any]]:
        """获取Arena对战模型"""
        try:
            # 优先获取支持对话且质量评分较高的模型
            models = self.db.query(ModelInfo).filter(
                ModelInfo.user_id == user_id,
                ModelInfo.is_active == True,
                ModelInfo.status == 'available',
                or_(
                    ModelInfo.capabilities.contains(['chat']),
                    ModelInfo.model_type == 'api'  # API模型通常支持对话
                )
            ).order_by(
                ModelInfo.quality_rating.desc().nullslast(),
                ModelInfo.usage_count.desc()
            ).all()
            
            arena_models = []
            for model in models:
                arena_model = self._serialize_model_for_eval(model)
                # 添加Arena特有字段
                arena_model.update({
                    'rating': model.quality_rating or 1500,  # ELO评分，默认1500
                    'battles': 0,  # 对战次数，需要从其他表获取
                    'win_rate': 0.5  # 胜率，需要从其他表计算
                })
                arena_models.append(arena_model)
            
            return arena_models
            
        except Exception as e:
            logger.error(f"获取Arena模型失败: {e}")
            return []
    
    async def record_model_usage(
        self, 
        user_id: str, 
        model_id: str, 
        usage_type: str = 'eval',
        usage_data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """记录模型使用"""
        try:
            model = self.db.query(ModelInfo).filter(
                ModelInfo.user_id == user_id,
                ModelInfo.model_id == model_id
            ).first()
            
            if model:
                model.usage_count += 1
                from datetime import datetime
                model.last_used_at = datetime.utcnow()
                self.db.commit()
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"记录模型使用失败: {e}")
            self.db.rollback()
            return False
    
    def _serialize_model_for_eval(self, model: ModelInfo) -> Dict[str, Any]:
        """序列化模型信息用于评测"""
        return {
            'id': model.model_id,
            'name': model.model_name,
            'display_name': model.display_name or model.model_name,
            'model_type': model.model_type,
            'model_family': model.model_family,
            'model_size': model.model_size,
            'capabilities': model.capabilities or [],
            'languages': model.languages or [],
            'tags': model.tags or [],
            'status': model.status,
            'usage_count': model.usage_count,
            'quality_rating': model.quality_rating,
            'is_favorite': model.is_favorite,
            
            # 评测相关配置
            'config': {
                'model_path': model.model_path,
                'api_url': model.api_url,
                'api_key': model.api_key,
                'api_provider': model.api_provider,
                'supported_context_length': model.supported_context_length,
                'max_tokens': model.max_tokens,
                'extra_metadata': model.extra_metadata or {}
            }
        }
    
    async def get_legacy_models(self, user_id: str) -> List[Dict[str, Any]]:
        """获取旧版配置的模型（兼容性）"""
        try:
            legacy_models = []
            
            # 从用户配置获取
            user_configs = self.db.query(UserModelConfig).filter(
                UserModelConfig.user_id == user_id,
                UserModelConfig.is_active == True
            ).all()
            
            for config in user_configs:
                legacy_models.append({
                    'id': f"user_config_{config.id}",
                    'name': config.model_name,
                    'display_name': config.name,
                    'model_type': 'api',
                    'config': {
                        'api_url': config.base_url,
                        'api_key': config.api_key,
                        'api_provider': config.type,
                        'extra_metadata': config.additional_params or {}
                    }
                })
            
            # 从系统配置获取
            model_configs = self.db.query(ModelConfig).filter(
                ModelConfig.user_id == user_id,
                ModelConfig.is_active == True
            ).all()
            
            for config in model_configs:
                legacy_models.append({
                    'id': f"model_config_{config.id}",
                    'name': config.model_name or config.model_id,
                    'display_name': config.model_name or config.model_id,
                    'model_type': 'local' if config.model_path else 'api',
                    'config': {
                        'model_path': config.model_path,
                        'api_url': config.api_url,
                        'api_key': config.api_key,
                        'extra_metadata': {
                            'model_args': config.model_args,
                            'generation_config': config.generation_config
                        }
                    }
                })
            
            return legacy_models
            
        except Exception as e:
            logger.error(f"获取旧版模型配置失败: {e}")
            return []
    
    async def get_all_available_models(self, user_id: str) -> List[Dict[str, Any]]:
        """获取所有可用模型（包括新版和旧版）"""
        try:
            # 获取新版统一管理的模型
            unified_models = await self.get_available_models(user_id)
            
            # 获取旧版配置的模型（如果新版没有对应模型）
            legacy_models = await self.get_legacy_models(user_id)
            
            # 合并去重
            all_models = unified_models.copy()
            unified_model_ids = {model['id'] for model in unified_models}
            
            for legacy_model in legacy_models:
                if legacy_model['id'] not in unified_model_ids:
                    all_models.append(legacy_model)
            
            return all_models
            
        except Exception as e:
            logger.error(f"获取所有可用模型失败: {e}")
            return []
    
    async def get_public_models(self) -> List[Dict[str, Any]]:
        """
        获取公共可用的模型（不需要认证）
        返回所有用户共享的模型配置
        这些是已经在数据库中配置好的、状态为available的模型
        """
        try:
            # 查询所有活跃且可用的模型（不限制用户）
            # 优先返回使用次数较多的模型，说明这些模型配置是可用的
            public_models = self.db.query(ModelInfo).filter(
                ModelInfo.is_active == True,
                ModelInfo.status == 'available'
            ).order_by(
                ModelInfo.usage_count.desc(),
                ModelInfo.quality_rating.desc().nullslast()
            ).limit(50).all()  # 限制返回前50个最常用的模型
            
            if public_models:
                logger.info(f"找到 {len(public_models)} 个公共模型")
                return [self._serialize_model_for_eval(model) for model in public_models]
            
            # 如果没有找到ModelInfo中的模型，尝试从ModelConfig中获取
            logger.info("ModelInfo中没有模型，尝试从ModelConfig获取")
            model_configs = self.db.query(ModelConfig).filter(
                ModelConfig.is_active == True
            ).limit(20).all()
            
            if model_configs:
                logger.info(f"从ModelConfig找到 {len(model_configs)} 个模型")
                return [self._serialize_model_config(config) for config in model_configs]
            
            logger.warning("数据库中没有找到任何公共模型")
            return []
            
        except Exception as e:
            logger.error(f"获取公共模型失败: {e}")
            return []
    
    def _serialize_model_config(self, config: ModelConfig) -> Dict[str, Any]:
        """序列化ModelConfig为统一格式"""
        return {
            'id': config.model_id,
            'name': config.model_name or config.model_id,
            'display_name': config.model_name or config.model_id,
            'model_type': config.model_type or ('local' if config.model_path else 'api'),
            'model_family': 'unknown',
            'model_size': 'unknown',
            'capabilities': ['chat'],  # 默认能力
            'languages': ['zh', 'en'],
            'tags': [],
            'status': 'available',
            'usage_count': 0,
            'quality_rating': None,
            'is_favorite': False,
            'config': {
                'model_path': config.model_path,
                'api_url': config.api_url,
                'api_key': config.api_key if config.api_key else '',
                'api_provider': 'openai',
                'supported_context_length': 4096,
                'max_tokens': 2048,
                'extra_metadata': {
                    'model_args': config.model_args or {},
                    'generation_config': config.generation_config or {}
                }
            }
        }