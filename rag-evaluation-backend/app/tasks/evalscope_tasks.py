"""
EvalScope任务模块 - WebSocket进度更新功能
"""

import asyncio
import logging
from typing import Dict, Any
from app.core.config import settings

logger = logging.getLogger(__name__)

async def send_progress_update(task_id: int, progress: int, message: str, detailed_progress: Dict[str, Any]):
    """
    发送WebSocket进度更新
    
    Args:
        task_id: 任务ID
        progress: 进度百分比 (0-100)
        message: 进度消息
        detailed_progress: 详细进度信息
    """
    try:
        # 导入WebSocket管理器
        from app.api.api_v1.endpoints.evalscope import ws_manager
        
        # 构建消息
        update_message = {
            "type": "progress_update",
            "task_id": task_id,
            "progress": progress,
            "message": message,
            "detailed_progress": detailed_progress,
            "timestamp": asyncio.get_event_loop().time()
        }
        
        # 发送WebSocket消息
        await ws_manager.send_message(task_id, update_message)
        
        logger.debug(f"WebSocket进度更新已发送: 任务{task_id}, 进度{progress}%")
        
    except Exception as e:
        logger.warning(f"WebSocket发送失败: {e}")
        # WebSocket发送失败不应该影响主流程，只记录警告
