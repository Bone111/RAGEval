"""
Benchmark注册表 - 从EvalScope官方注册表动态获取benchmark列表
"""
from typing import List, Dict, Any, Optional
import json
import logging
import sys
import os
from datetime import datetime, timedelta

# 添加EvalScope路径到系统路径（如果需要）
# 从环境变量获取，如果未设置则不添加（假设evalscope已安装在环境中）
evalscope_path = os.getenv('EVALSCOPE_PATH')
if evalscope_path and os.path.exists(evalscope_path):
    sys.path.insert(0, evalscope_path)

logger = logging.getLogger(__name__)


class BenchmarkRegistry:
    """Benchmark注册表，从EvalScope官方注册表动态获取benchmark"""
    
    # 官方文档URL
    EVALSCOPE_DOCS_URL = "https://evalscope.readthedocs.io/en/latest/"
    
    # 缓存配置
    _cache = {}
    _cache_timestamp = None
    _cache_ttl = timedelta(hours=1)  # 缓存1小时
    
    # EvalScope官方支持的LLM benchmarks（根据文档整理）
    OFFICIAL_LLM_BENCHMARKS = {
        # 通用能力
        'mmlu': {'display_name': 'MMLU', 'category': '通用能力', 'language': 'English', 'num_samples': 14042, 'file_size': '89 MB', 'num_subsets': 57},
        'cmmlu': {'display_name': 'CMMLU', 'category': '中文能力', 'language': 'Chinese', 'num_samples': 11528, 'file_size': '76 MB', 'num_subsets': 67},
        'ceval': {'display_name': 'C-Eval', 'category': '中文能力', 'language': 'Chinese', 'num_samples': 13948, 'file_size': '92 MB', 'num_subsets': 52},
        
        # 数学推理
        'gsm8k': {'display_name': 'GSM8K', 'category': '数学推理', 'language': 'English', 'num_samples': 1319, 'file_size': '12 MB', 'num_subsets': 1},
        'competition_math': {'display_name': 'MATH', 'category': '数学推理', 'language': 'English', 'num_samples': 5000, 'file_size': '45 MB', 'num_subsets': 5},
        
        # 科学推理
        'arc': {'display_name': 'ARC', 'category': '科学推理', 'language': 'English', 'num_samples': 7787, 'file_size': '25 MB', 'num_subsets': 2},
        'arc_challenge': {'display_name': 'ARC-Challenge', 'category': '科学推理', 'language': 'English', 'num_samples': 1172, 'file_size': '12 MB', 'num_subsets': 1},
        
        # 代码生成
        'humaneval': {'display_name': 'HumanEval', 'category': '代码生成', 'language': 'English', 'num_samples': 164, 'file_size': '3 MB', 'num_subsets': 1},
        
        # 常识推理
        'hellaswag': {'display_name': 'HellaSwag', 'category': '常识推理', 'language': 'English', 'num_samples': 10042, 'file_size': '68 MB', 'num_subsets': 1},
        'winogrande': {'display_name': 'WinoGrande', 'category': '常识推理', 'language': 'English', 'num_samples': 1767, 'file_size': '5 MB', 'num_subsets': 1},
        
        # 困难推理
        'bbh': {'display_name': 'BBH', 'category': '困难推理', 'language': 'English', 'num_samples': 6511, 'file_size': '59 MB', 'num_subsets': 27},
        'drop': {'display_name': 'DROP', 'category': '困难推理', 'language': 'English', 'num_samples': 9536, 'file_size': '125 MB', 'num_subsets': 1},
        
        # 阅读理解
        'race': {'display_name': 'RACE', 'category': '阅读理解', 'language': 'English', 'num_samples': 25047, 'file_size': '156 MB', 'num_subsets': 2},
        
        # 对话与指令
        'alpaca_eval': {'display_name': 'AlpacaEval', 'category': '对话能力', 'language': 'English', 'num_samples': 805, 'file_size': '15 MB', 'num_subsets': 1},
        
        # 安全与对齐
    }
    
    # VLM benchmarks
    OFFICIAL_VLM_BENCHMARKS = {
        'mmmu': {'display_name': 'MMMU', 'category': '多模态理解', 'language': 'English', 'num_samples': 11500, 'file_size': '1.5 GB', 'num_subsets': 30},
    }
    
    @classmethod
    def _load_evalscope_benchmarks(cls) -> Dict[str, Dict[str, Any]]:
        """从EvalScope注册表动态加载benchmark信息"""
        try:
            # 导入EvalScope注册表
            from evalscope.api.registry import BENCHMARK_REGISTRY
            
            # 确保所有benchmarks都被导入
            import evalscope.benchmarks
            
            evalscope_benchmarks = {}
            
            for benchmark_name, benchmark_meta in BENCHMARK_REGISTRY.items():
                try:
                    # 转换EvalScope的BenchmarkMeta到我们的格式
                    benchmark_info = cls._convert_benchmark_meta(benchmark_name, benchmark_meta)
                    evalscope_benchmarks[benchmark_name] = benchmark_info
                    logger.debug(f"加载EvalScope benchmark: {benchmark_name}")
                except Exception as e:
                    logger.warning(f"无法转换benchmark {benchmark_name}: {e}")
                    continue
            
            logger.info(f"成功从EvalScope加载了 {len(evalscope_benchmarks)} 个benchmarks")
            return evalscope_benchmarks
            
        except ImportError as e:
            logger.warning(f"无法导入EvalScope: {e}")
            # 尝试从官网API获取
            return cls._load_benchmarks_from_api()
        except Exception as e:
            logger.error(f"加载EvalScope benchmarks失败: {e}")
            # 尝试从官网API获取
            return cls._load_benchmarks_from_api()
    
    @classmethod
    def _load_benchmarks_from_api(cls) -> Dict[str, Dict[str, Any]]:
        """从EvalScope官网API获取benchmark信息"""
        try:
            import requests
            import json
            
            # EvalScope官方API端点（如果存在）
            api_urls = [
                "https://api.evalscope.org/benchmarks",
                "https://evalscope.readthedocs.io/api/benchmarks.json",
                "https://raw.githubusercontent.com/modelscope/eval-scope/main/docs/benchmarks.json"
            ]
            
            for api_url in api_urls:
                try:
                    response = requests.get(api_url, timeout=10)
                    if response.status_code == 200:
                        data = response.json()
                        benchmarks = {}
                        
                        # 解析API返回的数据
                        if isinstance(data, list):
                            for item in data:
                                if isinstance(item, dict) and 'name' in item:
                                    benchmarks[item['name']] = cls._convert_api_benchmark(item)
                        elif isinstance(data, dict) and 'benchmarks' in data:
                            for name, info in data['benchmarks'].items():
                                benchmarks[name] = cls._convert_api_benchmark(info)
                        
                        if benchmarks:
                            logger.info(f"从API {api_url} 获取了 {len(benchmarks)} 个benchmarks")
                            return benchmarks
                            
                except Exception as e:
                    logger.debug(f"API {api_url} 获取失败: {e}")
                    continue
            
            logger.warning("所有API端点都无法获取benchmark数据")
            return {}
            
        except Exception as e:
            logger.error(f"从API获取benchmarks失败: {e}")
            return {}
    
    @classmethod
    def _convert_api_benchmark(cls, api_data: Dict[str, Any]) -> Dict[str, Any]:
        """转换API返回的benchmark数据"""
        return {
            'name': api_data.get('name', ''),
            'display_name': api_data.get('display_name', api_data.get('name', '').upper()),
            'description': api_data.get('description', ''),
            'category': api_data.get('category', '其他'),
            'language': api_data.get('language', 'English'),
            'num_samples': api_data.get('num_samples', 1000),
            'file_size': api_data.get('file_size', '~50 MB'),
            'tags': api_data.get('tags', []),
            'type': api_data.get('type', 'llm'),
            'source': 'api',
            'num_subsets': api_data.get('num_subsets', 1)  # 默认1个子集
        }
    
    @classmethod
    def _convert_benchmark_meta(cls, name: str, meta) -> Dict[str, Any]:
        """将EvalScope的BenchmarkMeta转换为我们的格式"""
        # 从meta中提取信息
        display_name = getattr(meta, 'pretty_name', None) or name.upper()
        description = getattr(meta, 'description', None) or cls._generate_description(name, {'display_name': display_name})
        tags = getattr(meta, 'tags', [])
        
        # 推断类别和语言
        category = cls._infer_category(name, tags, description)
        language = cls._infer_language(name, tags, description)
        
        # 推断样本数量和文件大小（这些信息在meta中通常不直接可用）
        num_samples = cls._estimate_samples(name)
        file_size = cls._estimate_file_size(name)
        
        # 确定类型
        benchmark_type = cls._infer_type(name, tags)
        
        return {
            'name': name,
            'display_name': display_name,
            'category': category,
            'language': language,
            'num_samples': num_samples,
            'file_size': file_size,
            'description': description,
            'tags': tags + cls._generate_tags(name, {'category': category}),
            'type': benchmark_type,
            'source': 'evalscope',
            'num_subsets': cls._estimate_subsets(name)  # 估算子集数量
        }
    
    @classmethod
    def _infer_category(cls, name: str, tags: List[str], description: str) -> str:
        """根据benchmark名称和标签推断类别"""
        name_lower = name.lower()
        
        # 基于名称的映射
        if any(word in name_lower for word in ['math', 'gsm', 'competition']):
            return '数学推理'
        elif any(word in name_lower for word in ['code', 'human', 'mbpp', 'live']):
            return '代码生成'
        elif any(word in name_lower for word in ['mmlu', 'cmmlu', 'ceval']):
            return '通用能力' if 'chinese' not in name_lower and 'ceval' not in name_lower and 'cmmlu' not in name_lower else '中文能力'
        elif any(word in name_lower for word in ['arc', 'science', 'gpqa']):
            return '科学推理'
        elif any(word in name_lower for word in ['hella', 'wino', 'piqa', 'common']):
            return '常识推理'
        elif any(word in name_lower for word in ['bbh', 'drop', 'hard', 'difficult']):
            return '困难推理'
        elif any(word in name_lower for word in ['race', 'reading', 'comprehension']):
            return '阅读理解'
        elif any(word in name_lower for word in ['arena', 'mt_bench', 'alpaca', 'dialogue']):
            return '对话能力'
        elif any(word in name_lower for word in ['truth', 'safety', 'align']):
            return '安全对齐'
        elif any(word in name_lower for word in ['mm', 'vision', 'image', 'visual', 'vlm']):
            return '多模态理解'
        else:
            return '其他'
    
    @classmethod
    def _infer_language(cls, name: str, tags: List[str], description: str) -> str:
        """根据benchmark名称推断语言"""
        name_lower = name.lower()
        chinese_indicators = ['chinese', 'cmmlu', 'ceval']
        
        if any(indicator in name_lower for indicator in chinese_indicators):
            return 'Chinese'
        else:
            return 'English'
    
    @classmethod
    def _infer_type(cls, name: str, tags: List[str]) -> str:
        """推断benchmark类型"""
        name_lower = name.lower()
        vlm_indicators = ['mm', 'vision', 'image', 'visual', 'vlm', 'multimodal']
        
        if any(indicator in name_lower for indicator in vlm_indicators):
            return 'vlm'
        else:
            return 'llm'
    
    @classmethod
    def _estimate_samples(cls, name: str) -> int:
        """估算样本数量"""
        # 基于已知数据估算
        known_samples = {
            'mmlu': 14042, 'cmmlu': 11528, 'ceval': 13948,
            'gsm8k': 1319, 'competition_math': 5000, 'humaneval': 164,
            'arc': 7787, 'hellaswag': 10042, 'bbh': 6511
        }
        return known_samples.get(name.lower(), 1000)  # 默认1000
    
    @classmethod
    def _estimate_file_size(cls, name: str) -> str:
        """估算文件大小"""
        # 基于已知数据估算
        known_sizes = {
            'mmlu': '89 MB', 'cmmlu': '76 MB', 'ceval': '92 MB',
            'gsm8k': '12 MB', 'competition_math': '45 MB', 'humaneval': '3 MB',
            'arc': '25 MB', 'hellaswag': '68 MB', 'bbh': '59 MB'
        }
        return known_sizes.get(name.lower(), '~50 MB')  # 默认估算
    
    @classmethod
    def _estimate_subsets(cls, name: str) -> int:
        """估算子集数量"""
        # 基于已知数据估算
        known_subsets = {
            'mmlu': 57, 'cmmlu': 67, 'ceval': 52,
            'gsm8k': 1, 'competition_math': 5, 'humaneval': 1,
            'arc': 2, 'hellaswag': 1, 'bbh': 27, 'drop': 1,
            'race': 2, 'alpaca_eval': 1, 'mmmu': 30,
            'math_500': 5
        }
        return known_subsets.get(name.lower(), 1)  # 默认1个子集
    
    @classmethod
    def get_all_benchmarks(cls) -> Dict[str, Dict[str, Any]]:
        """获取所有支持的benchmarks - 优先使用EvalScope原生基准，失败时回退到官方列表"""
        # 检查缓存
        now = datetime.now()
        if (cls._cache_timestamp and 
            now - cls._cache_timestamp < cls._cache_ttl and 
            cls._cache):
            logger.debug("返回缓存的benchmark数据")
            return cls._cache.copy()
        
        all_benchmarks = {}
        
        # 优先从EvalScope动态获取
        try:
            evalscope_benchmarks = cls._load_evalscope_benchmarks()
            if evalscope_benchmarks:
                all_benchmarks.update(evalscope_benchmarks)
                logger.info(f"✅ 从EvalScope获取了 {len(evalscope_benchmarks)} 个benchmarks")
            else:
                logger.warning("⚠️ EvalScope返回空列表，回退到官方基准列表")
                all_benchmarks = cls.get_official_benchmarks()
        except Exception as e:
            logger.error(f"❌ 从EvalScope获取benchmarks失败: {e}")
            # 如果失败，回退到官方基准列表
            logger.warning("⚠️ EvalScope获取失败，使用官方基准列表作为fallback")
            all_benchmarks = cls.get_official_benchmarks()
        
        # 更新缓存
        cls._cache = all_benchmarks.copy()
        cls._cache_timestamp = now
        
        logger.info(f"✅ 总共获取了 {len(all_benchmarks)} 个benchmarks")
        return all_benchmarks
    
    @classmethod
    def get_official_benchmarks(cls) -> Dict[str, Dict[str, Any]]:
        """获取ModelScope官方支持的48个benchmarks"""
        # ModelScope官方支持的基准列表（基于官方文档）
        OFFICIAL_MODELSCOPE_BENCHMARKS = {
            # 基础LLM基准
            'mmlu': {'display_name': 'MMLU', 'category': '通用能力', 'language': 'English', 'num_samples': 14042, 'file_size': '89 MB', 'num_subsets': 57},
            'cmmlu': {'display_name': 'CMMLU', 'category': '中文能力', 'language': 'Chinese', 'num_samples': 11528, 'file_size': '76 MB', 'num_subsets': 67},
            'ceval': {'display_name': 'C-Eval', 'category': '中文能力', 'language': 'Chinese', 'num_samples': 13948, 'file_size': '92 MB', 'num_subsets': 52},
            'gsm8k': {'display_name': 'GSM8K', 'category': '数学推理', 'language': 'English', 'num_samples': 1319, 'file_size': '12 MB', 'num_subsets': 1},
            'competition_math': {'display_name': 'MATH', 'category': '数学推理', 'language': 'English', 'num_samples': 5000, 'file_size': '45 MB', 'num_subsets': 5},
            'arc': {'display_name': 'ARC', 'category': '科学推理', 'language': 'English', 'num_samples': 7787, 'file_size': '25 MB', 'num_subsets': 2},
            'humaneval': {'display_name': 'HumanEval', 'category': '代码生成', 'language': 'English', 'num_samples': 164, 'file_size': '3 MB', 'num_subsets': 1},
            'hellaswag': {'display_name': 'HellaSwag', 'category': '常识推理', 'language': 'English', 'num_samples': 10042, 'file_size': '68 MB', 'num_subsets': 1},
            'winogrande': {'display_name': 'WinoGrande', 'category': '常识推理', 'language': 'English', 'num_samples': 1767, 'file_size': '5 MB', 'num_subsets': 1},
            'bbh': {'display_name': 'BBH', 'category': '困难推理', 'language': 'English', 'num_samples': 6511, 'file_size': '59 MB', 'num_subsets': 27},
            'drop': {'display_name': 'DROP', 'category': '困难推理', 'language': 'English', 'num_samples': 9536, 'file_size': '125 MB', 'num_subsets': 1},
            'race': {'display_name': 'RACE', 'category': '阅读理解', 'language': 'English', 'num_samples': 25047, 'file_size': '156 MB', 'num_subsets': 2},
            'alpaca_eval': {'display_name': 'AlpacaEval', 'category': '对话能力', 'language': 'English', 'num_samples': 805, 'file_size': '15 MB', 'num_subsets': 1},
            
            # 多模态基准
            'mmmu': {'display_name': 'MMMU', 'category': '多模态理解', 'language': 'English', 'num_samples': 11500, 'file_size': '1.5 GB', 'num_subsets': 30},
            'mmmu_pro': {'display_name': 'MMMU-Pro', 'category': '多模态理解', 'language': 'English', 'num_samples': 2000, 'file_size': '300 MB', 'num_subsets': 10},
            'mm_bench': {'display_name': 'MM-Bench', 'category': '多模态理解', 'language': 'English', 'num_samples': 1000, 'file_size': '200 MB', 'num_subsets': 4},
            'mm_star': {'display_name': 'MM-Star', 'category': '多模态理解', 'language': 'English', 'num_samples': 1500, 'file_size': '250 MB', 'num_subsets': 6},
            
            # 高级基准
            'arena_hard': {'display_name': 'Arena-Hard', 'category': '对话能力', 'language': 'English', 'num_samples': 1000, 'file_size': '50 MB', 'num_subsets': 1},
            'truthful_qa': {'display_name': 'TruthfulQA', 'category': '安全对齐', 'language': 'English', 'num_samples': 817, 'file_size': '20 MB', 'num_subsets': 1},
            'needle_haystack': {'display_name': 'Needle-Haystack', 'category': '长文本理解', 'language': 'English', 'num_samples': 1000, 'file_size': '30 MB', 'num_subsets': 1},
            
            # 新增基准
            'simple_qa': {'display_name': 'Simple-QA', 'category': '问答能力', 'language': 'English', 'num_samples': 1000, 'file_size': '15 MB', 'num_subsets': 1},
            'docmath': {'display_name': 'DocMath', 'category': '数学推理', 'language': 'English', 'num_samples': 1000, 'file_size': '25 MB', 'num_subsets': 1},
            'ifeval': {'display_name': 'IFEval', 'category': '指令遵循', 'language': 'English', 'num_samples': 1000, 'file_size': '20 MB', 'num_subsets': 1},
            'iquiz': {'display_name': 'IQuiz', 'category': '知识问答', 'language': 'English', 'num_samples': 1000, 'file_size': '15 MB', 'num_subsets': 1},
            'process_bench': {'display_name': 'Process-Bench', 'category': '过程推理', 'language': 'English', 'num_samples': 1000, 'file_size': '30 MB', 'num_subsets': 1},
            'mmlu_redux': {'display_name': 'MMLU-Redux', 'category': '通用能力', 'language': 'English', 'num_samples': 1000, 'file_size': '20 MB', 'num_subsets': 1},
            'omni_bench': {'display_name': 'Omni-Bench', 'category': '综合能力', 'language': 'English', 'num_samples': 1000, 'file_size': '40 MB', 'num_subsets': 1},
            'real_world_qa': {'display_name': 'Real-World-QA', 'category': '现实问答', 'language': 'English', 'num_samples': 1000, 'file_size': '25 MB', 'num_subsets': 1},
            'hle': {'display_name': 'HLE', 'category': '高级推理', 'language': 'English', 'num_samples': 1000, 'file_size': '30 MB', 'num_subsets': 1},
            'general_qa': {'display_name': 'General-QA', 'category': '通用问答', 'language': 'English', 'num_samples': 1000, 'file_size': '20 MB', 'num_subsets': 1},
            'data_collection': {'display_name': 'Data-Collection', 'category': '数据收集', 'language': 'English', 'num_samples': 1000, 'file_size': '35 MB', 'num_subsets': 1},
            'aime25': {'display_name': 'AIME-25', 'category': '数学竞赛', 'language': 'English', 'num_samples': 1000, 'file_size': '15 MB', 'num_subsets': 1},
            'aime24': {'display_name': 'AIME-24', 'category': '数学竞赛', 'language': 'English', 'num_samples': 1000, 'file_size': '15 MB', 'num_subsets': 1},
            'general_mcq': {'display_name': 'General-MCQ', 'category': '多选题', 'language': 'English', 'num_samples': 1000, 'file_size': '20 MB', 'num_subsets': 1},
            'tau_bench': {'display_name': 'TAU-Bench', 'category': '技术评估', 'language': 'English', 'num_samples': 1000, 'file_size': '25 MB', 'num_subsets': 1},
            'tool_bench': {'display_name': 'Tool-Bench', 'category': '工具使用', 'language': 'English', 'num_samples': 1000, 'file_size': '30 MB', 'num_subsets': 1},
            'olympiad_bench': {'display_name': 'Olympiad-Bench', 'category': '竞赛题', 'language': 'English', 'num_samples': 1000, 'file_size': '25 MB', 'num_subsets': 1},
            'minerva_math': {'display_name': 'Minerva-Math', 'category': '数学推理', 'language': 'English', 'num_samples': 1000, 'file_size': '20 MB', 'num_subsets': 1},
            'frames': {'display_name': 'Frames', 'category': '框架理解', 'language': 'English', 'num_samples': 1000, 'file_size': '30 MB', 'num_subsets': 1},
            'trivia_qa': {'display_name': 'Trivia-QA', 'category': '知识问答', 'language': 'English', 'num_samples': 1000, 'file_size': '25 MB', 'num_subsets': 1},
            'bfcl_v3': {'display_name': 'BFCL-v3', 'category': '基准测试', 'language': 'English', 'num_samples': 1000, 'file_size': '35 MB', 'num_subsets': 1},
            'ai2d': {'display_name': 'AI2D', 'category': '图表理解', 'language': 'English', 'num_samples': 1000, 'file_size': '40 MB', 'num_subsets': 1},
            'math_500': {'display_name': 'Math-500', 'category': '数学题', 'language': 'English', 'num_samples': 500, 'file_size': '10 MB', 'num_subsets': 5},
            'general_t2i': {'display_name': 'General-T2I', 'category': '文本生成图像', 'language': 'English', 'num_samples': 1000, 'file_size': '50 MB', 'num_subsets': 1},
            'tifa160': {'display_name': 'TIFA-160', 'category': '图像评估', 'language': 'English', 'num_samples': 160, 'file_size': '8 MB', 'num_subsets': 1},
            'evalmuse': {'display_name': 'EvalMuse', 'category': '音乐评估', 'language': 'English', 'num_samples': 1000, 'file_size': '60 MB', 'num_subsets': 1},
            'genai_bench': {'display_name': 'GenAI-Bench', 'category': '生成AI', 'language': 'English', 'num_samples': 1000, 'file_size': '45 MB', 'num_subsets': 1},
            'hpdv2': {'display_name': 'HPD-v2', 'category': '高性能计算', 'language': 'English', 'num_samples': 1000, 'file_size': '40 MB', 'num_subsets': 1},
            'amc': {'display_name': 'AMC', 'category': '数学竞赛', 'language': 'English', 'num_samples': 1000, 'file_size': '20 MB', 'num_subsets': 1},
            'gedit': {'display_name': 'GEdit', 'category': '文本编辑', 'language': 'English', 'num_samples': 1000, 'file_size': '25 MB', 'num_subsets': 1},
            'chinese_simpleqa': {'display_name': 'Chinese-SimpleQA', 'category': '中文问答', 'language': 'Chinese', 'num_samples': 1000, 'file_size': '20 MB', 'num_subsets': 1},
            'health_bench': {'display_name': 'Health-Bench', 'category': '医疗健康', 'language': 'English', 'num_samples': 1000, 'file_size': '30 MB', 'num_subsets': 1},
            'multi_if': {'display_name': 'Multi-IF', 'category': '多条件推理', 'language': 'English', 'num_samples': 1000, 'file_size': '35 MB', 'num_subsets': 1},
            'musr': {'display_name': 'MuSR', 'category': '多步推理', 'language': 'English', 'num_samples': 1000, 'file_size': '30 MB', 'num_subsets': 1},
            'math_vista': {'display_name': 'Math-Vista', 'category': '视觉数学', 'language': 'English', 'num_samples': 1000, 'file_size': '40 MB', 'num_subsets': 1},
            'maritime_bench': {'display_name': 'Maritime-Bench', 'category': '海事知识', 'language': 'English', 'num_samples': 1000, 'file_size': '25 MB', 'num_subsets': 1},
            'super_gpqa': {'display_name': 'Super-GPQA', 'category': '科学问答', 'language': 'English', 'num_samples': 1000, 'file_size': '35 MB', 'num_subsets': 1},
            'live_code_bench': {'display_name': 'Live-Code-Bench', 'category': '代码执行', 'language': 'English', 'num_samples': 1000, 'file_size': '30 MB', 'num_subsets': 1},
            'gpqa_diamond': {'display_name': 'GPQA-Diamond', 'category': '科学问答', 'language': 'English', 'num_samples': 1000, 'file_size': '30 MB', 'num_subsets': 1},
            'general_arena': {'display_name': 'General-Arena', 'category': '综合竞技', 'language': 'English', 'num_samples': 1000, 'file_size': '40 MB', 'num_subsets': 1},
            'cc_bench': {'display_name': 'CC-Bench', 'category': '代码理解', 'language': 'English', 'num_samples': 1000, 'file_size': '25 MB', 'num_subsets': 1},
        }
        
        official_benchmarks = {}
        for name, info in OFFICIAL_MODELSCOPE_BENCHMARKS.items():
            official_benchmarks[name] = {
                'name': name,
                **info,
                'description': cls._generate_description(name, info),
                'tags': cls._generate_tags(name, info),
                'type': cls._infer_type(name, []),
                'source': 'modelscope_official'
            }
        
        logger.info(f"获取了 {len(official_benchmarks)} 个ModelScope官方benchmarks")
        return official_benchmarks
    
    @classmethod
    def get_benchmarks_by_category(cls, category: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
        """按类别筛选benchmarks"""
        all_benchmarks = cls.get_all_benchmarks()
        
        if not category:
            return all_benchmarks
        
        return {
            name: info for name, info in all_benchmarks.items()
            if info['category'] == category
        }
    
    @classmethod
    def get_benchmarks_by_language(cls, language: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
        """按语言筛选benchmarks"""
        all_benchmarks = cls.get_all_benchmarks()
        
        if not language:
            return all_benchmarks
        
        return {
            name: info for name, info in all_benchmarks.items()
            if info['language'] == language
        }
    
    @classmethod
    def _generate_description(cls, name: str, info: Dict[str, Any]) -> str:
        """生成benchmark描述"""
        descriptions = {
            'mmlu': '大规模多任务语言理解，涵盖57个学科领域',
            'cmmlu': '中文多任务语言理解，涵盖多个中文学科',
            'ceval': '中文语言模型综合能力评估，涵盖多个学科',
            'gsm8k': '小学数学应用题，测试基础数学推理能力',
            'competition_math': '高难度数学问题，包含代数、几何、概率等',
            'arc': 'AI推理挑战，包含科学问题的逻辑推理',
            'arc_challenge': 'ARC挑战集，更高难度的科学推理',
            'humaneval': '代码生成与编程能力评测，Python函数实现',
            'hellaswag': '常识推理能力测试，需要理解日常生活场景',
            'winogrande': '代词消歧推理，测试常识理解',
            'bbh': '超难大模型基准测试，精选最具挑战性任务',
            'drop': '阅读理解与数值推理结合',
            'race': '阅读理解测试，来自中学和高中考试',
            'c3': '中文多选阅读理解',
            'alpaca_eval': '指令遵循能力评测',
            'mt_bench': '多轮对话能力评测',
            'seedbench': '多模态生成评测基准',
            'mmmu': '大学级别多模态理解与推理',
            'mathvista': '视觉数学推理评测',
        }
        
        return descriptions.get(name, f"{info['display_name']} benchmark")
    
    @classmethod
    def _generate_tags(cls, name: str, info: Dict[str, Any]) -> List[str]:
        """生成benchmark标签"""
        tags = []
        
        # 基于类别添加标签
        category_tags = {
            '通用能力': ['knowledge', 'general', '权威'],
            '中文能力': ['chinese', '中文', 'knowledge'],
            '数学推理': ['math', 'reasoning', '数学'],
            '科学推理': ['science', 'reasoning', '科学'],
            '代码生成': ['coding', 'programming', '代码'],
            '常识推理': ['commonsense', 'reasoning', '常识'],
            '困难推理': ['hard', 'challenging', '困难'],
            '阅读理解': ['reading', 'comprehension', '理解'],
            '对话能力': ['dialogue', 'conversation', '对话'],
            '安全对齐': ['safety', 'alignment', '安全'],
            '多模态理解': ['multimodal', 'vision', '多模态'],
            '多模态推理': ['multimodal', 'reasoning', '视觉'],
        }
        
        tags.extend(category_tags.get(info['category'], []))
        
        # 添加热门标签
        hot_benchmarks = ['mmlu', 'gsm8k', 'humaneval', 'cmmlu', 'ceval']
        if name in hot_benchmarks:
            tags.append('热门')
        
        return list(set(tags))  # 去重
    
    @classmethod
    def get_benchmark_count(cls) -> int:
        """获取benchmark总数"""
        return len(cls.get_all_benchmarks())
    
    @classmethod
    def refresh_cache(cls) -> Dict[str, Dict[str, Any]]:
        """强制刷新缓存并重新获取benchmark数据"""
        cls._cache = {}
        cls._cache_timestamp = None
        logger.info("强制刷新benchmark缓存")
        return cls.get_all_benchmarks()
    
    @classmethod
    def get_cache_info(cls) -> Dict[str, Any]:
        """获取缓存信息"""
        return {
            'cache_size': len(cls._cache),
            'cache_timestamp': cls._cache_timestamp.isoformat() if cls._cache_timestamp else None,
            'cache_ttl_hours': cls._cache_ttl.total_seconds() / 3600,
            'is_cache_valid': (
                cls._cache_timestamp and 
                datetime.now() - cls._cache_timestamp < cls._cache_ttl
            ) if cls._cache_timestamp else False
        }


# 导出函数供外部使用
def get_available_benchmarks_from_registry(
    category: Optional[str] = None,
    language: Optional[str] = None,
    official_only: bool = False
) -> List[Dict[str, Any]]:
    """从注册表获取可用的benchmarks"""
    if official_only:
        # 使用ModelScope官方基准列表
        benchmarks_dict = BenchmarkRegistry.get_official_benchmarks()
    else:
        # 使用所有基准（包括实验性基准）
        benchmarks_dict = BenchmarkRegistry.get_all_benchmarks()
    
    if category:
        benchmarks_dict = {k: v for k, v in benchmarks_dict.items() if v['category'] == category}
    if language:
        benchmarks_dict = {k: v for k, v in benchmarks_dict.items() if v['language'] == language}
    
    return list(benchmarks_dict.values())


