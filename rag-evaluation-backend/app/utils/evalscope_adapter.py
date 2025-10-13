"""
EvalScope API适配器
统一处理API配置、模型ID解析等转换逻辑
"""
from typing import Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
from app.models.user_config import UserModelConfig
from app.models.model_management import ModelInfo


class EvalScopeAPIAdapter:
    """EvalScope API配置适配器"""
    
    @staticmethod
    def parse_model_id(
        model_id: str,
        extra_metadata: Optional[Dict] = None,
        db: Optional[Session] = None
    ) -> Tuple[str, str, Optional[Dict]]:
        """
        解析模型ID，返回真实的模型名称和评测类型
        
        Args:
            model_id: 原始模型ID（可能是user_config_xxx格式）
            extra_metadata: 任务的额外元数据
            db: 数据库会话
            
        Returns:
            (真实模型名, 评测类型, API配置字典)
        """
        # 1. 处理空或无效的模型ID
        if not model_id or model_id.strip() == '' or model_id == 'model':
            # 尝试从extra_metadata中获取
            if extra_metadata and extra_metadata.get('user_model_config'):
                user_config = extra_metadata['user_model_config']
                if user_config.get('model_name'):
                    model_name = user_config['model_name']
                    eval_type = 'openai_api'
                    api_config = {
                        'api_key': user_config.get('api_key'),
                        'api_url': user_config.get('base_url')
                    }
                    return model_name, eval_type, api_config
            
            # 如果都没有，抛出错误
            raise ValueError("模型ID无效且无法从配置中提取")
        
        # 2. 处理用户配置格式 (user_config_xxx)
        if model_id.startswith('user_config_'):
            # 优先从extra_metadata中获取
            if extra_metadata and extra_metadata.get('user_model_config'):
                user_config = extra_metadata['user_model_config']
                if user_config.get('model_name'):
                    model_name = user_config['model_name']
                    eval_type = 'openai_api'
                    api_config = {
                        'api_key': user_config.get('api_key'),
                        'api_url': user_config.get('base_url')
                    }
                    return model_name, eval_type, api_config
            
            # 尝试从数据库查询
            if db:
                try:
                    config_id = model_id.replace('user_config_', '')
                    user_config_record = db.query(UserModelConfig).filter(
                        UserModelConfig.id == config_id,
                        UserModelConfig.is_active == True
                    ).first()
                    
                    if user_config_record:
                        model_name = user_config_record.model_name
                        eval_type = 'openai_api'
                        api_config = {
                            'api_key': user_config_record.api_key,
                            'api_url': user_config_record.base_url
                        }
                        return model_name, eval_type, api_config
                except Exception as e:
                    print(f"从数据库查询用户配置失败: {e}")
            
            # 如果都失败了，抛出错误
            raise ValueError(f"无法解析用户配置模型ID: {model_id}")
        
        # 3. 处理config:开头的格式
        if model_id.startswith('config:'):
            config_name = model_id.replace('config:', '')
            # 尝试从extra_metadata中获取
            if extra_metadata and extra_metadata.get('user_model_config'):
                user_config = extra_metadata['user_model_config']
                if user_config.get('model_name'):
                    model_name = user_config['model_name']
                    eval_type = 'openai_api'
                    api_config = {
                        'api_key': user_config.get('api_key'),
                        'api_url': user_config.get('base_url')
                    }
                    return model_name, eval_type, api_config
            
            raise ValueError(f"无法解析配置格式模型ID: {model_id}")
        
        # 4. 处理普通模型ID - 判断是本地模型还是API模型
        eval_type, api_config = EvalScopeAPIAdapter._detect_model_type(
            model_id, extra_metadata
        )
        
        # 如果是API模型但没有配置，尝试从数据库查询用户配置
        if eval_type == 'openai_api' and not api_config and db:
            try:
                user_config_record = db.query(UserModelConfig).filter(
                    UserModelConfig.model_name == model_id,
                    UserModelConfig.is_active == True
                ).first()
                
                if user_config_record:
                    api_config = {
                        'api_key': user_config_record.api_key,
                        'api_url': user_config_record.base_url
                    }
                    # 将用户配置保存到extra_metadata中
                    if extra_metadata is not None:
                        extra_metadata['user_model_config'] = {
                            'model_name': user_config_record.model_name,
                            'api_key': user_config_record.api_key,
                            'base_url': user_config_record.base_url,
                            'additional_params': user_config_record.additional_params
                        }
            except Exception as e:
                print(f"从数据库查询用户配置失败: {e}")
        
        return model_id, eval_type, api_config
    
    @staticmethod
    def _detect_model_type(
        model_id: str,
        extra_metadata: Optional[Dict] = None
    ) -> Tuple[str, Optional[Dict]]:
        """
        检测模型类型（本地模型或API模型）
        
        Returns:
            (评测类型, API配置或None)
        """
        # API模型的特征标识
        api_patterns = [
            'gpt-', 'claude-', 'gemini-',
            'qwen-plus', 'qwen-max', 'qwen-turbo', 'qwen3-',
            'deepseek-', 'moonshot-'
        ]
        
        model_lower = model_id.lower()
        
        # 检查是否匹配API模型特征
        is_api_model = any(pattern in model_lower for pattern in api_patterns)
        
        if is_api_model:
            # API模型，尝试获取API配置
            api_config = None
            if extra_metadata and extra_metadata.get('user_model_config'):
                user_config = extra_metadata['user_model_config']
                api_config = {
                    'api_key': user_config.get('api_key'),
                    'api_url': user_config.get('base_url')
                }
            
            return 'openai_api', api_config
        
        # 本地模型（通常包含 / 分隔符）
        return 'llm_ckpt', None
    
    @staticmethod
    def build_task_config_params(
        model_name: str,
        datasets: list,
        eval_type: str,
        work_dir: str,
        api_config: Optional[Dict] = None,
        model_args: Optional[Dict] = None,
        generation_config: Optional[Dict] = None,
        dataset_args: Optional[Dict] = None,
        limit: Optional[int] = None,
        use_cache: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        构建EvalScope TaskConfig参数
        
        Args:
            model_name: 模型名称
            datasets: 数据集列表
            eval_type: 评测类型
            work_dir: 工作目录
            api_config: API配置（包含api_key和api_url）
            model_args: 模型参数
            generation_config: 生成配置
            dataset_args: 数据集参数
            limit: 样本数量限制
            
        Returns:
            TaskConfig参数字典
        """
        config_params = {
            'model': model_name,
            'datasets': datasets,
            'eval_type': eval_type,
            'work_dir': work_dir
        }
        
        # 添加use_cache参数（如果提供）
        if use_cache is not None:
            config_params['use_cache'] = use_cache
        
        # 添加limit参数
        if limit is not None:
            config_params['limit'] = limit
        
        # 添加API配置（如果是API模型）
        if eval_type == 'openai_api' and api_config:
            # EvalScope TaskConfig使用api_url字段
            # 验证必需的API配置
            if not api_config.get('api_url'):
                raise ValueError("API模型配置缺少api_url")
            if not api_config.get('api_key'):
                raise ValueError("API模型配置缺少api_key")
            config_params['api_url'] = api_config['api_url']
            config_params['api_key'] = api_config['api_key']
        
        # 添加模型参数
        if model_args:
            config_params['model_args'] = model_args
        
        # 添加生成配置
        if generation_config:
            config_params['generation_config'] = generation_config
        
        # 添加数据集参数
        if dataset_args:
            # 处理数据集级别的limit
            processed_dataset_args = {}
            for dataset in datasets:
                if dataset in dataset_args:
                    processed_dataset_args[dataset] = dataset_args[dataset]
                elif limit is not None:
                    # 如果没有指定数据集参数但有全局limit，添加limit
                    processed_dataset_args[dataset] = {'limit': limit}
            
            if processed_dataset_args:
                config_params['dataset_args'] = processed_dataset_args
        
        return config_params
    
    @staticmethod
    def validate_api_config(api_config: Optional[Dict]) -> bool:
        """
        验证API配置是否完整
        
        Args:
            api_config: API配置字典
            
        Returns:
            是否有效
        """
        if not api_config:
            return False
        
        # 必须有api_key
        if not api_config.get('api_key'):
            return False
        
        # api_url可以为空（会使用默认值）
        return True
    
    @staticmethod
    def extract_api_config_from_metadata(
        extra_metadata: Optional[Dict]
    ) -> Optional[Dict]:
        """
        从extra_metadata中提取API配置
        
        Args:
            extra_metadata: 任务的额外元数据
            
        Returns:
            API配置字典或None
        """
        if not extra_metadata:
            return None
        
        user_config = extra_metadata.get('user_model_config')
        if not user_config:
            return None
        
        return {
            'api_key': user_config.get('api_key'),
            'api_url': user_config.get('base_url', 'https://api.openai.com/v1'),
            'model_name': user_config.get('model_name')
        }
    
    @staticmethod
    def format_error_message(error: Exception, context: str = "") -> str:
        """
        格式化错误消息
        
        Args:
            error: 异常对象
            context: 上下文信息
            
        Returns:
            格式化的错误消息
        """
        error_type = type(error).__name__
        error_msg = str(error)
        
        if context:
            return f"[{context}] {error_type}: {error_msg}"
        
        return f"{error_type}: {error_msg}"


class ModelIDResolver:
    """模型ID解析器 - 用于在任务创建时就解析模型ID"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def resolve(
        self,
        model_id: str,
        user_model_config: Optional[Dict] = None
    ) -> Tuple[str, Dict[str, Any]]:
        """
        解析模型ID，返回真实模型名和完整元数据
        
        Args:
            model_id: 原始模型ID
            user_model_config: 用户模型配置
            
        Returns:
            (真实模型名, 完整的extra_metadata)
        """
        extra_metadata = {}
        
        # 保存原始模型ID用于追溯
        extra_metadata['original_model_id'] = model_id
        
        # 如果提供了用户配置，保存它
        if user_model_config:
            extra_metadata['user_model_config'] = user_model_config
            print(f"DEBUG: ModelIDResolver保存user_model_config: {user_model_config}")
        
        # 使用适配器解析
        try:
            real_model_name, eval_type, api_config = EvalScopeAPIAdapter.parse_model_id(
                model_id=model_id,
                extra_metadata=extra_metadata,
                db=self.db
            )
            
            # 保存解析结果
            extra_metadata['resolved_model_name'] = real_model_name
            extra_metadata['eval_type'] = eval_type
            
            return real_model_name, extra_metadata
            
        except ValueError as e:
            # 解析失败，返回原始ID和错误信息
            extra_metadata['resolution_error'] = str(e)
            return model_id, extra_metadata

